from asyncpg import Connection
from datetime import datetime
from typing import Optional
from src import db


async def process_token_rotation_bg(
    new_token_id: str,
    user_id: str,
    expires_at: datetime,
    new_family_id: str,
    old_family_id: Optional[str] = None,
    old_token_id: Optional[str] = None
):
    """
    Background worker that handles DB operations for tokens in a SINGLE round-trip.
    Utilizes PostgreSQL CTEs (WITH clause) to execute an UPDATE and an INSERT atomically.
    """
    pool = db.pool 
    
    query = """
        WITH revoke_old_family AS (
            UPDATE 
                refresh_tokens
            SET 
                revoked = TRUE,
                replaced_by = $1
            WHERE
                id = $2
                OR family_id = $3
        )
        INSERT INTO refresh_tokens (
            id, 
            user_id, 
            expires_at, 
            family_id
        )
        VALUES 
            ($4, $5, $6, $7);
    """
    
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                query,
                new_token_id,
                old_token_id,
                old_family_id,
                new_token_id,
                user_id,
                expires_at,
                new_family_id
            )
            
    except Exception as e:
        # log to Sentry/Datadog
        print(f"[BG_TASK_ERROR] Cosmic token rotation failed: {e}")


async def task_revoke_token_by_family(family_id: str) -> None:
    pool = db.pool
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                    UPDATE 
                        refresh_tokens
                    SET
                        revoked = TRUE
                    WHERE
                        family_id = $1;
                """,
                family_id
            )
    except Exception as e:
        # In production, log this to Sentry/Datadog
        print(f"[BG_TASK_ERROR] Cosmic token rotation failed: {e}")


async def revoke_all_other_sessions(user_id: str, current_family_id: str, conn: Connection) -> None:
    """
    The Panic Button. Severs all connections except the one the user is currently holding.
    """
    query = """
        UPDATE 
            refresh_tokens
        SET 
            revoked = TRUE
        WHERE 
            user_id = $1 
            AND family_id != $2
            AND revoked = FALSE;
    """
    await conn.execute(query, user_id, current_family_id)