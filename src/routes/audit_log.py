from fastapi import APIRouter, Depends, status, Query, Path, HTTPException, Request
from typing import Optional
from asyncpg import Connection
from src.security.cookies import require_admin_access
from src.schemas.audit_log import AuditLogResponse
from src.db import db_connection
from src.ratelimit import limiter
from src.tables import audit_log as audit_log_table


router = APIRouter(
    prefix='/audit',
    tags=['audit_logs'],
    dependencies=[Depends(require_admin_access)]
)


@router.get("/", response_model=list[AuditLogResponse], status_code=status.HTTP_200_OK)
@limiter.limit("30/minute")
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
    logs = await audit_log_table.get_audit_logs(
        conn=conn,
        limit=limit,
        offset=offset,
        action=action,
        table_name=table_name,
        actor_id=actor_id,
        record_id=record_id
    )
    return logs


@router.get("/{log_id}", response_model=AuditLogResponse, status_code=status.HTTP_200_OK)
@limiter.limit("30/minute")
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Audit log entry not found."
        )
        
    return log_entry


@router.delete("/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_audit_log(
    request: Request, 
    log_id: str = Path(...), 
    conn: Connection = Depends(db_connection)
):
    """
    Delete a specific audit log. Warning: This should rarely be used.
    """
    success = await audit_log_table.delete_audit_log_by_id(log_id, conn)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Audit log entry not found."
        )


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
async def clear_old_audit_logs(
    request: Request,
    days_to_keep: int = Query(default=30, ge=0, description="Delete logs older than this many days. Use 0 to truncate all."),
    conn: Connection = Depends(db_connection)
):
    """
    Bulk delete old audit logs for database maintenance.
    """
    await audit_log_table.delete_old_audit_logs(days_to_keep, conn)