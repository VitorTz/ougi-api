from fastapi import (
    APIRouter, 
    status, 
    Request,
    Depends,    
    Query
)
from src.dependencies import get_limiter
from src.tables import login_attempts as login_attempts_table
from src.tables import tokens as tokens_table
from src.db import db_connection
from asyncpg import Connection


router = APIRouter(prefix="/auth")
limiter = get_limiter()


@router.delete("/", status_code=status.HTTP_200_OK)
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
        hours_to_keep=hours_to_keep, 
        conn=conn
    )
        
    return {
        "message": "Login attempts cleaned up successfully.",
        "deleted_count": deleted_count,
        "hours_kept": hours_to_keep
    }


@router.delete("/", status_code=status.HTTP_200_OK)
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