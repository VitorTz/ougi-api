from fastapi import (
    APIRouter, 
    status, 
    Request, 
    Path, 
    Depends,
    Query    
)
from src.schemas.user import UserPublicResponse
from src.dependencies import get_limiter
from src.schemas.pagination import Pagination
from src.tables import user as users_table
from asyncpg import Connection
from typing import Optional
from src.db import db_connection


router = APIRouter()
limiter = get_limiter()


@router.get("/users", status_code=status.HTTP_200_OK, response_model=Pagination[UserPublicResponse])
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
    conn: Connection = Depends(db_connection)
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


@router.delete("/users", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("32/minute")
async def delete_user(
    request: Request,
    user_id: str = Path(
        ...,
        title="User ID",
        description="The unique UUID of the user whose role is being updated."
    ),
    conn: Connection = Depends(db_connection)
):
    await users_table.delete_user(user_id, conn)