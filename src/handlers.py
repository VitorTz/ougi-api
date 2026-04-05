from fastapi import BackgroundTasks, Request, status
from fastapi.responses import JSONResponse
from src.exceptions import DatabaseException
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from src.tables import logs as logs_table
from src import util
import traceback


async def database_exception_handler(request: Request, exc: DatabaseException):
    background_tasks = BackgroundTasks()
    background_tasks.add_task(
        logs_table.insert_log,
        error_type=exc.error_type,
        error_level='ERROR',
        user_id=exc.user_id,
        ip_address=util.get_real_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        request_method=request.method,
        request_path=request.url.path,
        failed_query=exc.query,
        query_parameters=str(exc.params) if exc.params else None,
        execution_context=exc.context,
        stack_trace=exc.traceback_str,
        error_message=str(exc.original_error)
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=exc.client_message,
        background=background_tasks
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handles Pydantic validation errors, returning a cleaner 
    response format instead of the default FastAPI structure.
    """
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error.get("loc", []))
        errors.append({"field": field, "message": error.get("msg")})    

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Data validation failed.",
            "details": errors
        }
    )

async def global_exception_handler(request: Request, exc: Exception):
    client_ip = util.get_real_client_ip(request)
    client_user_agent = request.headers.get("user-agent")
        
    stack_trace_str = "".join(
        traceback.format_exception(type(exc), exc, exc.__traceback__)
    )
    
    background_tasks = BackgroundTasks()
        
    background_tasks.add_task(
        logs_table.insert_log,
        error_type=type(exc).__name__,
        error_message=str(exc),
        error_level="CRITICAL",
        request_method=request.method,
        request_path=request.url.path,
        ip_address=client_ip,
        user_agent=client_user_agent,
        stack_trace=stack_trace_str
    )
        
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "An unexpected critical error occurred. Our team has been notified."},
        background=background_tasks
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Ensures all standard HTTPExceptions return a consistent JSON structure.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )