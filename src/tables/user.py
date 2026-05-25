from src.exceptions import (
    DatabaseException, 
    DuplicateRecordError, 
    EmptyUpdateException,
    CredentialsException
)
from src.schemas.user import (
    UserPublicResponse, 
    UserCreate, 
    UserRole, 
    UserUpdate
)
from fastapi import Cookie, Depends
from asyncpg import Connection, UniqueViolationError
from src.schemas.pagination import Pagination
from src.schemas.device_info import DeviceInfo
from src.security import jwt_utils
from datetime import datetime
from typing import Optional
from src import util
from src import db


USER_PUBLIC_INFO_COLUMNS = """
    u.id,
    u.username,
    u.role,
    u.avatar_url,
    u.bio,
    u.banner_url,
    u.is_banned,
    u.last_seen_at,
    u.created_at
"""

USER_SENSITIVE_INFO_COLUMNS = """
    u.id,
    u.username,
    u.role,
    u.avatar_url,
    u.bio,
    u.banner_url,
    u.is_banned,
    u.last_seen_at,
    u.created_at,
    u.password_hash
"""


async def require_role(
    access_token: str | None,
    conn: Connection,
    *roles: str
):
    user_id: str | None = jwt_utils.extract_sub(access_token)
    role = await conn.fetchval(
        "SELECT role FROM users WHERE id = $1::uuid;",
        user_id
    )
    if not role or role not in roles: 
        raise CredentialsException()


async def require_admin_access(
    access_token: str | None = Cookie(default=None),
    conn: Connection = Depends(db.db_connection)
) -> str | None:
    """Dependency for admin-only routes."""
    await require_role(access_token, conn, 'admin')


async def require_moderator_access(
    access_token: str | None = Cookie(default=None),
    conn: Connection = Depends(db.db_connection)
) -> str | None:
    """Dependency for routes that allow either admins or moderators."""
    await require_role(access_token, conn, 'admin', 'moderator')


async def get_user_by_id(user_id: str, conn: Connection) -> Optional[UserPublicResponse]:
    query = f"""
        UPDATE
            users u
        SET
            last_seen_at = NOW()
        WHERE
            u.id = $1 
            AND u.is_active IS TRUE
        RETURNING
            {USER_PUBLIC_INFO_COLUMNS};
    """
    return await db.fetchrow(query, UserPublicResponse, conn, user_id)    


async def get_user_login_data(identifier: str, ip_address: str, conn: Connection) -> dict:
    """
    Retrieves sensitive user data and counts failed attempts based on IP.
    Always returns a dictionary containing 'recent_failed_attempts', even if the user does not exist,
    preventing enumeration attacks and Account Lockout DoS.
    """
    query = f"""
        WITH updated_user AS (
            UPDATE
                users u
            SET
                last_seen_at = NOW()
            WHERE
                (u.username = TRIM($1) OR u.email = TRIM($1))
                AND u.is_active = TRUE
                AND u.is_banned = FALSE
            RETURNING
                {USER_SENSITIVE_INFO_COLUMNS}
        ),
        attempt_count AS (
            SELECT 
                COUNT(id) AS recent_failed_attempts
            FROM 
                login_attempts
            WHERE 
                ip_address = $2::inet
                AND success = FALSE
                AND created_at >= NOW() - make_interval(mins => 15)
        )
        SELECT 
            up.*,
            ac.recent_failed_attempts
        FROM 
            attempt_count ac
        LEFT JOIN 
            updated_user up ON TRUE;
    """
    
    try:
        row = await conn.fetchrow(query, identifier, ip_address)        
        return dict(row)
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred while verifying your credentials.",
            original_error=e,
            query=query,
            params=[identifier, ip_address],
            additional_context={
                "action": "get_user_login_data", 
                "description": "Failed to fetch user and login attempts."
            }
        )


async def create_user(user: UserCreate, conn: Connection) -> None:
    query = """
        INSERT INTO users (
            username,
            email,
            password_hash,
            bio
        )
        VALUES
            (TRIM($1), TRIM($2), $3, TRIM($4))
    """
    try:
        await conn.execute(
            query,
            user.username,
            user.email,
            user.password,
            user.bio
        )
    except UniqueViolationError as e:
        constraint = getattr(e, 'constraint_name', '')        
        if constraint == "users_username_key":
            raise DuplicateRecordError("This username is already taken.")
        elif constraint == "users_email_key":
            raise DuplicateRecordError("This email is already registered.")
        else:
            raise DuplicateRecordError("The provided data conflicts with an existing record.")
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred while creating the account. Please try again later.",
            original_error=e,
            query="INSERT INTO users (Executed via repository layer)",
            params=user.model_dump(exclude={"password"}),
            additional_context={
                "action": "user_signup",
                "attempted_username": user.username,
                "attempted_email": user.email
            }
        )


async def update_role_user(user_id: str, role: UserRole, conn: Connection) -> bool:
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
        return await conn.fetchval(
            query,
            role.value,
            user_id
        ) is not None
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


