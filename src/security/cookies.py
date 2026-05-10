from src.exceptions import CREDENTIALS_EXCEPTION
from fastapi import Cookie
from fastapi.responses import Response
from src.constants import Constants
from datetime import datetime
from src.util import seconds_until
from typing import Optional
from src.security import jwt



async def require_role(access_token: Optional[str] = Cookie(default=None), *roles: str) -> None:
    jwt_token: dict = jwt.extract_jwt_token(access_token)
    role: str | None = jwt_token.get('role')
    if not role or role not in roles:
        raise CREDENTIALS_EXCEPTION


async def require_admin_access(access_token: Optional[str] = Cookie(default=None)) -> None:
    require_role(access_token, "admin")
    

async def require_moderator_access(access_token: Optional[str] = Cookie(default=None)) -> None:
    require_role(access_token, "admin", "moderator")


def set_session_cookie(
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

    
def unset_session_cookie(response: Response):
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
