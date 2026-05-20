from src.exceptions import DatabaseException
from src.schemas.device_info import DeviceInfo
from src.schemas.token import ActiveSessionResponse
from asyncpg import Connection
from datetime import datetime
from typing import Optional
from src import util


async def process_token_rotation(
    new_token_id: str,
    user_id: str,
    expires_at: datetime,
    device_info: DeviceInfo,
    conn: Connection,
    old_token_id: Optional[str] = None
):
    """
    Rotates a refresh token: revokes the previous token (if it exists) and inserts the new one.
    Automatically reuses the old token's family_id or generates a new one.
    Maintains the family chain to track token rotations and detect reuse.
    """
    new_family_id = util.generate_uuid_v7()
    
    query = """
        WITH get_old_family AS (
            SELECT 
                family_id 
            FROM 
                refresh_tokens
            WHERE 
                id = $2::uuid 
                AND user_id = $3::uuid
        ),
        revoke_old_token AS (
            UPDATE 
                refresh_tokens
            SET 
                revoked = TRUE,
                replaced_by = $1::uuid
            WHERE
                id = $2::uuid
                AND user_id = $3::uuid
        )
        INSERT INTO refresh_tokens (
            id,
            user_id,
            device_info,
            ip_address,
            expires_at,
            family_id
        )
        VALUES 
            (
                $1::uuid,     -- new_token_id
                $3::uuid,     -- user_id
                $4,           -- device_info.device
                $5::inet,     -- device_info.ip_address
                $6,           -- expires_at
                COALESCE((SELECT family_id FROM get_old_family), $7::uuid)
            );
    """
 
    sql_params = (
        new_token_id,
        old_token_id,
        user_id,
        device_info.device,
        device_info.ip_address,
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
                "old_token_id": old_token_id,
                "user_id": user_id,
                "expires_at": expires_at.isoformat(),
                "device_info": device_info.device,
                "ip_address": device_info.ip_address,
                "new_family_id": new_family_id,
            },
            additional_context={
                "action": "process_token_rotation",
                "description": "Failed to safely rotate the refresh token.",
            },
            user_id=str(user_id),
        )


async def revoke_token_family(token_id: str, user_id: str, conn: Connection) -> None:
    """
    Revokes an entire token family based on a single token_id.
    Uses a subquery to automatically resolve the family_id and apply the revocation.
    """
    query = """
        UPDATE 
            refresh_tokens
        SET
            revoked = TRUE
        WHERE
            family_id = (
                SELECT 
                    family_id 
                FROM 
                    refresh_tokens 
                WHERE 
                    id = $1::uuid 
                    AND user_id = $2::uuid
            )
            AND user_id = $2::uuid;
    """

    try:
        await conn.execute(query, token_id, user_id)
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred while processing your session. Please try again.",
            original_error=e,
            query=query,
            params={
                "token_id": token_id,
                "user_id": user_id,
            },
            additional_context={
                "action": "revoke_token_family",
                "description": "Failed to revoke token family based on token_id. Potential security risk.",
            },
            user_id=str(user_id),
        )


async def revoke_all_user_sessions(user_id: str, conn: Connection) -> None:
    """
    Revoga TODAS as sessões ativas do usuário em TODOS os dispositivos.
    Usado no logout completo (logout de todos os dispositivos).
    """
    query = """
        UPDATE 
            refresh_tokens
        SET 
            revoked = TRUE
        WHERE 
            user_id = $1
            AND revoked = FALSE;
    """    
    try:
        await conn.execute(query, user_id)
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred while logging out of all devices. Please try again.",
            original_error=e,
            query=query,
            params={
                "user_id": user_id,
            },
            additional_context={
                "action": "revoke_all_user_sessions",
                "description": "Failed to revoke all user sessions.",
            },
            user_id=str(user_id),
        )


async def revoke_device_session(user_id: str, device_info: str, conn: Connection) -> None:
    """
    Revoga a sessão de um dispositivo específico do usuário.
    Útil para logout em um dispositivo sem afetar outros.
    
    Args:
        user_id: UUID do usuário
        device_info: User-Agent resumido do dispositivo
        conn: Conexão asyncpg
    """
    query = """
        UPDATE 
            refresh_tokens
        SET 
            revoked = TRUE
        WHERE 
            user_id = $1
            AND device_info = $2
            AND revoked = FALSE;
    """
    
    try:
        await conn.execute(query, user_id, device_info)
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred while logging out of this device. Please try again.",
            original_error=e,
            query=query,
            params={
                "user_id": user_id,
                "device_info": device_info,
            },
            additional_context={
                "action": "revoke_device_session",
                "description": "Failed to revoke device session.",
            },
            user_id=str(user_id),
        )


async def delete_expired_refresh_tokens(days_to_keep: int, conn: Connection) -> int:
    """
    Deleta tokens que expiraram ou foram revogados há mais de X dias.
    Tokens ativos nunca são deletados.
    
    Returns:
        Número total de registros deletados.
    """    
    query = """
        DELETE FROM 
            refresh_tokens 
        WHERE 
            (expires_at < NOW() - make_interval(days => $1))
            OR (revoked = TRUE AND created_at < NOW() - make_interval(days => $1));
    """
    
    try:
        command_tag = await conn.execute(query, days_to_keep)
        _, deleted_count = command_tag.split()
        return int(deleted_count)
    except Exception as e:
        raise DatabaseException(
            client_message="An error occurred while cleaning up old sessions.",
            original_error=e,
            query=query,
            params={"days_to_keep": days_to_keep},
            additional_context={
                "action": "delete_expired_refresh_tokens",
                "days_to_keep": days_to_keep,
            },
        )


async def get_user_active_sessions(
    user_id: str, 
    current_family_id: str, 
    conn: Connection
) -> list[ActiveSessionResponse]:
    """
    Retrieves all active sessions for the user, hiding sensitive internal data.
    Flags the session that made the request as 'is_current_session'.
    """
    query = """
        SELECT 
            family_id AS session_id,
            device_info,
            ip_address,
            created_at,
            expires_at
        FROM 
            refresh_tokens
        WHERE 
            user_id = $1::uuid
            AND revoked = FALSE
            AND expires_at > NOW()
        ORDER BY 
            created_at DESC;
    """
    
    try:
        rows = await conn.fetch(query, user_id)
        
        sessions = []
        for row in rows:
            session_data = dict(row)            
            is_current = str(session_data["session_id"]) == str(current_family_id)
            session_data["is_current_session"] = is_current            
            sessions.append(ActiveSessionResponse(**session_data))

        return sessions
    except Exception as e:
        raise DatabaseException(
            client_message="An error occurred while fetching your active sessions.",
            original_error=e,
            query=query,
            params={
                "user_id": user_id, 
                "current_family_id": current_family_id
            },
            additional_context={
                "action": "get_user_active_sessions",
                "description": "Failed to retrieve active sessions from the database."
            },
            user_id=str(user_id),
        )