async def ban_user(user_id: str, conn: Connection) -> bool:
    """
    Bans a user by setting their is_banned flag to TRUE.
    Returns True if the user was found and updated, False otherwise.
    """
    query = """
        UPDATE 
            users 
        SET
            is_banned = TRUE
        WHERE
            id = $1::uuid
        RETURNING 
            id;
    """
    try:
        return await conn.fetchval(query, user_id) is not None
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred while banning the user.",
            original_error=e,
            query=query,
            params=[user_id],
            additional_context={
                "action": "ban_user", 
                "user_id": str(user_id)
            }
        )


async def update_user(
    user_id: str, 
    payload: UserUpdate, 
    conn: Connection
) -> Optional[UserPublicResponse]:
    
    update_data = payload.model_dump(exclude_unset=True)
        
    if not update_data: 
        raise EmptyUpdateException()
    
    set_clauses = []
    params = []
    
    for i, (key, value) in enumerate(update_data.items(), start=1):
        set_clauses.append(f"{key} = ${i}")
        params.append(value)
            
    params.append(user_id)
    where_clause = f"WHERE id = ${len(params)}"
        
    query = f"""
        UPDATE 
            users 
        SET 
            {', '.join(set_clauses)}
        {where_clause}
        RETURNING 
            *;
    """
    
    try:
        return await db.fetchrow(query, UserPublicResponse, conn, *params)
    except UniqueViolationError as e:
        constraint = getattr(e, 'constraint_name', '')        
        if constraint == "users_username_key":
            raise DuplicateRecordError("This username is already taken.")
        elif constraint == "users_email_key":
            raise DuplicateRecordError("This email is already in use by another account.")
        else:
            raise DuplicateRecordError("The provided data conflicts with an existing record.")        
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred while updating your profile.",
            original_error=e,
            query=query,
            params=params,
            additional_context={
                "action": "user_update", 
                "user_id": str(user_id),
                "attempted_updates": list(update_data.keys())
            }
        )
    

async def get_users(
    conn: Connection,
    limit: int = 32, 
    offset: int = 0, 
    username: Optional[str] = None,
    role: Optional[str] = None,
    is_banned: Optional[bool] = None
) -> Pagination[UserPublicResponse]:
    """
    Fetches a paginated list of users from the database with dynamic filters.
    """    
    conditions = []
    params = []
        
    if username:
        params.append(f"%{username}%")
        conditions.append(f"u.username ILIKE ${len(params)}")
        
    if role:
        params.append(role)
        conditions.append(f"u.role = ${len(params)}")
        
    if is_banned is not None:
        params.append(is_banned)
        conditions.append(f"u.is_banned = ${len(params)}")    
        
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        
    params.extend([limit, offset])
        
    query = f"""
        SELECT 
            {USER_PUBLIC_INFO_COLUMNS},
            COUNT(*) OVER() AS total_count
        FROM 
            users u
        {where_clause}
        ORDER BY 
            u.created_at DESC
        LIMIT 
            ${len(params) - 1} 
        OFFSET 
            ${len(params)};
    """
        
    try:
        return await db.fetch_pagination(
            query,
            UserPublicResponse,
            limit,
            offset,
            conn,
            *params
        )
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred while fetching the user list.",
            original_error=e,
            query=query,
            params=params,
            additional_context={"action": "get_users"}
        )


async def delete_user(user_id: str, conn: Connection) -> None:
    await conn.execute("DELETE FROM users WHERE id = $1;", user_id)


async def rotate_session_and_get_user(
    new_token_id: str,
    user_id: str,
    expires_at: datetime,
    device_info: DeviceInfo,
    conn: Connection,
    old_token_id: str
) -> Optional[UserPublicResponse]:
    """
    Updates the user's last_seen_at, revokes the old refresh token, and inserts the new one.
    All operations are performed in a single atomic database round-trip.
    If the user does not exist or is inactive, no tokens are rotated and None is returned.
    """
    new_family_id = util.generate_uuid_v7()
    
    query = f"""
        WITH updated_user AS (
            UPDATE
                users u
            SET
                last_seen_at = NOW()
            WHERE
                u.id = $3::uuid
                AND u.is_active IS TRUE
            RETURNING
                {USER_PUBLIC_INFO_COLUMNS}
        ),
        get_old_family AS (
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
                AND EXISTS (SELECT 1 FROM updated_user) -- Garante que só revoga se o usuário for válido
        ),
        insert_new_token AS (
            INSERT INTO refresh_tokens (
                id,
                user_id,
                device_info,
                ip_address,
                expires_at,
                family_id
            )
            SELECT 
                $1::uuid,     
                $3::uuid,     
                $4,           
                $5::inet,     
                $6,           
                COALESCE((SELECT family_id FROM get_old_family), $7::uuid)
            WHERE EXISTS 
                (SELECT 1 FROM updated_user) 
        )
        SELECT 
            * 
        FROM 
            updated_user;
    """

    try:
        return await db.fetchrow(
            query, 
            UserPublicResponse, 
            conn, 
            new_token_id,
            old_token_id,
            user_id,
            device_info.device,
            device_info.ip_address,
            expires_at,
            new_family_id
        )
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
            },
            additional_context={"action": "rotate_session_and_get_user"},
            user_id=str(user_id),
        )