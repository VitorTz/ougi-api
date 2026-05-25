from datetime import datetime
from fastapi import Response
from src.constants import Constants
from src.util import seconds_until


COOKIE_SECURITY_SETTINGS = {
    "secure": True if Constants.IS_PRODUCTION else False,
    "samesite": "none" if Constants.IS_PRODUCTION else "lax",
    "httponly": True,
    "path": "/"
}


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