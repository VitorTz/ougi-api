from src.schemas.user import UserPublicResponse, UserCreate
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
                id = $1 AND is_active IS TRUE
        """,
        user_id
    )
    return UserPublicResponse(**row) if row else None


async def get_user_login_data(identifier: str, conn: Connection) -> dict:
    row = await conn.fetchrow(
        f"""
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
        """,
        identifier
    )
    
    return dict(row)


async def create_user(user: UserCreate, conn: Connection):
    await conn.execute(
        """
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
        """,
        user.username,
        user.email,
        user.password,
        user.avatar_url,
        user.bio,
        user.banner_url,
        user.is_adult
    )

