from fastapi import Cookie, status
from fastapi.responses import Response
from fastapi.exceptions import HTTPException
from src.constants import Constants
from datetime import datetime
from src.util import seconds_until
from typing import Optional
from src.security import jwt


CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def require_admin_access(access_token: Optional[str] = Cookie(default=None)) -> None:
    jwt_token = jwt.extract_jwt_token(access_token)
    if jwt_token.get('role') != "admin":
        raise CREDENTIALS_EXCEPTION
    

async def require_moderator_access(access_token: Optional[str] = Cookie(default=None)) -> None:
    jwt_token = jwt.extract_jwt_token(access_token)
    if jwt_token.get('role') not in ("admin", "moderator"):
        raise CREDENTIALS_EXCEPTION


def set_session_token_cookie(
    response: Response, 
    access_token_jwt: str,
    access_token_expires_at: datetime,
    refresh_token_jwt: str,
    refresh_token_expires_at: datetime
):
    if Constants.IS_PRODUCTION:
        samesite_policy = "none"
        secure_policy = True
    else:
        samesite_policy = "lax"
        secure_policy = False
    
    # Cookie do Access Token (curta duração)
    response.set_cookie(
        key="access_token",
        value=access_token_jwt,
        httponly=True,
        secure=secure_policy,
        samesite=samesite_policy,
        path="/",
        max_age=seconds_until(access_token_expires_at)
    )
    
    # Cookie do Refresh Token (longa duração)
    response.set_cookie(
        key="refresh_token",
        value=refresh_token_jwt,
        httponly=True,
        secure=secure_policy,
        samesite=samesite_policy,
        path="/",
        max_age=seconds_until(refresh_token_expires_at)
    )

    
def unset_session_token_cookie(response: Response):
    if Constants.IS_PRODUCTION:
        samesite_policy = "none"
        secure_policy = True
    else:
        samesite_policy = "lax"
        secure_policy = False

    response.delete_cookie(
        key="access_token",
        httponly=True,
        path="/",
        samesite=samesite_policy,
        secure=secure_policy
    )

    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        path="/",
        samesite=samesite_policy,
        secure=secure_policy
    )
