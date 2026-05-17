from typing import Optional
from datetime import datetime
from fastapi import Cookie, Response
from src.exceptions import CREDENTIALS_EXCEPTION
from src.constants import Constants
from src.util import seconds_until
from src.security import jwt


def _get_cookie_security_settings() -> dict:
    """
    Internal helper to define cookie security flags based on the environment.
    Prevents code duplication across set and unset functions.
    """
    return {
        "secure": True if Constants.IS_PRODUCTION else False,
        "samesite": "none" if Constants.IS_PRODUCTION else "lax",
        "httponly": True,
        "path": "/"
    }


async def require_role(access_token: Optional[str] = Cookie(default=None), *roles: str) -> None:
    """
    Base dependency to verify if the current user has at least one of the required roles.
    """
    payload: dict = jwt.extract_jwt_token(access_token)
    
    role: Optional[str] = payload.get('role')
    if not role or role not in roles:
        raise CREDENTIALS_EXCEPTION


def require_admin_access(access_token: Optional[str] = Cookie(default=None)) -> None:
    """Dependency for admin-only routes."""
    require_role(access_token, "admin")
    

def require_moderator_access(access_token: Optional[str] = Cookie(default=None)) -> None:
    """Dependency for routes that allow either admins or moderators."""
    require_role(access_token, "admin", "moderator")


def set_session_cookie(
    response: Response, 
    access_token_jwt: str,
    access_token_expires_at: datetime,
    refresh_token_jwt: str,
    refresh_token_expires_at: datetime
):
    settings = _get_cookie_security_settings()    
    response.set_cookie(
        key="access_token",
        value=access_token_jwt,
        max_age=seconds_until(access_token_expires_at),
        **settings
    )
        
    response.set_cookie(
        key="refresh_token",
        value=refresh_token_jwt,
        max_age=seconds_until(refresh_token_expires_at),
        **settings
    )

    
def unset_session_cookie(response: Response):
    settings = _get_cookie_security_settings()
    response.delete_cookie(key="access_token", **settings)
    response.delete_cookie(key="refresh_token", **settings)