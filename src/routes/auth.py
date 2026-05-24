from fastapi import (
    APIRouter, 
    Depends, 
    status, 
    Cookie, 
    Request, 
    BackgroundTasks
)
from src.exceptions import (
    CredentialsException,
    MaxLoginAttemptException,
    AccountNotFoundException    
)
from fastapi.responses import Response
from src.constants import Constants
from src.db import db_connection
from src.schemas.user import UserPublicResponse, UserCreate
from src.schemas.login import LoginIdentifier
from src.schemas.token import JWtTokenCreate
from src.schemas.device_info import DeviceInfo
from src.schemas.session_pulse import SessionPulseResponse
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


@router.get(
    "/me", 
    status_code=status.HTTP_200_OK, 
    response_model=UserPublicResponse,
    summary="Get current user profile",
    description="Retrieves the profile information of the currently authenticated user based on the access token stored in the cookies. Returns a 401 Unauthorized error if the token is invalid or the account no longer exists."
)
@limiter.limit("16/minute")
async def get_me(
    request: Request,
    access_token: str | None = Cookie(default=None),
    conn: Connection = Depends(db_connection)
):
    user_id: str = jwt_utils.extract_value_from_jwt_token(access_token, "sub")
    user: UserPublicResponse | None = await users_table.get_user_by_id(user_id, conn)
    
    if not user: 
        raise AccountNotFoundException()
        
    return user


@router.get(
    "/pulse", 
    status_code=status.HTTP_200_OK,
    response_model=SessionPulseResponse,
    summary="Check session time-to-live",
    description="Returns the remaining TTL (in seconds) for both access and refresh tokens stored in cookies."
)
@limiter.limit("16/minute")
async def check_session_pulse(
    request: Request,
    access_token: str | None = Cookie(default=None),
    refresh_token: str | None = Cookie(default=None)
) -> SessionPulseResponse:
    access_ttl: int = jwt_utils.calculate_jwt_token_ttl(access_token)
    refresh_ttl: int = jwt_utils.calculate_jwt_token_ttl(refresh_token)    
    session_status = "active" if refresh_ttl > 0 else "expired"    
    return SessionPulseResponse(
        access_token_ttl=access_ttl,
        refresh_token_ttl=refresh_ttl,
        status=session_status
    )


@router.post(
    "/login", 
    status_code=status.HTTP_200_OK, 
    response_model=UserPublicResponse,
    summary="User Login",
    description="Authenticates a user via email or username. Includes built-in brute-force protection, rotates the session token family, and injects secure HTTP-only cookies."
)
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
    user_login_data: dict = await users_table.get_user_login_data(identifier.identifier, conn)
         
    # 1. Check for brute-force locks BEFORE hashing the password (Prevents CPU DoS)
    if user_login_data['recent_failed_attempts'] >= Constants.MAX_FAILED_LOGIN_ATTEMPTS:
        raise MaxLoginAttemptException()
    
    # 2. Verify Password
    if not user_login_data.get('id') or not hasher.verify_password(identifier.password, user_login_data['password_hash']):
        await login_attempts_table.insert_failed_login_attempt(
            identifier.identifier,
            device_info.ip_address,
            conn
        )
        raise CredentialsException()
    
    # 3. Parse user response model
    user = UserPublicResponse(**user_login_data)

    # 4. Token Rotation
    old_token_id: str | None = jwt_utils.extract_value_from_jwt_token_if_exists(refresh_token, "jti")
    new_token_id: str = util.generate_uuid_v7()
    
    new_access_token: JWtTokenCreate = jwt_utils.create_jwt_access_token(user.id, user.role)
    new_refresh_token: JWtTokenCreate = jwt_utils.create_jwt_refresh_token(user.id, new_token_id)

    # Must be awaited directly (synchronous) to guarantee the session exists in DB before sending 200 OK
    await tokens_table.process_token_rotation(
        new_token_id,
        user.id,
        new_refresh_token.expires_at,
        device_info,
        conn,
        old_token_id
    )
    
    # 5. Apply cookies
    cookies.set_session_cookie(
        response, 
        new_access_token.jwt_token,
        new_access_token.expires_at,
        new_refresh_token.jwt_token,
        new_refresh_token.expires_at
    )

    # 6. Log the successful attempt in the background
    background_tasks.add_task(
        login_attempts_table.insert_successful_login_attempt,
        identifier=identifier.identifier,
        ip_address=device_info.ip_address,
        conn=None # Background task will acquire its own connection from the pool
    )
    
    return user


