from fastapi import (
    APIRouter, 
    status, 
    Request, 
    Path, 
    Depends,    
    Query
)
from src.schemas.audit_log import AuditLogResponse
from src.dependencies import get_limiter
from src.exceptions import ResourceNotFoundException
from src.tables import audit_log as audit_log_table
from src.db import db_connection
from asyncpg import Connection
from typing import Optional


router = APIRouter()
limiter = get_limiter()


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