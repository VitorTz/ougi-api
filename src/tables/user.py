from src.schemas.user import UserPublicResponse, UserCreate, UserRole, UserUpdate
from src.exceptions import DatabaseException, DuplicateRecordError
from asyncpg import Connection, UniqueViolationError
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
            UPDATE
                users u
            SET
                u.last_seen_at = NOW()
            WHERE
                u.id = $1 
                AND u.is_active IS TRUE
            RETURNING
                {USER_COLUMNS};
        """,
        user_id
    )
    return UserPublicResponse(row) if row else None


async def get_user_login_data(identifier: str, conn: Connection) -> dict | None:
    query = f"""
        UPDATE
            users u
        SET
            u.last_seen_at = NOW()
        WHERE
            (u.username = TRIM($1) OR u.email = TRIM($1))
            AND u.is_active = TRUE
            AND u.is_banned = FALSE
        RETURNING
            {USER_COLUMNS},
            u.password_hash;
    """
    row = await conn.fetchrow(query, identifier)
    if row: return dict(row)


async def user_create(user: UserCreate, conn: Connection):
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
    try:
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


async def user_update(
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