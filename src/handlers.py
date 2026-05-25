from fastapi import BackgroundTasks, Request, status
from fastapi.responses import JSONResponse
from src.exceptions import DatabaseException, DuplicateRecordError, EmptyUpdateException
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError
from src.tables import logs as logs_table
from src import util


async def database_exception_handler(request: Request, exc: DatabaseException):
    request_id: str = util.extract_request_id(request)
    background_tasks = BackgroundTasks()
    background_tasks.add_task(
        logs_table.insert_log,
        error_type=exc.error_type,
        error_level='ERROR',
        user_id=exc.user_id,
        ip_address=util.extract_client_ip(request),
        user_agent=util.extract_user_agent(request),
        request_id=request_id,
        request_method=request.method,
        request_path=request.url.path,
        failed_query=exc.query,
        query_parameters=exc.query_parameters,
        stack_trace=exc.traceback_str,
        error_message=exc.error_message
    )

    content = { "message": exc.client_message }
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=content,
        background=background_tasks
    )


async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal data validation error.",
            "details": exc.errors()
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Data validation failed.",
            "details": exc.errors()
        }
    )


async def global_exception_handler(request: Request, exc: Exception):
    request_id = util.extract_request_id(request)
    background_tasks = BackgroundTasks()
    background_tasks.add_task(
        logs_table.insert_log,
        error_type=type(exc).__name__,
        error_message=str(exc),
        error_level="CRITICAL",
        request_method=request.method,
        request_path=request.url.path,
        ip_address=util.extract_client_ip(request),
        request_id=request_id,
        user_agent=util.extract_user_agent(request),
        stack_trace=util.format_stacktrace(exc)
    )
    
    content = {
        "error": "An unexpected critical error occurred. Our team has been notified."
    }
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=content,
        background=background_tasks
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    request_id = util.extract_request_id(request)
    
    background_tasks = BackgroundTasks()
    if exc.status_code >= 500:
        background_tasks.add_task(
            logs_table.insert_log,
            error_type="HTTPException",
            error_level="ERROR",
            ip_address=util.extract_client_ip(request),
            user_agent=util.extract_user_agent(request),
            request_id=request_id,
            request_method=request.method,
            request_path=request.url.path,
            error_message=f"HTTP {exc.status_code}: {exc.detail}",
        )
    
    content = { "error": exc.detail }
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        background=background_tasks
    )


async def duplicate_record_exception_handler(request: Request, exc: DuplicateRecordError):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": exc.detail}
    )


async def empty_update_exception_handler(request: Request, exc: EmptyUpdateException):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": exc.detail}
    )