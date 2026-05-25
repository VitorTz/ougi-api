from src.schemas.login import LoginAttemptResponse
from src.schemas.pagination import Pagination
from src.exceptions import DatabaseException
from asyncpg import Connection
from datetime import datetime
from src import db


async def get_login_attempts_report(
    conn: Connection,
    limit: int = 50,
    offset: int = 0,
    identifier: str | None = None,
    ip_address: str | None = None,
    success: bool | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None
) -> Pagination[LoginAttemptResponse]:    
    conditions = []
    params = []
        
    if identifier:
        params.append(f"%{identifier}%")
        conditions.append(f"identifier ILIKE ${len(params)}")
        
    if ip_address:
        params.append(ip_address)
        conditions.append(f"ip_address = ${len(params)}::inet")
        
    if success is not None:
        params.append(success)
        conditions.append(f"success = ${len(params)}")
        
    if start_date:
        params.append(start_date)
        conditions.append(f"created_at >= ${len(params)}")
        
    if end_date:
        params.append(end_date)
        conditions.append(f"created_at <= ${len(params)}")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        
    params.extend([limit, offset])
    
    query = f"""
        SELECT 
            id, 
            identifier, 
            HOST(ip_address) AS ip_address, 
            success, 
            created_at,
            COUNT(*) OVER() AS total_count
        FROM 
            login_attempts
        {where_clause}
        ORDER BY 
            created_at DESC
        LIMIT 
            ${len(params) - 1} 
        OFFSET 
            ${len(params)};
    """
    
    try:
        return await db.fetch_pagination(
            query,
            LoginAttemptResponse,
            limit,
            offset,
            conn,
            *params
        )
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred while fetching the login attempts report.",
            original_error=e,
            query=query,
            params=params,
            additional_context={"action": "get_login_attempts_report"}
        )


async def insert_login_attempt(
    identifier: str,
    ip_address: str,
    success: bool,
    conn: Connection | None = None
) -> None:
    """
    Inserts a new login attempt record into the database to help 
    track brute force attacks and audit logins.
    Accepts an optional database connection to participate in existing transactions.
    """
    query = """
        INSERT INTO login_attempts (
            identifier, 
            ip_address, 
            success
        ) VALUES (
            TRIM($1), 
            $2::inet, 
            $3
        );
    """
    await db.execute(query, conn, identifier, ip_address, success)


async def insert_failed_login_attempt(identifier: str, ip_address: str, conn: Connection) -> None:
    """
    Records a failed login attempt for security tracking.
    """
    await insert_login_attempt(identifier, ip_address, False, conn)


async def insert_successful_login_attempt(identifier: str, ip_address: str, conn: Connection) -> None:
    """
    Records a successful login attempt.
    """
    await insert_login_attempt(identifier, ip_address, True, conn)


async def delete_old_login_attempts(hours_to_keep: int, conn: Connection) -> int:
    """
    Deletes login attempts older than the specified number of hours. 
    If hours_to_keep is 0, deletes all the records.
    Returns the total number of deleted records.
    """
    query = """
        DELETE FROM 
            login_attempts 
        WHERE 
            (created_at < NOW() - make_interval(hours => $1));
    """
    try:
        return await db.delete(query, conn, hours_to_keep)
    except Exception as e:
        raise DatabaseException(
            client_message="An error occurred while cleaning up old login attempts.",
            original_error=e,
            query="DELETE login_attempts",
            params=[hours_to_keep],
            additional_context={
                "action": "delete_old_login_attempts", 
                "hours_to_keep": hours_to_keep
            }
        )
    