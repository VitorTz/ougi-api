from src.schemas.user import UserPublicResponse, UserCreate, UserRole, UserUpdate
from src.schemas.pagination import Pagination
from src.exceptions import DatabaseException, DuplicateRecordError
from asyncpg import Connection, UniqueViolationError
from typing import Optional


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


async def get_user_by_id(user_id: str, conn: Connection) -> Optional[UserPublicResponse]:
    row = await conn.fetchrow(
        f"""
            UPDATE
                users u
            SET
                u.last_seen_at = NOW()
            WHERE
                u.id = $1 
                AND u.is_active IS TRUE
            RETURNING
                {USER_PUBLIC_INFO_COLUMNS};
        """,
        user_id
    )
    return UserPublicResponse(row) if row else None


async def get_user_login_data(identifier: str, conn: Connection) -> Optional[dict]:
    """
    Retrieves user sensitive data for login and counts recent failed login attempts 
    using a Common Table Expression (CTE) to perform both actions in a single query.
    """
    query = f"""
        WITH updated_user AS (
            UPDATE
                users
            SET
                last_seen_at = NOW()
            WHERE
                (username = TRIM($1) OR email = TRIM($1))
                AND is_active = TRUE
                AND is_banned = FALSE
            RETURNING
                {USER_SENSITIVE_INFO_COLUMNS}
        )
        SELECT 
            u.*,
            (
                SELECT 
                    COUNT(id)
                FROM 
                    login_attempts
                WHERE 
                    identifier = TRIM($1)
                    AND success = FALSE
                    AND created_at >= NOW() - make_interval(mins => 15)
            ) AS recent_failed_attempts
        FROM 
            updated_user u;
    """
    
    try:
        row = await conn.fetchrow(query, identifier)
        return dict(row) if row else None
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred while verifying your credentials.",
            original_error=e,
            query=query,
            params=[identifier],
            additional_context={
                "action": "get_user_login_data", 
                "description": "Failed to fetch user and login attempts."
            }
        )

async def create_user(user: UserCreate, conn: Connection):
    query = """
        INSERT INTO users (
            username,
            email,
            password_hash,
            bio
        )
        VALUES
            (TRIM($1), TRIM($2), $3, TRIM($4), $5)
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
        row = await conn.fetchval(
            query,
            role.value,
            user_id
        )
        return row is not None
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
    query = """
        UPDATE 
            users 
        SET
            is_banned = TRUE
        WHERE
            id = $1
        RETURNING 
            id;
    """
    try:
        row = await conn.fetchval(query, user_id)
        return row is not None
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


async def update_user(
    user_id: str, 
    payload: UserUpdate, 
    conn: Connection
) -> Optional[UserPublicResponse]:
    
    update_data = payload.model_dump(exclude_unset=True)
        
    if not update_data: 
        return None
    
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
        row = await conn.fetchrow(query, *params)        
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

    return UserPublicResponse(**row) if row else None


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
    
    # 1. Build the dynamic filters
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
        
    count_query = f"SELECT COUNT(u.id) FROM users u {where_clause};"
    
    fetch_params = params.copy()
    fetch_params.extend([limit, offset])
    
    fetch_query = f"""
        SELECT 
            {USER_PUBLIC_INFO_COLUMNS}
        FROM 
            users u
        {where_clause}
        ORDER BY 
            u.created_at DESC
        LIMIT 
            ${len(fetch_params) - 1} 
        OFFSET 
            ${len(fetch_params)};
    """
        
    try:
        total_items = await conn.fetchval(count_query, *params)
        
        if total_items == 0:
            return Pagination(
                items=[], 
                total_items=0, 
                limit=limit, 
                offset=offset
            )        
            
        rows = await conn.fetch(fetch_query, *fetch_params)        
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred while fetching the user list.",
            original_error=e,
            query=fetch_query,
            params=fetch_params,
            additional_context={"action": "get_users"}
        )
    
    parsed_items: list[UserPublicResponse] = [
        UserPublicResponse(**dict(row)) for row in rows
    ]
        
    return Pagination(
        items=parsed_items,
        total_items=total_items,
        limit=limit,
        offset=offset
    )