@router.post(
    "/signup", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="User Signup",
    description="Registers a new user account in the system. It safely handles unique constraint validations (such as duplicate emails or usernames) and returns a 409 Conflict if the data is already in use."
)
@limiter.limit("8/minute")
async def create_user(
    request: Request,
    payload: UserCreate,
    conn: Connection = Depends(db_connection)
):
    await users_table.create_user(payload, conn)


@router.post(
    "/refresh", 
    status_code=status.HTTP_200_OK, 
    response_model=UserPublicResponse,
    summary="Refresh Session Tokens",
    description="Validates the user's current refresh token, securely rotates the token family in the database, and sets new HTTP-only cookies for continuous authentication."
)
@limiter.limit("32/minute")
async def refresh(
    request: Request,
    response: Response,
    device: DeviceInfo = Depends(util.get_device_info),
    conn: Connection = Depends(db_connection),
    refresh_token: str | None = Cookie(default=None)
):
    # 1. Extract and mathematically validate the token
    jwt_data: dict = jwt_utils.extract_jwt_token(refresh_token)
    user_id: str | None = jwt_data.get("sub")
    old_token_id: str | None = jwt_data.get("jti")

    # 2. Prevent logical tampering (e.g. using an access token to refresh)
    if jwt_data.get("type") != "refresh" or not user_id or not old_token_id:
        raise CredentialsException()    
        
    # 3. Ensure the user still exists in the database and is not banned
    user: UserPublicResponse | None = await users_table.get_user_by_id(user_id, conn)
    if not user:
        raise AccountNotFoundException()

    # 4. Generate new tokens
    new_token_id: str = util.generate_uuid_v7()
    new_access_token: JWtTokenCreate = jwt_utils.create_jwt_access_token(user_id, user.role)
    new_refresh_token: JWtTokenCreate = jwt_utils.create_jwt_refresh_token(user_id, new_token_id)

    # 5. Process Database Rotation (Synchronous, blocking call for safety)
    await tokens_table.process_token_rotation(
        new_token_id,
        user_id,
        new_refresh_token.expires_at,
        device,
        conn,
        old_token_id
    )
    
    # 6. Apply new secure cookies
    cookies.set_session_cookie(
        response, 
        new_access_token.jwt_token,
        new_access_token.expires_at,
        new_refresh_token.jwt_token,
        new_refresh_token.expires_at
    )
    
    return user


@router.post(
    "/logout", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="User Logout",
    description="Logs out the user by immediately clearing local session cookies. If a valid refresh token is provided, it securely revokes the entire token family in the database to prevent session hijacking."
)
@limiter.limit("16/minute")
async def logout(
    request: Request,
    response: Response,
    conn: Connection = Depends(db_connection),
    refresh_token: str | None = Cookie(default=None)
):
    cookies.unset_session_cookie(response)
    try:
        token: dict = jwt_utils.extract_jwt_token(refresh_token)
        user_id: str | None = token.get("sub")
        token_id: str | None = token.get("jti")
                
        if user_id and token_id:
            await tokens_table.revoke_token_family(token_id, user_id, conn)
            
    except CredentialsException:
        pass


@router.delete(
    "/sessions/revoke-all", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout of all devices",
    description="Logs the user out globally. It clears the local session cookies immediately and safely revokes every active refresh token family associated with this user's account in the database."
)
@limiter.limit("16/minute")
async def revoke_all_sessions(
    request: Request,
    response: Response,
    conn: Connection = Depends(db_connection),
    access_token: str | None = Cookie(default=None)
):
    cookies.unset_session_cookie(response)    
    try:
        user_id: str = jwt_utils.extract_value_from_jwt_token(access_token, "sub")
        await tokens_table.revoke_all_user_sessions(user_id, conn)    
    except CredentialsException:
        pass
    