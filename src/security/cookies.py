from typing import Optional
from datetime import datetime
from fastapi import Cookie, Response
from src.exceptions import CredentialsException
from src.constants import Constants
from src.util import seconds_until
from src.security import jwt_utils


COOKIE_SECURITY_SETTINGS = {
    "secure": True if Constants.IS_PRODUCTION else False,
    "samesite": "none" if Constants.IS_PRODUCTION else "lax",
    "httponly": True,
    "path": "/"
}


def require_role(access_token: Optional[str] = Cookie(default=None), *roles: str) -> None:
    """
    Base dependency to verify if the current user has at least one of the required roles.
    """
    role: str = jwt_utils.extract_value_from_jwt_token(access_token, 'role')

    if not role or role not in roles: raise CredentialsException()


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
    response.set_cookie(
        key="access_token",
        value=access_token_jwt,
        max_age=seconds_until(access_token_expires_at),
        **COOKIE_SECURITY_SETTINGS
    )
        
    response.set_cookie(
        key="refresh_token",
        value=refresh_token_jwt,
        max_age=seconds_until(refresh_token_expires_at),
        **COOKIE_SECURITY_SETTINGS
    )

    
def unset_session_cookie(response: Response):
    response.delete_cookie(key="access_token", **COOKIE_SECURITY_SETTINGS)
    response.delete_cookie(key="refresh_token", **COOKIE_SECURITY_SETTINGS)