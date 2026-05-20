from fastapi import (
    APIRouter, 
    Depends, 
    status, 
    Cookie, 
    Request, 
    BackgroundTasks
)
from src.exceptions import (
    ACCOUNT_NOT_FOUND_EXCEPTION,
    CREDENTIALS_EXCEPTION, 
    MAX_LOGIN_ATTEMPT_EXCEPTION,
    FORBIDDEN_EXCEPTION
)
from fastapi.responses import Response
from src.constants import Constants
from src.db import db_connection
from src.schemas.user import UserPublicResponse, UserCreate
from src.schemas.login import LoginIdentifier
from src.schemas.token import JWtTokenCreate
from src.schemas.device_info import DeviceInfo
from src.tables import user as users_table
from src.tables import tokens as tokens_table
from src.tables import login_attempts as login_attempts_table
from src.security import jwt_utils
from src.security import cookies
from src.security.hashing import PasswordHasher
from src.dependencies import get_password_hasher
from asyncpg import Connection
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
    user_id: str = jwt_utils.extract_value_from_token(access_token, "sub")
    user: UserPublicResponse | None = await users_table.get_user_by_id(user_id, conn)
    if not user: raise ACCOUNT_NOT_FOUND_EXCEPTION
    return user


@router.get("/pulse", status_code=status.HTTP_200_OK)
@limiter.limit("16/minute")
async def check_session_pulse(
    request: Request,
    access_token: str | None = Cookie(default=None),
    refresh_token: str | None = Cookie(default=None)
):
    return {
        "access_token_ttl": jwt_utils.calculate_token_ttl(access_token),
        "refresh_token_ttl": jwt_utils.calculate_token_ttl(refresh_token),
        "status": "active" if jwt_utils.calculate_token_ttl(refresh_token) > 0 else "expired"
    }


@router.post("/login", status_code=status.HTTP_200_OK, response_model=UserPublicResponse)
@limiter.limit("16/minute")
async def login(
    request: Request,
    identifier: LoginIdentifier,
    response: Response,
    background_tasks: BackgroundTasks,
    device_info: DeviceInfo = Depends(util.get_device_info),
    conn: Connection = Depends(db_connection),
    hasher: PasswordHasher = Depends(get_password_hasher),
    refresh_token: str | None = Cookie(default=None)
):
    user_login_data: dict | None = await users_table.get_user_login_data(identifier.identifier, conn)
    
    if not user_login_data:
        await login_attempts_table.insert_failed_login_attempt(
            identifier.identifier,
            device_info.ip_address,
            conn=conn
        )
        raise CREDENTIALS_EXCEPTION
        
    if user_login_data['recent_failed_attempts'] >= Constants.MAX_FAILED_LOGIN_ATTEMPTS:
        raise MAX_LOGIN_ATTEMPT_EXCEPTION
    
    if not hasher.verify_password(identifier.password, user_login_data['password_hash']):
        await login_attempts_table.insert_failed_login_attempt(
            identifier.identifier,
            device_info.ip_address,
            conn=conn
        )
        raise CREDENTIALS_EXCEPTION
    
    user = UserPublicResponse(**user_login_data)

    old_token_id: str | None = jwt_utils.extract_value_from_token_if_exists(refresh_token, "jti")
    new_token_id: str = util.generate_uuid_v7()
    new_access_token: JWtTokenCreate = jwt_utils.create_access_token(user.id, user.role)
    new_refresh_token: JWtTokenCreate = jwt_utils.create_jwt_refresh_token(user.id, new_token_id)

    await tokens_table.process_token_rotation(
        new_token_id,
        user.id,
        new_refresh_token.expires_at,
        device_info,
        conn,
        old_token_id
    )
    
    cookies.set_session_cookie(
        response, 
        new_access_token.jwt_token,
        new_access_token.expires_at,
        new_refresh_token.jwt_token,
        new_refresh_token.expires_at
    )

    background_tasks.add_task(
        login_attempts_table.insert_successful_login_attempt,
        identifier=identifier.identifier,
        ip_address=device_info.ip_address,
        success=True,
        conn=None
    )
    
    return user


@router.post("/signup", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("8/minute")
async def create_user(
    request: Request,
    payload: UserCreate,
    conn: Connection = Depends(db_connection)
):
    await users_table.create_user(payload, conn)


@router.post("/refresh", status_code=status.HTTP_200_OK, response_model=UserPublicResponse)
@limiter.limit("32/minute")
async def refresh(
    request: Request,
    response: Response,
    device: DeviceInfo = Depends(util.get_device_info),
    conn: Connection = Depends(db_connection),
    refresh_token: str | None = Cookie(default=None)
):
    jwt_data: dict =  jwt_utils.extract_token(refresh_token)
    user_id: str | None = jwt_data.get("sub")
    old_token_id: str | None = jwt_data.get("jti")

    if jwt_data.get("type") != "refresh" or not user_id or not old_token_id:
        raise CREDENTIALS_EXCEPTION    
        
    user: UserPublicResponse = await users_table.get_user_by_id(user_id, conn)

    new_token_id: str = util.generate_uuid_v7()
    new_access_token: JWtTokenCreate = jwt_utils.create_access_token(user_id, user.role)
    new_refresh_token: JWtTokenCreate = jwt_utils.create_jwt_refresh_token(user_id, new_token_id)

    await tokens_table.process_token_rotation(
        new_token_id,
        user_id,
        new_refresh_token.expires_at,
        device,
        conn,
        old_token_id
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
@limiter.limit("16/minute")
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
    token: dict = jwt_utils.extract_token(refresh_token)
    user_id: str = token.get("sub")
    token_id: str = token.get("jti")
    if not user_id or not token_id: return
    await tokens_table.revoke_token_family(token_id, user_id, conn)


@router.delete("/sessions/revoke-all", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("16/minute")
async def revoke_all_other_sessions(
    request: Request,
    response: Response,
    conn: Connection = Depends(db_connection),
    access_token: str | None = Cookie(default=None)
):
    cookies.unset_session_cookie(response)
    user_id: str = jwt_utils.extract_value_from_token(access_token, "sub")
    if not user_id: raise FORBIDDEN_EXCEPTION
    await tokens_table.revoke_all_user_sessions(user_id, conn)
    