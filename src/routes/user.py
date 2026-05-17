from fastapi import APIRouter, Depends, Request, status, Cookie
from fastapi.exceptions import HTTPException
from src.schemas.user import UserUpdate, UserPublicResponse
from src.exceptions import DuplicateRecordError
from src.db import db_connection
from src.tables import user as user_table
from src.dependencies import get_limiter
from typing import Optional
from asyncpg import Connection
from src.security import jwt


router = APIRouter(
    prefix="/user", 
    tags=['user']
)
limiter = get_limiter()


@router.patch("", response_model=UserPublicResponse, status_code=status.HTTP_200_OK)
@limiter.limit("32/minute")
async def update_user(
    request: Request,
    payload: UserUpdate,
    access_token: Optional[str] = Cookie(default=None),
    conn: Connection = Depends(db_connection)
):
    user_id: str = jwt.extract_user_id_from_jwt_access_token(access_token)
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid or missing authentication token."
        )
    
    if not payload.model_dump(exclude_unset=True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid fields provided for update."
        )

    try:
        updated_user: UserPublicResponse | None = await user_table.update_user(
            user_id=user_id, 
            payload=payload,
            conn=conn
        )
    except DuplicateRecordError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message
        )
    
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account no longer exists."
        )
        
    return updated_user
