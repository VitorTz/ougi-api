from fastapi import (
    APIRouter, 
    status, 
    Request, 
    Path, 
    Depends,
    Query,
    BackgroundTasks,
    Cookie
)
from src.schemas.user import UserPublicResponse, UserRole
from src.dependencies import get_limiter
from src.schemas.pagination import Pagination
from src.exceptions import ResourceNotFoundException
from src.tables import user as users_table
from src.tables import audit_log as audit_log_table
from asyncpg import Connection
from typing import Optional
from src.security import jwt_utils
from src import util
from src import db


router = APIRouter(prefix="/users")
limiter = get_limiter()


@router.get("", status_code=status.HTTP_200_OK, response_model=Pagination[UserPublicResponse])
@limiter.limit("32/minute")
async def list_users(
    request: Request,
    limit: int = Query(
        default=32, 
        ge=1, 
        le=64,
        title="Pagination Limit",
        description="Maximum number of users to return per page."
    ),
    offset: int = Query(
        default=0, 
        ge=0,
        title="Pagination Offset",
        description="Number of users to skip before starting to collect the result set."
    ),
    username: Optional[str] = Query(
        default=None, 
        title="Username Filter",
        description="Search for users by partial or exact username (case-insensitive)."
    ),
    role: Optional[str] = Query(
        default=None, 
        title="Role Filter",
        description="Filter the list by a specific user role (e.g., admin, moderator, user)."
    ),
    is_banned: Optional[bool] = Query(
        default=None, 
        title="Ban Status",
        description="Filter users by their current ban status (true for banned, false for active)."
    ),
    conn: Connection = Depends(db.db_connection)
):
    """
    Retrieves a paginated list of registered users.
    Supports dynamic filtering by username, role, and ban status.
    """
    return await users_table.get_users(
        limit=limit,
        offset=offset,
        conn=conn,
        username=username,
        role=role,
        is_banned=is_banned
    )


@router.get("/{user_id}", status_code=status.HTTP_200_OK, response_model=UserPublicResponse)
async def get_user(
    request: Request,
    user_id: str = Path(
        ...,
        title="User ID",
        description="The user unique UUID"
    ),
    conn: Connection = Depends(db.db_connection)
):
    user: UserPublicResponse | None = await users_table.get_user_by_id(user_id, conn)
    if not user: raise ResourceNotFoundException(f"User {user_id}")
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("32/minute")
async def delete_user(
    request: Request,
    user_id: str = Path(
        ...,
        title="User ID",
        description="The user unique UUID"
    ),
    conn: Connection = Depends(db.db_connection)
):
    await users_table.delete_user(user_id, conn)


@router.post("/{user_id}/role", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("32/minute")
async def update_user_role(
    request: Request,
    background_tasks: BackgroundTasks,
    user_id: str = Path(
        ...,
        title="User ID",
        description="The unique UUID of the user whose role is being updated."
    ),
    role: UserRole = Query(
        ...,
        title="New User Role",
        description="The new role to assign to the user (e.g., admin, moderator, user)."
    ),
    access_token: Optional[str] = Cookie(default=None),
    conn: Connection = Depends(db.db_connection)
):
    """
    Updates the role of a specific user. 
    Triggers a background task to record the action in the audit logs.
    """
    id_actor: str = jwt_utils.extract_sub(access_token)
    
    success: bool = await users_table.update_role_user(user_id, role, conn)
    
    if not success:
        raise ResourceNotFoundException("User")
    
    # Audit logging in background
    background_tasks.add_task(
        audit_log_table.insert_audit_log,
        action="update_user_role",
        table_name="users",
        record_id=str(user_id),
        actor_id=id_actor,
        ip_address=util.extract_client_ip(request)
    )