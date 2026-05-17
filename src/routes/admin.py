from fastapi import (
    APIRouter, 
    Depends, 
    status, 
    Request, 
    Query, 
    BackgroundTasks, 
    Cookie,
    Path
)
from src.security.cookies import require_admin_access
from src.schemas.user import UserRole, UserPublicResponse
from src.schemas.pagination import Pagination
from src.tables import user as users_table
from src.tables import audit_log as audit_log_table
from src.tables import logs as logs_table
from src.tables import tokens as tokens_table
from src.tables import login_attempts as login_attempts_table
from src.exceptions import ResourceNotFoundException
from src.schemas.log import SystemLogResponse
from src.schemas.audit_log import AuditLogResponse
from src.db import db_connection, refresh_view
from typing import Optional
from asyncpg import Connection
from src.dependencies import get_limiter
from src.util import get_real_client_ip
from src.security import jwt_utils
from uuid import UUID


router = APIRouter(
    prefix="/admin", 
    tags=['admin'], 
    dependencies=[Depends(require_admin_access)]
)
limiter = get_limiter()


# ============================================= 
# DATABASE
# ============================================= 

@router.post("/database/refresh_mv/{mv_name}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("32/minute")
async def refresh_materialized_view(
    request: Request,
    mv_name: str = Path(
        ..., 
        title="Materialized View Name",
        description="The exact name of the materialized view to be refreshed in the database.",
        examples=["mv_manhwa_catalog", "mv_user_statistics"]
    ),
    conn: Connection = Depends(db_connection)
):
    """
    Triggers a manual refresh of a specific materialized view to update its cached data.
    """
    await refresh_view(mv_name, conn)


# ============================================= 
# MODERATORS
# ============================================= 
@router.post("/moderators/{user_id}/role", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("32/minute")
async def update_user_role(
    request: Request,
    background_tasks: BackgroundTasks,
    user_id: str = Path(
        ...,
        title="User ID",
        description="The unique UUID of the user whose role is being updated."
    ),
    role: UserRole = Query(
        ...,
        title="New User Role",
        description="The new role to assign to the user (e.g., admin, moderator, user)."
    ),
    access_token: Optional[str] = Cookie(default=None),
    conn: Connection = Depends(db_connection)
):
    """
    Updates the role of a specific user. 
    Triggers a background task to record the action in the audit logs.
    """
    id_actor: str = jwt_utils.extract_value_from_token(access_token, "sub")
    
    success: bool = await users_table.update_role_user(user_id, role, conn)
    
    if not success:
        raise ResourceNotFoundException("User")
    
    # Audit logging in background
    background_tasks.add_task(
        audit_log_table.insert_audit_log,
        action="update_user_role",
        table_name="users",
        record_id=str(user_id),
        actor_id=id_actor,
        ip_address=get_real_client_ip(request) 
    )


# =============================================
# USERS
# =============================================
@router.get("/users", status_code=status.HTTP_200_OK, response_model=Pagination[UserPublicResponse])
@limiter.limit("32/minute")
async def list_users(
    request: Request,
    limit: int = Query(
        default=32, 
        ge=1, 
        le=64,
        title="Pagination Limit",
        description="Maximum number of users to return per page."
    ),
    offset: int = Query(
        default=0, 
        ge=0,
        title="Pagination Offset",
        description="Number of users to skip before starting to collect the result set."
    ),
    username: Optional[str] = Query(
        default=None, 
        title="Username Filter",
        description="Search for users by partial or exact username (case-insensitive)."
    ),
    role: Optional[str] = Query(
        default=None, 
        title="Role Filter",
        description="Filter the list by a specific user role (e.g., admin, moderator, user)."
    ),
    is_banned: Optional[bool] = Query(
        default=None, 
        title="Ban Status",
        description="Filter users by their current ban status (true for banned, false for active)."
    ),
    conn: Connection = Depends(db_connection)
):
    """
    Retrieves a paginated list of registered users.
    Supports dynamic filtering by username, role, and ban status.
    """
    return await users_table.get_users(
        limit=limit,
        offset=offset,
        conn=conn,
        username=username,
        role=role,
        is_banned=is_banned
    )


@router.delete("/users", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("32/minute")
async def delete_user(
    request: Request,
    user_id: str = Path(
        ...,
        title="User ID",
        description="The unique UUID of the user whose role is being updated."
    ),
    conn: Connection = Depends(db_connection)
):
    await users_table.delete_user(user_id, conn)


# =============================================
# AUTH
# =============================================

@router.delete("/auth", status_code=status.HTTP_200_OK)
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


@router.delete("/auth", status_code=status.HTTP_200_OK)
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

# =============================================
# SYSTEM LOGS
# =============================================
@router.get("/logs", status_code=status.HTTP_200_OK, response_model=Pagination[SystemLogResponse])
@limiter.limit("32/minute")
async def list_logs(
    request: Request,
    limit: int = Query(
        default=32, 
        ge=1, 
        le=64,
        title="Pagination Limit",
        description="Maximum number of logs to return per page."
    ),
    offset: int = Query(
        default=0, 
        ge=0,
        title="Pagination Offset",
        description="Number of logs to skip before starting to collect the result set."
    ),
    error_level: Optional[str] = Query(
        default=None, 
        title="Error Level",
        description="Filter by the severity of the log (e.g., ERROR, WARNING, CRITICAL, INFO)."
    ),
    error_type: Optional[str] = Query(
        default=None, 
        title="Error Type",
        description="Exact match for the Python exception type or custom error category."
    ),
    user_id: Optional[UUID] = Query(
        default=None, 
        title="User ID Filter",
        description="Filter logs generated by a specific user's UUID."
    ),
    conn: Connection = Depends(db_connection)
):
    """
    Retrieves a paginated list of system and error logs.
    Supports filtering by severity level, error type, and specific users.
    """
    return await logs_table.get_logs(
        limit=limit,
        offset=offset,
        conn=conn,
        error_level=error_level,
        user_id=user_id,
        error_type=error_type
    )
    

@router.get("/logs/{log_id}", response_model=SystemLogResponse)
@limiter.limit("16/minute")
async def get_log_details(
    request: Request,
    log_id: UUID = Path(
        ...,
        title="Log ID",
        description="The unique UUID of the specific system log entry to retrieve."
    ),
    conn: Connection = Depends(db_connection)
):
    """
    Retrieves the complete details of a specific system log entry by its ID.
    """
    log: SystemLogResponse | None = await logs_table.get_log_by_id(log_id, conn)
    if not log: raise ResourceNotFoundException("Log entry")
    return log


@router.delete("/logs/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("16/minute")
async def delete_log(
    request: Request, 
    log_id: UUID = Path(
        ...,
        title="Log ID",
        description="The unique UUID of the specific system log entry to delete."
    ), 
    conn: Connection = Depends(db_connection)
):
    """
    Permanently deletes a specific system log entry by its ID.
    """    
    deleted: bool = await logs_table.delete_log_by_id(
        log_id=log_id, 
        conn=conn
    )
        
    if not deleted:
        raise ResourceNotFoundException("Log entry")
    

@router.delete("/logs", status_code=status.HTTP_200_OK)
@limiter.limit("16/minute")
async def clear_old_logs(
    request: Request,
    days_to_keep: int = Query(
        default=30, 
        ge=0, 
        description="Delete logs older than this many days. Use 0 to delete all logs."
    ),
    conn: Connection = Depends(db_connection)
) -> dict:
    """
    Deletes old system logs and returns the amount of records that were deleted.
    """
    deleted_count = await logs_table.delete_logs(days_to_keep, conn)    
    return {
        "message": "Logs cleaned up successfully.",
        "deleted_count": deleted_count,
        "days_kept": days_to_keep
    }


# =============================================
# AUDIT LOG
# =============================================
@router.get("/audit-log", response_model=list[AuditLogResponse], status_code=status.HTTP_200_OK)
@limiter.limit("32/minute")
async def list_audit_logs(
    request: Request,
    limit: int = Query(default=32, ge=1, le=64),
    offset: int = Query(default=0, ge=0),
    action: Optional[str] = Query(default=None, description="Filter by action name (e.g., 'delete_comment')"),
    table_name: Optional[str] = Query(default=None, description="Filter by affected table"),
    actor_id: Optional[str] = Query(default=None, description="Filter by the user who performed the action"),
    record_id: Optional[str] = Query(default=None, description="Filter by the affected record ID"),
    conn: Connection = Depends(db_connection)
):
    """
    Retrieve a paginated list of audit logs with optional filtering.
    """
    return await audit_log_table.get_audit_logs(
        conn=conn,
        limit=limit,
        offset=offset,
        action=action,
        table_name=table_name,
        actor_id=actor_id,
        record_id=record_id
    )


@router.get("/audit-log/{log_id}", response_model=AuditLogResponse, status_code=status.HTTP_200_OK)
@limiter.limit("32/minute")
async def get_audit_log_details(
    request: Request,
    log_id: str = Path(...),
    conn: Connection = Depends(db_connection)
):
    """
    Retrieve specific details of a single audit log entry.
    """
    log_entry = await audit_log_table.get_audit_log_by_id(log_id, conn)
    
    if not log_entry:
        raise ResourceNotFoundException("Audit log entry")
        
    return log_entry


@router.delete("/audit-log/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("16/minute")
async def delete_audit_log(
    request: Request, 
    log_id: str = Path(...), 
    conn: Connection = Depends(db_connection)
):
    """
    Delete a specific audit log. Warning: This should rarely be used.
    """
    success = await audit_log_table.delete_audit_log_by_id(log_id, conn)
    
    if not success: raise ResourceNotFoundException("Audit log entry")


@router.delete("/audit-log", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("16/minute")
async def clear_old_audit_logs(
    request: Request,
    days_to_keep: int = Query(default=30, ge=0, description="Delete logs older than this many days. Use 0 to truncate all."),
    conn: Connection = Depends(db_connection)
):
    """
    Bulk delete old audit logs for database maintenance.
    """
    await audit_log_table.delete_old_audit_logs(days_to_keep, conn)