from src.schemas.log import SystemLogResponse
from src.exceptions import DatabaseException
from src.schemas.pagination import Pagination
from asyncpg import Connection
from uuid import UUID
from src import db
import json


async def insert_log(
    error_type: str,
    error_message: str,
    error_level: str = "ERROR",
    user_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    request_method: str | None = None,
    request_path: str | None = None,
    failed_query: str | None = None,
    query_parameters: dict | None = None,
    execution_context: dict | None = None,
    stack_trace: str | None = None,
    conn: Connection | None = None
) -> str | None:
    params_json = json.dumps(query_parameters) if query_parameters else None
    context_json = json.dumps(execution_context) if execution_context else None

    query = """
        INSERT INTO system_logs (
            user_id, 
            ip_address, 
            user_agent, 
            request_method, 
            request_path,
            error_level, 
            error_type, 
            error_message, 
            failed_query, 
            query_parameters, 
            execution_context, 
            stack_trace
        ) VALUES (
            $1, $2::INET, $3, $4, $5, 
            $6, $7, $8, $9, 
            $10::JSONB, $11::JSONB, $12
        );
    """
    if conn is None:
        async with db.pool.acquire() as conn:
            await conn.execute(
                query,
                user_id,
                ip_address,
                user_agent,
                request_method,
                request_path,
                error_level,
                error_type,
                error_message,
                failed_query,
                params_json,
                context_json,
                stack_trace
            )
    else:
        await conn.execute(
                query,
                user_id,
                ip_address,
                user_agent,
                request_method,
                request_path,
                error_level,
                error_type,
                error_message,
                failed_query,
                params_json,
                context_json,
                stack_trace
            )



async def get_logs(
    limit: int,
    offset: int,
    conn: Connection,
    error_level: str | None = None,
    user_id: UUID | str | None = None,
    error_type: str | None = None
) -> Pagination[SystemLogResponse]:
    """
    Retrieves a paginated list of system logs, optionally filtered by level, user, or type.
    Acquires its own connection from the global pool.
    """
    conditions = []
    params = []
        
    if error_level:
        params.append(error_level)
        conditions.append(f"error_level = ${len(params)}")
        
    if user_id:
        params.append(str(user_id))
        conditions.append(f"user_id = ${len(params)}")
        
    if error_type:
        params.append(error_type)
        conditions.append(f"error_type = ${len(params)}")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""    
    count_query = f"SELECT COUNT(id) FROM system_logs {where_clause};"    
    fetch_params = params.copy()
    fetch_params.extend([limit, offset])
        
    fetch_query = f"""
        SELECT 
            id, 
            user_id, 
            ip_address::TEXT as ip_address, 
            user_agent, 
            request_method, 
            request_path, 
            error_level, 
            error_type, 
            error_message, 
            failed_query, 
            query_parameters::TEXT as query_parameters,
            execution_context::TEXT as execution_context, 
            stack_trace, 
            created_at
        FROM 
            system_logs
        {where_clause}
        ORDER BY 
            created_at DESC
        LIMIT ${len(fetch_params) - 1} 
        OFFSET ${len(fetch_params)};
    """
    
    try:
        total_items = await conn.fetchval(count_query, *params)
        if total_items == 0:
            return Pagination(items=[], total_items=0, limit=limit, offset=offset)
        rows = await conn.fetch(fetch_query, *fetch_params)            
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred while fetching system logs.",
            original_error=e,
            query=fetch_query,
            params=fetch_params,
            additional_context={"action": "get_logs"}
        )
    
    parsed_items = [SystemLogResponse(**row) for row in rows]
    
    return Pagination(
        items=parsed_items,
        total_items=total_items,
        limit=limit,
        offset=offset
    )

async def get_log_by_id(log_id: UUID, conn: Connection) -> SystemLogResponse | None:
    """
    Retrieves a specific log entry by its UUID using the global connection pool.
    """
    query = """
        SELECT 
            id, 
            user_id, 
            ip_address::TEXT as ip_address, 
            user_agent, 
            request_method, 
            request_path, 
            error_level, 
            error_type, 
            error_message, 
            failed_query, 
            query_parameters, 
            execution_context, 
            stack_trace, 
            created_at
        FROM 
            system_logs
        WHERE 
            id = $1;
    """    
    row = await conn.fetchrow(query, log_id)
    if row: return SystemLogResponse(**row)


async def delete_log_by_id(log_id: UUID, conn: Connection) -> str | None:
    await conn.execute(
        "DELETE FROM system_logs WHERE id = $1;",
        log_id
    )

async def delete_logs(days_to_keep: int, conn: Connection) -> int:
    """
    Deletes system logs older than the specified number of days and 
    returns the total number of deleted records.
    """
    try:
        if days_to_keep == 0:
            count = await conn.fetchval("SELECT COUNT(id) FROM system_logs;")
            await conn.execute("TRUNCATE TABLE system_logs;")
            return count            
        else:
            query = "DELETE FROM system_logs WHERE created_at < NOW() - make_interval(days => $1);"
            command_tag = await conn.execute(query, days_to_keep)
            _, deleted_count = command_tag.split(" ")
            return int(deleted_count)            
    except Exception as e:
        raise DatabaseException(
            client_message="An error occurred while cleaning up old system logs.",
            original_error=e,
            query="DELETE / TRUNCATE system_logs",
            params=[days_to_keep],
            additional_context={
                "action": "delete_logs", 
                "days_to_keep": days_to_keep
            }
        )