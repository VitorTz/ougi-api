from fastapi import APIRouter, Depends, status, Cookie, BackgroundTasks, Request
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
from src.exceptions import DatabaseException
from typing import Optional
from src.ratelimit import limiter
import asyncpg


router = APIRouter(prefix="/auth", tags=['auth'])


CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


@router.get("/me", status_code=status.HTTP_200_OK, response_model=UserPublicResponse)
@limiter.limit("16/minute")
async def get_me(
    request: Request,
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
@limiter.limit("16/minute")
async def check_session_pulse(
    request: Request,
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
@limiter.limit("5/minute")
async def login(
    request: Request,
    identifier: LoginIdentifier,
    response: Response,
    background_tasks: BackgroundTasks,
    conn: Connection = Depends(db_connection),
    refresh_token: Optional[str] = Cookie(default=None)
):
    user_login_data: Optional[dict] = await users_table.get_user_login_data(identifier.identifier, conn)
    if (
        not user_login_data or
        not argon.verify_password(identifier.password, user_login_data['password_hash'])
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized"
        )
    
    user: UserPublicResponse = UserPublicResponse(user_login_data)
    
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
@limiter.limit("5/minute")
async def create_user(
    request: Request, 
    payload: UserCreate, 
    conn: Connection = Depends(db_connection)
):
    try:
        await users_table.create_user(payload, conn)    
    except asyncpg.UniqueViolationError as e:
        constraint = getattr(e, 'constraint_name', '')        
        if constraint == "users_username_key":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This username is already taken."
            )
        elif constraint == "users_email_key":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is already registered."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The provided data conflicts with an existing record."
            )
    except Exception as e:
        raise DatabaseException(
            client_message="An unexpected error occurred while creating the account. Please try again later.",
            original_error=e,
            query="INSERT INTO users (Executed via repository layer)",
            params=payload.model_dump(exclude={"password"}),
            additional_context={
                "action": "user_signup",
                "attempted_username": payload.username,
                "attempted_email": payload.email
            }
        )
    

@router.post("/refresh", status_code=status.HTTP_200_OK, response_model=UserPublicResponse)
@limiter.limit("9/minute")
async def refresh(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    conn: Connection = Depends(db_connection),
    refresh_token: Optional[str] = Cookie(default=None)
):
    token_data: dict = jwt.extract_jwt_token(refresh_token)
    token_type: str = token_data.get('type')
    family_id: str = token_data.get('family_id')
    user_id: str = token_data.get('user_id')
    
    if token_type != 'refresh' or not family_id or not user_id:        
        raise CREDENTIALS_EXCEPTION
        
    user: UserPublicResponse = await users_table.get_user_by_id(user_id, conn)
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
@limiter.limit("5/minute")
async def logout(
    request: Request,
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
@limiter.limit("5/minute")
async def revoke_all_other_sessions(
    request: Request,
    conn: Connection = Depends(db_connection),
    access_token: Optional[str] = Cookie(default=None),
    refresh_token: Optional[str] = Cookie(default=None)
):
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