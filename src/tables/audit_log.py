from asyncpg import Connection
from src.tables import logs as logs_table
from src.exceptions import DatabaseException
from src.schemas.pagination import Pagination
from src.schemas.audit_log import AuditLogResponse
from src import util
from src import db
import json


async def insert_audit_log(
    action: str,
    table_name: str,
    record_id: str,
    actor_id: str | None = None,
    old_data: dict | None = None,
    new_data: dict | None = None,
    ip_address: str | None = None
) -> None:
    query = """
        INSERT INTO audit_log (
            actor_id, 
            action, 
            table_name, 
            record_id, 
            old_data, 
            new_data, 
            ip_address
        ) VALUES (
            $1, $2, $3, $4, $5::jsonb, $6::jsonb, $7::inet
        );
    """
    
    old_data_json = json.dumps(old_data) if old_data is not None else None
    new_data_json = json.dumps(new_data) if new_data is not None else None

    params = (
        actor_id,
        action,
        table_name,
        record_id,
        old_data_json,
        new_data_json,
        ip_address
    )

    async with db.pool.acquire() as conn:
        try:
            await conn.execute(query, *params)
        except Exception as e:
            log_user_id = str(actor_id) if util.is_uuid(actor_id) else None
            await logs_table.insert_log(
                error_type=type(e).__name__,
                error_message=str(e),
                error_level="ERROR",
                user_id=log_user_id,
                failed_query=query,
                query_parameters={
                    "actor_id": actor_id,
                    "action": action,
                    "table_name": table_name,
                    "record_id": record_id,
                    "old_data": old_data,
                    "new_data": new_data,
                    "ip_address": ip_address
                },
                execution_context={
                    "action": "insert_audit_log",
                    "description": "Failed to insert audit log. Reusing connection for system log."
                },
                stack_trace=util.format_stacktrace(e),
                conn=conn
            )
    

async def get_audit_logs(
    conn: Connection,
    limit: int = 32,
    offset: int = 0,
    action: str | None = None,
    table_name: str | None = None,
    actor_id: str | None = None,
    record_id: str | None = None
) -> Pagination[AuditLogResponse]:
    conditions = []
    params = []
        
    if action:
        params.append(action)
        conditions.append(f"action = ${len(params)}")
        
    if table_name:
        params.append(table_name)
        conditions.append(f"table_name = ${len(params)}")
        
    if actor_id:
        params.append(actor_id)
        conditions.append(f"actor_id = ${len(params)}")
        
    if record_id:
        params.append(record_id)
        conditions.append(f"record_id = ${len(params)}")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        
    params.extend([limit, offset])
        
    query = f"""
        SELECT 
            id, 
            actor_id, 
            action, 
            table_name, 
            record_id, 
            old_data as old_data, 
            new_data as new_data, 
            ip_address::TEXT as ip_address, 
            created_at,
            COUNT(*) OVER() AS total_count
        FROM 
            audit_log
        {where_clause}
        ORDER BY 
            created_at DESC
        LIMIT 
            ${len(params) - 1} 
        OFFSET 
            ${len(params)};
    """
    
    try:
        return await db.fetch_pagination(query, AuditLogResponse, limit, offset, conn, *params)
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred while fetching audit logs.",
            original_error=e,
            query=query,
            params=params,
            additional_context={"action": "get_audit_logs"}
        )


async def get_audit_log_by_id(log_id: str, conn: Connection) -> AuditLogResponse | None:
    query = """
        SELECT 
            id, 
            actor_id, 
            action, 
            table_name, 
            record_id, 
            old_data as old_data, 
            new_data as new_data, 
            ip_address::TEXT as ip_address,
            created_at
        FROM 
            audit_log
        WHERE 
            id = $1;
    """
    try:
        return await db.fetchrow(query, AuditLogResponse, conn, log_id)
    except Exception as e:
        raise DatabaseException(
            client_message="An error occurred while fetching the specific audit log.",
            original_error=e,
            query=query,
            params=[log_id],
            additional_context={
                "action": "get_audit_log_by_id", 
                "log_id": log_id
            }
        )


async def delete_audit_log_by_id(log_id: str, conn: Connection) -> bool:
    query = "DELETE FROM audit_log WHERE id = $1 RETURNING id;"
    try:
        deleted_id = await conn.fetchval(query, log_id)
        return deleted_id is not None
    except Exception as e:
        raise DatabaseException(
            client_message="An error occurred while deleting the audit log.",
            original_error=e,
            query=query,
            params=[log_id],
            additional_context={"action": "delete_audit_log_by_id", "log_id": log_id}
        )


async def delete_old_audit_logs(days_to_keep: int, conn: Connection) -> int:
    """
    Deletes audit logs older than the specified number of days and 
    returns the total number of deleted records.
    Executes in a single database round-trip.
    """
    query = """
        DELETE FROM 
            audit_log 
        WHERE 
            created_at < NOW() - make_interval(days => $1);
        """
    try:
        return await db.delete(query, conn, days_to_keep)
    except Exception as e:
        raise DatabaseException(
            client_message="An error occurred while cleaning up old audit logs.",
            original_error=e,
            query="DELETE FROM audit_log",
            params=[days_to_keep],
            additional_context={
                "action": "delete_logs", 
                "days_to_keep": days_to_keep
            }
        )