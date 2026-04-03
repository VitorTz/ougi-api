from fastapi import APIRouter, Depends, status, Cookie, BackgroundTasks
from fastapi.responses import Response
from fastapi.exceptions import HTTPException
from asyncpg import Connection
from src.db import db_connection
from src.schemas.user import UserPublicResponse, UserCreate
from src.schemas.login import LoginIdentifier
from src.schemas.token import AccessTokenCreate, RefreshTokenCreate
from src.tables import user as users_table
from src.tables import tokens as tokens_table
from src.security import jwt
from src.security import argon
from src.security import cookies
from typing import Optional
import asyncpg


router = APIRouter()


@router.get("/me", status_code=status.HTTP_200_OK, response_model=UserPublicResponse)
async def get_me(
    access_token: Optional[str] = Cookie(default=None),
    conn: Connection = Depends(db_connection)
):
    user_id: str = jwt.extract_user_id_from_jwt_access_token(access_token)
    user: Optional[UserPublicResponse] = await users_table.get_user_by_id(user_id, conn)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail='User not found'
        )
    return user


@router.get("/pulse", status_code=status.HTTP_200_OK)
async def check_session_pulse(
    access_token: Optional[str] = Cookie(default=None),
    refresh_token: Optional[str] = Cookie(default=None)
):
    """
    Retorna o tempo de vida restante (TTL) dos tokens em segundos.
    Útil para o Frontend decidir quando disparar o refresh silencioso.
    """
    return {
        "access_token_ttl": jwt.calculate_token_ttl(access_token),
        "refresh_token_ttl": jwt.calculate_token_ttl(refresh_token),
        "status": "active" if jwt.calculate_token_ttl(refresh_token) > 0 else "expired"
    }


@router.post("/login", status_code=status.HTTP_200_OK, response_model=UserPublicResponse)
async def login(
    identifier: LoginIdentifier,
    response: Response,
    background_tasks: BackgroundTasks,
    conn: Connection = Depends(db_connection),
    refresh_token: Optional[str] = Cookie(default=None)
):
    user_login_data = await users_table.get_user_login_data(identifier.username, conn)
    if (
        not user_login_data or
        not argon.verify_password(identifier.password, user_login_data['password_hash'])
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized"
        )
    
    user: UserPublicResponse = UserPublicResponse(**user_login_data)
    
    old_family_id = None
    if refresh_token:
        try:
            jwt_refresh_token: dict = jwt.extract_jwt_token(refresh_token)
            old_family_id = jwt_refresh_token.get('family_id')
        except Exception:
            pass
    
    new_access_token: AccessTokenCreate = jwt.create_jwt_access_token(user.id, user.role)
    new_refresh_token: RefreshTokenCreate = jwt.ceate_jwt_refresh_token(user.id)
    
    background_tasks.add_task(
        tokens_table.process_token_rotation_bg,
        old_family_id=old_family_id,
        new_token_id=new_refresh_token.token_id,
        user_id=user.id,
        expires_at=new_refresh_token.expires_at,
        new_family_id=new_refresh_token.family_id
    )
    
    cookies.set_session_token_cookie(
        response, 
        new_access_token.jwt_token,
        new_access_token.expires_at,
        new_refresh_token.jwt_token,
        new_refresh_token.expires_at
    )
    
    return user


@router.post("/signup", status_code=status.HTTP_204_NO_CONTENT)
async def create_user(payload: UserCreate, conn: Connection = Depends(db_connection)):
    try:
        users_table.create_user(payload, conn)
    except asyncpg.UniqueViolationError as e:
        if "users_username_key" in e.constraint_name:
            raise ValueError("This name is already in use.")
        raise e
    except Exception as e:
        print(f"[CRITICAL ERROR] {e}")
        # In production, log this to Sentry/Datadog
        raise e
    

@router.post("/refresh", status_code=status.HTTP_200_OK, response_model=UserPublicResponse)
async def refresh(
    response: Response,
    background_tasks: BackgroundTasks,
    conn: Connection = Depends(db_connection),
    refresh_token: Optional[str] = Cookie(default=None)
):
    token_data: dict = jwt.extract_jwt_token(refresh_token)
    if token_data.get('type') != 'refresh':
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized."
        )
    
    family_id: str = token_data.get('family_id')
    user_id: str = token_data.get('user_id')
    
    if not family_id or not user_id:        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized."
        )
        
    user: UserPublicResponse = await users_table.get_user_by_id(conn, user_id)
    new_access_token: AccessTokenCreate = jwt.create_jwt_access_token(user.id, user.role)
    new_refresh_token: RefreshTokenCreate = jwt.create_jwt_refresh_token(user.id, family_id)
    
    background_tasks.add_task(
        tokens_table.process_token_rotation_bg,
        old_family_id=family_id,
        new_token_id=new_refresh_token.token_id,
        user_id=user.id,
        expires_at=new_refresh_token.expires_at,
        new_family_id=family_id
    )
    
    cookies.set_session_token_cookie(
        response, 
        new_access_token.jwt_token,
        new_access_token.expires_at,
        new_refresh_token.jwt_token,
        new_refresh_token.expires_at
    )
    
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    background_tasks: BackgroundTasks,
    refresh_token: Optional[str] = Cookie(default=None)
):
    try:
        token_family_id: str = jwt.extract_jwt_refresh_token_family_id(refresh_token)    
    except Exception:
        pass
    else:
        background_tasks.add_task(
            tokens_table.task_revoke_token_by_family,
            family_id=token_family_id
        )
        
    cookies.unset_session_token_cookie(response)


@router.delete("/sessions/revoke-all", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_all_other_sessions(
    conn: Connection = Depends(db_connection),
    access_token: Optional[str] = Cookie(default=None),
    refresh_token: Optional[str] = Cookie(default=None)
):
    """
    The Panic Button. Cuts all tethers to the cosmos except the current one.
    """
    user_id: str = jwt.extract_user_id_from_jwt_access_token(access_token)
    
    current_family_id = None
    if refresh_token:
        try:
            token_data = jwt.extract_jwt_token(refresh_token)
            current_family_id = token_data.get('family_id')
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to verify current session integrity."
            )
            
    # Executed synchronously to guarantee the purge before responding
    await token_data.revoke_all_other_sessions(user_id, current_family_id, conn)
    return Response(status_code=status.HTTP_204_NO_CONTENT)