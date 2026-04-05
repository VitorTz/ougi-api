from src.schemas.log import SystemLogResponse
from typing import Optional, List, Dict, Any
from uuid import UUID
from src.db import pool 
import json


async def insert_log(
    error_type: str,
    error_message: str,
    error_level: str = "ERROR",
    user_id: Optional[UUID] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    request_method: Optional[str] = None,
    request_path: Optional[str] = None,
    failed_query: Optional[str] = None,
    query_parameters: Optional[Dict[str, Any]] = None,
    execution_context: Optional[Dict[str, Any]] = None,
    stack_trace: Optional[str] = None
) -> Optional[UUID]:
    """
    Inserts a new error log into the system_logs table using the global connection pool.
    Ideal for FastAPI BackgroundTasks since it acquires its own connection.
    """
    
    # Safely dump dictionaries to strings, or keep them as None
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
        )
        RETURNING id;
    """
    
    # Acquire a connection from the global pool automatically 
    # and release it back when the block exits.
    async with pool.acquire() as conn:
        log_id = await conn.fetchval(
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
        
    return log_id


async def get_logs(
    limit: int = 50,
    offset: int = 0,
    error_level: Optional[str] = None,
    user_id: Optional[UUID] = None,
    error_type: Optional[str] = None
) -> List[SystemLogResponse]:
    """
    Retrieves a paginated list of logs, optionally filtered by level, user, or type.
    Acquires its own connection from the global pool.
    """
    conditions = []
    params: List[Any] = []
    
    if error_level:
        params.append(error_level)
        conditions.append(f"error_level = ${len(params)}")
        
    if user_id:
        params.append(user_id)
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
        {where_clause}
        ORDER BY 
            created_at DESC
        LIMIT ${len(params) - 1} 
        OFFSET ${len(params)};
    """
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
    
    return [SystemLogResponse(**dict(row)) for row in rows]


async def get_log_by_id(log_id: UUID) -> Optional[SystemLogResponse]:
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
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, log_id)
    
    if row:
        return SystemLogResponse(**dict(row))
    return None