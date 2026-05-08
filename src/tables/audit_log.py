
from src.exceptions import DatabaseException
from typing import Optional, Any
from asyncpg import Connection
from src import db
import json


async def insert_audit_log(
    action: str,
    table_name: str,
    record_id: str,
    actor_id: Optional[str] = None,
    old_data: Optional[dict] = None,
    new_data: Optional[dict] = None,
    ip_address: Optional[str] = None
) -> None:
    """
    Inserts a new record into the audit_log table.
    Returns the UUID of the newly created log entry.
    """
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
        ) RETURNING id;
    """
    
    old_data_json = json.dumps(old_data) if old_data is not None else None
    new_data_json = json.dumps(new_data) if new_data is not None else None

    try:
        async with db.pool.acquire() as conn:
            await conn.execute(
                query,
                actor_id,
                action,
                table_name,
                record_id,
                old_data_json,
                new_data_json,
                ip_address
            )
    except Exception as e:
        raise DatabaseException(
            client_message="Failed to register audit log.",
            original_error=e,
            query=query,
            params=[
                actor_id, 
                action, 
                table_name, 
                record_id, 
                old_data_json, 
                new_data_json, 
                ip_address
            ],
            additional_context={
                "action": "insert_audit_log"
            }
        )
    

async def get_audit_logs(
    conn: Connection,
    limit: int = 50,
    offset: int = 0,
    action: Optional[str] = None,
    table_name: Optional[str] = None,
    actor_id: Optional[str] = None,
    record_id: Optional[str] = None
) -> list[dict]:
    conditions = []
    params: list[Any] = []
    
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
    
    # We cast JSONB to TEXT and INET to TEXT to safely parse them in Python
    query = f"""
        SELECT 
            id, actor_id, action, table_name, record_id, 
            old_data::TEXT as old_data, new_data::TEXT as new_data, 
            ip_address::TEXT as ip_address, created_at
        FROM 
            audit_log
        {where_clause}
        ORDER BY 
            created_at DESC
        LIMIT ${len(params) - 1} 
        OFFSET ${len(params)};
    """
    
    rows = await conn.fetch(query, *params)
    
    # Process rows to convert JSON strings back to Python dictionaries
    results = []
    for row in rows:
        row_dict = dict(row)
        if row_dict.get('old_data'):
            row_dict['old_data'] = json.loads(row_dict['old_data'])
        if row_dict.get('new_data'):
            row_dict['new_data'] = json.loads(row_dict['new_data'])
        results.append(row_dict)
        
    return results


async def get_audit_log_by_id(log_id: str, conn: Connection) -> Optional[dict]:
    query = """
        SELECT 
            id, actor_id, action, table_name, record_id, 
            old_data::TEXT as old_data, new_data::TEXT as new_data, 
            ip_address::TEXT as ip_address, created_at
        FROM 
            audit_log
        WHERE 
            id = $1;
    """
    row = await conn.fetchrow(query, log_id)
    
    if row:
        row_dict = dict(row)
        if row_dict.get('old_data'):
            row_dict['old_data'] = json.loads(row_dict['old_data'])
        if row_dict.get('new_data'):
            row_dict['new_data'] = json.loads(row_dict['new_data'])
        return row_dict
        
    return None


async def delete_audit_log_by_id(log_id: str, conn: Connection) -> bool:
    query = "DELETE FROM audit_log WHERE id = $1 RETURNING id;"
    deleted_id = await conn.fetchval(query, log_id)
    return deleted_id is not None


async def delete_old_audit_logs(days_to_keep: int, conn: Connection) -> None:
    if days_to_keep == 0:
        await conn.execute("TRUNCATE TABLE audit_log;")
    else:
        query = "DELETE FROM audit_log WHERE created_at < NOW() - make_interval(days => $1);"
        await conn.execute(query, days_to_keep)