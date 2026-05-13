from datetime import datetime
from typing import Optional
from src.tables import logs as logs_table
from src import db
import traceback


async def process_token_rotation_bg(
    new_token_id: str,
    user_id: str,
    expires_at: datetime,
    new_family_id: str,
    old_family_id: Optional[str] = None,
    old_token_id: Optional[str] = None
):
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

    params = (
        new_token_id,
        old_token_id,
        old_family_id,
        new_token_id,
        user_id,
        expires_at,
        new_family_id
    )

    async with db.pool.acquire() as conn:
        try:
            await conn.execute(query, *params)            
        except Exception as e:
            tb_str = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            await logs_table.insert_log(
                error_type=type(e).__name__,
                error_message=str(e),
                error_level="CRITICAL",
                user_id=user_id,
                failed_query=query,
                query_parameters={
                    "new_token_id": new_token_id,
                    "old_token_id": old_token_id,
                    "old_family_id": old_family_id,
                    "user_id": user_id,
                    "expires_at": expires_at.isoformat() if expires_at else None, 
                    "new_family_id": new_family_id
                },
                execution_context={
                    "action": "process_token_rotation_bg",
                    "description": "Failed to rotate refresh token family in background task."
                },
                stack_trace=tb_str,
                conn=conn
            )


async def task_revoke_token_by_family(family_id: str) -> None:
    query = """
        UPDATE 
            refresh_tokens
        SET
            revoked = TRUE
        WHERE
            family_id = $1;
    """

    async with db.pool.acquire() as conn:
        try:
            await conn.execute(query, family_id)
        except Exception as e:
            tb_str = "".join(traceback.format_exception(type(e), e, e.__traceback__))        
            await logs_table.insert_log(
                error_type=type(e).__name__,
                error_message=str(e),
                error_level="CRITICAL",
                failed_query=query,
                query_parameters={
                    "family_id": family_id
                },
                execution_context={
                    "action": "task_revoke_token_by_family",
                    "description": "Failed to revoke token family in background task. Reusing connection for log."
                },
                stack_trace=tb_str,
                conn=conn
            )


async def revoke_all_other_sessions_bg(user_id: str, current_family_id: str) -> None:
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
    async with db.pool.acquire() as conn:
        try:
            await conn.execute(
                query,
                user_id,
                current_family_id
            )
        except Exception as e:
            tb_str = "".join(traceback.format_exception(type(e), e, e.__traceback__))        
            await logs_table.insert_log(
                error_type=type(e).__name__,
                error_message=str(e),
                error_level="CRITICAL",
                failed_query=query,
                user_id=user_id,
                query_parameters={
                    "current_family_id": current_family_id
                },
                execution_context={
                    "action": "task_revoke_all_other_sessions_bg",
                    "description": "Failed to revoke all user sessions in background task. Reusing connection for log."
                },
                stack_trace=tb_str,
                conn=conn
            )