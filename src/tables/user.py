from src.schemas.user import UserPublicResponse, UserCreate, UserRole
from src.exceptions import DatabaseException
from asyncpg import Connection
from typing import Optional


USER_COLUMNS = """
    u.id,
    u.username,
    u.role,
    u.avatar_url,
    u.bio,
    u.banner_url,
    u.is_banned,
    u.is_adult,
    u.last_seen_at,
    u.created_at
"""


async def get_user_by_id(user_id: str, conn: Connection) -> Optional[UserPublicResponse]:
    row = await conn.fetchrow(
        f"""
            SELECT
                {USER_COLUMNS}
            FROM
                users u
            WHERE
                id = $1 
                AND is_active IS TRUE
        """,
        user_id
    )
    return UserPublicResponse(**row) if row else None


async def get_user_login_data(identifier: str, conn: Connection) -> dict | None:
    query = f"""
        UPDATE
            users
        SET
            last_seen_at = NOW()
        WHERE
            (username = TRIM($1) OR email = TRIM($1))
            AND is_active = TRUE
            AND is_banned = FALSE
        RETURNING
            {USER_COLUMNS},
            password_hash;
    """
    row = await conn.fetchrow(query, identifier)
    if row: return dict(row)


async def create_user(user: UserCreate, conn: Connection):
    query = """
        INSERT INTO users (
            username,
            email,
            password_hash,
            avatar_url,
            bio,
            banner_url,
            is_adult
        )
        VALUES
            (TRIM($1), $2, $3, TRIM($4), $5, $6)
    """
    await conn.execute(
        query,
        user.username,
        user.email,
        user.password,
        user.avatar_url,
        user.bio,
        user.banner_url,
        user.is_adult
    )


async def set_role_to_user(user_id: str, role: UserRole, conn: Connection) -> bool:
    query = """
        UPDATE 
            users 
        SET        
            role = $1
        WHERE
            id = $2
        RETURNING 
            id;
    """
    try:
        row = await conn.fetchval(
            query,
            role.value,
            user_id
        )
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred while updating the user role.",
            original_error=e,
            query=query,
            params=[role.value, user_id],
            additional_context={
                "action": "set_role_to_user", 
                "user_id": str(user_id), 
                "role": role.value
            }
        )
    
    return row is not None


async def ban_user(user_id: str, conn: Connection) -> bool:
    query = """
        UPDATE 
            users 
        SET
            is_banned = TRUE
        WHERE
            id = $1
        RETURNING id;
    """
    try:
        row = await conn.fetchval(query, user_id)
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred while banning user.",
            original_error=e,
            query=query,
            params=[user_id],
            additional_context={
                "action": "ban_user", 
                "user_id": str(user_id)
            }
        )
    
    return row is not None