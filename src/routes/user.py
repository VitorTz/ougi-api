from src.exceptions import EmptyUpdateException, ResourceNotFoundException
from fastapi import APIRouter, Depends, Request, status, Cookie
from src.schemas.user import UserUpdate, UserPublicResponse
from src.db import db_connection
from src.tables import user as user_table
from src.dependencies import get_limiter
from typing import Optional
from asyncpg import Connection
from src.security import jwt_utils


router = APIRouter(
    prefix="/user", 
    tags=['user']
)
limiter = get_limiter()


@router.patch(
    "", 
    response_model=UserPublicResponse, 
    status_code=status.HTTP_200_OK,
    summary="Update User Profile",
    description="Updates the authenticated user's profile information. Only fields explicitly provided in the payload will be modified. Returns a 409 Conflict if attempting to change the username or email to one already in use."
)
@limiter.limit("32/minute")
async def update_user(
    request: Request,
    payload: UserUpdate,
    access_token: Optional[str] = Cookie(default=None),
    conn: Connection = Depends(db_connection)
):
    user_id: str = jwt_utils.extract_sub(access_token)
        
    if not payload.model_dump(exclude_unset=True):
        raise EmptyUpdateException()

    updated_user: Optional[UserPublicResponse] = await user_table.update_user(
        user_id=user_id, 
        payload=payload,
        conn=conn
    )
    
    if not updated_user:
        raise ResourceNotFoundException("User account")
        
    return updated_user