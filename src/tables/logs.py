from src.schemas.log import SystemLogResponse
from src.exceptions import DatabaseException
from src.schemas.pagination import Pagination
from asyncpg import Connection
from uuid import UUID
from src import db
import json


LOG_INSERT_QUERY = """
    INSERT INTO system_logs (
        user_id, 
        ip_address, 
        request_id,
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
        $1::uuid,
        $2::INET, 
        $3::uuid, 
        $4, 
        $5, 
        $6, 
        $7, 
        $8, 
        $9, 
        $10,
        $11, 
        $12,
        $13
    );
"""


LOG_GET_QUERY = """
    SELECT 
        id, 
        user_id, 
        request_id,
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
    WHERE 
        id = $1;
""" 


async def insert_log(
    error_type: str,
    error_message: str,
    error_level: str = "ERROR",
    user_id: str | UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    request_method: str | None = None,
    request_path: str | None = None,
    failed_query: str | None = None,
    query_parameters: dict | None = None,
    execution_context: dict | None = None,
    stack_trace: str | None = None,
    request_id: str | None = None,
    conn: Connection | None = None
) -> str | None:
    params_json = json.dumps(query_parameters) if query_parameters else None
    context_json = json.dumps(execution_context) if execution_context else None    
    await db.execute(
        LOG_INSERT_QUERY, 
        conn, 
        user_id,
        ip_address,
        request_id,
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
    user_id: UUID | str = None,
    error_type: str | None = None
) -> Pagination[SystemLogResponse]:
    """
    Retrieves a paginated list of system logs, optionally filtered by level, user, or type.
    Uses a Window Function to fetch data and total count in a single database round-trip.
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
        
    params.extend([limit, offset])
            
    query = f"""
        SELECT 
            id, 
            user_id, 
            request_id,
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
            created_at,
            COUNT(*) OVER() AS total_count 
        FROM 
            system_logs
        {where_clause}
        ORDER BY 
            created_at DESC
        LIMIT 
            ${len(params) - 1} 
        OFFSET 
            ${len(params)};
    """
    
    try:
        return await db.fetch_pagination(query, SystemLogResponse, limit, offset, conn, *params)
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred while fetching system logs.",
            original_error=e,
            query=query,
            params=params,
            additional_context={"action": "get_logs"}
        )


async def get_log_by_id(log_id: UUID, conn: Connection) -> SystemLogResponse | None:
    """
    Retrieves a specific log entry by its UUID using the global connection pool.
    """
    return await db.fetchrow(LOG_GET_QUERY, SystemLogResponse, conn, log_id)


async def delete_log_by_id(log_id: UUID, conn: Connection) -> bool:
    row = await conn.fetchval(
        "DELETE FROM system_logs WHERE id = $1 RETURNING id;",
        log_id
    )
    return row is not None


async def delete_logs(days_to_keep: int, conn: Connection) -> int:
    """
    Deletes system logs older than the specified number of days and 
    returns the total number of deleted records.
    Executes in a single database round-trip.
    """
    query = """
        DELETE FROM 
            system_logs 
        WHERE 
            created_at < NOW() - make_interval(days => $1);
        """
    try:
        return await db.delete(query, conn, days_to_keep)
    except Exception as e:
        raise DatabaseException(
            client_message="An error occurred while cleaning up old system logs.",
            original_error=e,
            query="DELETE FROM system_logs",
            params=[days_to_keep],
            additional_context={
                "action": "delete_logs", 
                "days_to_keep": days_to_keep
            }
        )