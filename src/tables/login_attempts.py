from src.exceptions import DatabaseException
from asyncpg import Connection
from src import db


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
    
    if conn is None:
        async with db.pool.acquire() as acquired_conn:
            await acquired_conn.execute(query, identifier, ip_address, success)
    else:
        await conn.execute(query, identifier, ip_address, success)


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
    If hours_to_keep is 0, truncates the entire table.
    Returns the total number of deleted records.
    """
    try:
        if hours_to_keep == 0:
            count = await conn.fetchval("SELECT COUNT(id) FROM login_attempts;")
            await conn.execute("TRUNCATE TABLE login_attempts;")
            return count
        else:
            query = "DELETE FROM login_attempts WHERE created_at < NOW() - make_interval(hours => $1);"            
            command_tag = await conn.execute(query, hours_to_keep)            
            _, deleted_count = command_tag.split(" ")
            return int(deleted_count)
    except Exception as e:
        raise DatabaseException(
            client_message="An error occurred while cleaning up old login attempts.",
            original_error=e,
            query="DELETE / TRUNCATE login_attempts",
            params=[hours_to_keep],
            additional_context={
                "action": "delete_old_login_attempts", 
                "hours_to_keep": hours_to_keep
            }
        )