from src.exceptions import DatabaseException
from asyncpg import Connection
from datetime import datetime
from typing import Optional


async def process_token_rotation(
    new_token_id: str,
    user_id: str,
    expires_at: datetime,
    new_family_id: str,
    conn: Connection,
    old_family_id: Optional[str] = None
):
    """
    Synchronously revokes the old token family and inserts the new refresh token.
    """
    query = """
        WITH revoke_old_family AS (
            UPDATE 
                refresh_tokens
            SET 
                revoked = TRUE,
                replaced_by = $1
            WHERE
                family_id = $2
        )
        INSERT INTO refresh_tokens (
            id, 
            user_id, 
            expires_at, 
            family_id
        )
        VALUES 
            ($1, $3, $4, $5);
    """

    sql_params = (
        new_token_id,
        old_family_id,
        user_id,
        expires_at,
        new_family_id
    )

    try:
        await conn.execute(query, *sql_params)            
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred during authentication. Please try logging in again.",
            original_error=e,
            query=query,
            params={
                "new_token_id": new_token_id,
                "old_family_id": old_family_id,
                "user_id": user_id,
                "expires_at": expires_at.isoformat() if expires_at else None, 
                "new_family_id": new_family_id
            },
            additional_context={
                "action": "process_token_rotation",
                "description": "Failed to safely rotate the refresh token family."
            },
            user_id=str(user_id)
        )
    

async def revoke_token_by_family(family_id: str, conn: Connection) -> None:
    """
    Synchronously revokes a refresh token family.
    """
    query = """
        UPDATE 
            refresh_tokens
        SET
            revoked = TRUE
        WHERE
            family_id = $1;
    """

    try:
        await conn.execute(query, family_id)
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred while processing your session. Please try again.",
            original_error=e,
            query=query,
            params={
                "family_id": family_id
            },
            additional_context={
                "action": "task_revoke_token_by_family",
                "description": "Failed to safely revoke token family. Security risk."
            }
        )


async def revoke_all_user_sessions(user_id: str, conn: Connection) -> None:
    """
    Revokes all active sessions for a user.
    """
    query = """
        UPDATE 
            refresh_tokens
        SET 
            revoked = TRUE
        WHERE 
            user_id = $1;
    """    
    try:
        await conn.execute(query, user_id)
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred while logging out of all devices. Please try again.",
            original_error=e,
            query=query,
            params={
                "user_id": user_id
            },
            additional_context={
                "action": "revoke_all_other_sessions",
                "description": "Failed to revoke all other user sessions. Potential security risk."
            },
            user_id=str(user_id)
        )
    

async def delete_expired_refresh_tokens(days_to_keep: int, conn: Connection) -> int:
    """
    Deletes refresh tokens that have been expired or revoked for longer than 
    the specified number of days. Active sessions are never touched.
    Returns the total number of deleted records.
    """    
    query = """
        DELETE FROM 
            refresh_tokens 
        WHERE 
            expires_at < NOW() - make_interval(days => $1)
            OR revoked_at < NOW() - make_interval(days => $1);
    """
    
    try:
        command_tag = await conn.execute(query, days_to_keep)        
        _, deleted_count = command_tag.split(" ")
        return int(deleted_count)
        
    except Exception as e:
        raise DatabaseException(
            client_message="An error occurred while cleaning up old refresh tokens.",
            original_error=e,
            query=query,
            params=[days_to_keep],
            additional_context={
                "action": "delete_expired_refresh_tokens", 
                "days_to_keep": days_to_keep
            }
        )