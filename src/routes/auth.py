from asyncpg import Connection
from fastapi import APIRouter, Depends, status, Cookie, Request, BackgroundTasks
from fastapi.responses import Response
from src.constants import Constants
from fastapi.exceptions import HTTPException
from src.db import db_connection
from src.schemas.user import UserPublicResponse, UserCreate
from src.schemas.login import LoginIdentifier
from src.schemas.token import AccessTokenCreate, RefreshTokenCreate
from src.tables import user as users_table
from src.tables import tokens as tokens_table
from src.tables import login_attempts as login_attempts_table
from src.security import jwt
from src.security import cookies
from src.security.hashing import PasswordHasher
from src.dependencies import get_password_hasher
from src.exceptions import CREDENTIALS_EXCEPTION, DuplicateRecordError, DatabaseException
from src.dependencies import get_limiter
from src import util


router = APIRouter(prefix="/auth", tags=['auth'])
limiter = get_limiter()


@router.get("/me", status_code=status.HTTP_200_OK, response_model=UserPublicResponse)
@limiter.limit("16/minute")
async def get_me(
    request: Request,
    access_token: str | None = Cookie(default=None),
    conn: Connection = Depends(db_connection)
):
    user_id: str = jwt.extract_user_id_from_jwt_access_token(access_token)
    user: UserPublicResponse | None = await users_table.get_user_by_id(user_id, conn)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail='User account no longer exists or is invalid.'
        )
    return user


@router.get("/pulse", status_code=status.HTTP_200_OK)
@limiter.limit("16/minute")
async def check_session_pulse(
    request: Request,
    access_token: str | None = Cookie(default=None),
    refresh_token: str | None = Cookie(default=None)
):
    return {
        "access_token_ttl": jwt.calculate_token_ttl(access_token),
        "refresh_token_ttl": jwt.calculate_token_ttl(refresh_token),
        "status": "active" if jwt.calculate_token_ttl(refresh_token) > 0 else "expired"
    }


@router.post("/login", status_code=status.HTTP_200_OK, response_model=UserPublicResponse)
@limiter.limit("16/minute")
async def login(
    request: Request,
    identifier: LoginIdentifier,
    response: Response,
    background_tasks: BackgroundTasks,
    conn: Connection = Depends(db_connection),
    hasher: PasswordHasher = Depends(get_password_hasher),
    refresh_token: str | None = Cookie(default=None)
):
    user_login_data: dict | None = await users_table.get_user_login_data(identifier.identifier, conn)
    client_ip: str = util.get_real_client_ip(request)
    
    if not user_login_data:
        await login_attempts_table.insert_login_attempt(
            identifier=identifier.identifier,
            ip_address=client_ip,
            success=False,
            conn=conn
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
        
    if user_login_data['recent_failed_attempts'] >= Constants.MAX_FAILED_LOGIN_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again in 15 minutes."
        )
    
    if not hasher.verify_password(identifier.password, user_login_data['password_hash']):
        background_tasks.add_task(
            login_attempts_table.insert_login_attempt,
            identifier=identifier.identifier,
            ip_address=util.get_real_client_ip(request),
            success=False
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    
    user = UserPublicResponse(user_login_data)
    
    old_family_id = None
    if refresh_token:
        try:
            jwt_refresh_token: dict = jwt.extract_jwt_token(refresh_token)
            old_family_id = jwt_refresh_token.get('family_id')
        except Exception:
            pass
    
    new_access_token: AccessTokenCreate = jwt.create_jwt_access_token(user.id, user.role)
    new_refresh_token: RefreshTokenCreate = jwt.create_jwt_refresh_token(user.id)

    await tokens_table.process_token_rotation(
        new_refresh_token.token_id,
        user.id,
        new_refresh_token.expires_at,
        new_refresh_token.family_id,
        conn,
        old_family_id
    )
    
    cookies.set_session_cookie(
        response, 
        new_access_token.jwt_token,
        new_access_token.expires_at,
        new_refresh_token.jwt_token,
        new_refresh_token.expires_at
    )

    background_tasks.add_task(
        login_attempts_table.insert_login_attempt,
        identifier=identifier.identifier,
        ip_address=util.get_real_client_ip(request),
        success=True
    )
    
    return user


@router.post("/signup", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("8/minute")
async def create_user(
    request: Request,
    payload: UserCreate,
    conn: Connection = Depends(db_connection)
):
    try:
        await users_table.create_user(payload, conn)
    except DuplicateRecordError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message
        )

    

@router.post("/refresh", status_code=status.HTTP_200_OK, response_model=UserPublicResponse)
@limiter.limit("16/minute")
async def refresh(
    request: Request,
    response: Response,
    conn: Connection = Depends(db_connection),
    refresh_token: str | None = Cookie(default=None)
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

    await tokens_table.process_token_rotation(
        new_refresh_token.token_id,
        user.id,
        new_refresh_token.expires_at,
        new_refresh_token.family_id,
        conn,
        family_id
    )
    
    cookies.set_session_cookie(
        response, 
        new_access_token.jwt_token,
        new_access_token.expires_at,
        new_refresh_token.jwt_token,
        new_refresh_token.expires_at
    )
    
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("8/minute")
async def logout(
    request: Request,
    response: Response,
    conn: Connection = Depends(db_connection),
    refresh_token: str | None = Cookie(default=None)
):
    """
    Logs out the user by clearing local cookies and revoking the active 
    refresh token family in the database.
    """
    cookies.unset_session_cookie(response)        
    if not refresh_token: return

    try:
        token_family_id: str = jwt.extract_jwt_refresh_token_family_id(refresh_token)
        await tokens_table.task_revoke_token_by_family(token_family_id, conn)
    except CREDENTIALS_EXCEPTION:
        pass
    except DatabaseException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.client_message
        )        
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during logout."
        )


@router.delete("/sessions/revoke-all", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("8/minute")
async def revoke_all_other_sessions(
    request: Request,
    response: Response,
    conn: Connection = Depends(db_connection),
    access_token: str | None = Cookie(default=None)
):
    cookies.unset_session_cookie(response)
    user_id: str = jwt.extract_user_id_from_jwt_access_token(access_token)    

    if not user_id:
        raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to verify current session integrity."
            )

    await tokens_table.revoke_all_user_sessions(user_id, conn)
    