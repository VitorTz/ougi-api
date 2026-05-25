from fastapi import (
    APIRouter, 
    status, 
    Request,
    Depends,    
    Query
)
from src.dependencies import get_limiter
from src.tables import login_attempts as login_attempts_table
from src.schemas.pagination import Pagination
from src.schemas.login import LoginAttemptResponse
from datetime import datetime
from src.tables import tokens as tokens_table
from src.db import db_connection
from asyncpg import Connection


router = APIRouter(prefix="/auth")
limiter = get_limiter()



@router.get(
    "/login-attempts",
    status_code=status.HTTP_200_OK,
    response_model=Pagination[LoginAttemptResponse],
    summary="Login Attempts Report",
    description="Retrieves a paginated and filterable report of all login attempts (success and failures) for security auditing."
)
@limiter.limit("16/minute")
async def report_login_attempts(
    request: Request,
    conn: Connection = Depends(db_connection),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Items to skip"),
    identifier: str | None = Query(None, description="Search by username or email (partial match)"),
    ip_address: str | None = Query(None, description="Exact match for an IP address"),
    success: bool | None = Query(None, description="Filter by successful or failed attempts"),
    start_date: datetime | None = Query(None, description="Filter from this date/time"),
    end_date: datetime | None = Query(None, description="Filter up to this date/time")
):
    return await login_attempts_table.get_login_attempts_report(
        conn=conn,
        limit=limit,
        offset=offset,
        identifier=identifier,
        ip_address=ip_address,
        success=success,
        start_date=start_date,
        end_date=end_date
    )


@router.delete("/login-attempts", status_code=status.HTTP_200_OK)
@limiter.limit("16/minute")
async def clear_old_login_attempts(
    request: Request,
    hours_to_keep: int = Query(
        default=1, 
        ge=0, 
        title="Hours to Keep",
        description="Delete login attempts older than this many hours. Use 0 to truncate and delete all records."
    ),
    conn: Connection = Depends(db_connection)
) -> dict:
    """
    Cleans up old login attempts to free up database space and returns the amount of records deleted.
    """    
    deleted_count: int = await login_attempts_table.delete_old_login_attempts(
        hours_to_keep,
        conn
    )
        
    return {
        "message": "Login attempts cleaned up successfully.",
        "deleted_count": deleted_count,
        "hours_kept": hours_to_keep
    }


@router.delete("/refresh-tokens", status_code=status.HTTP_200_OK)
@limiter.limit("16/minute")
async def clear_expired_tokens(
    request: Request,
    days_to_keep: int = Query(
        default=7, 
        ge=0, 
        title="Days to Keep Dead Tokens",
        description="Delete expired or revoked tokens older than this many days. Use 0 to delete all currently dead tokens. Active tokens are never deleted."
    ),
    conn: Connection = Depends(db_connection)
) -> dict:
    """
    Cleans up expired and revoked refresh tokens to free up database space.
    Preserves active sessions.
    """
    deleted_count: int = await tokens_table.delete_expired_refresh_tokens(
        days_to_keep=days_to_keep, 
        conn=conn
    )
    
    return {
        "message": "Expired refresh tokens cleaned up successfully.",
        "deleted_count": deleted_count,
        "days_kept": days_to_keep
    }