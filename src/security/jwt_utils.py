from datetime import datetime, timezone, timedelta
from src.exceptions import CredentialsException
from src.schemas.token import JWtTokenCreate
from src.constants import Constants
from typing import Any
from uuid import UUID
import jwt


def create_token(**kwargs) -> JWtTokenCreate:
    """
    Base function to encode a JWT token and return the Pydantic schema.
    """
    jwt_token = jwt.encode(
        kwargs,
        Constants.SECRET_KEY,
        algorithm=Constants.ALGORITHM
    )

    return JWtTokenCreate(
        jwt_token=jwt_token, 
        expires_at=kwargs["exp"] 
    )
    

def create_access_token(user_id: str | UUID) -> JWtTokenCreate:
    """
    Creates a short-lived access token for the user.
    """
    return create_token(
        sub=str(user_id),
        type="access",
        exp=datetime.now(timezone.utc) + timedelta(minutes=Constants.ACCESS_TOKEN_EXPIRE_MINUTES)
    )


def create_refresh_token(user_id: str | UUID, token_id: str | UUID) -> JWtTokenCreate:    
    """
    Creates a long-lived refresh token for session rotation.
    """
    return create_token(
        sub=str(user_id),
        jti=str(token_id),
        exp=datetime.now(timezone.utc) + timedelta(days=Constants.REFRESH_TOKEN_EXPIRE_DAYS),
        type="refresh"
    )


def decode_token(jwt_token: str) -> dict[str, Any]:
    """
    Decodes and validates a JWT token, returning its payload.
    Throws CREDENTIALS_EXCEPTION if the token is missing, expired, or invalid.
    """
    if not jwt_token: 
        raise CredentialsException()
        
    try:
        return jwt.decode(
            jwt_token,
            Constants.SECRET_KEY,
            algorithms=[Constants.ALGORITHM]
        )
    except jwt.PyJWTError:
        raise CredentialsException()
    

def extract_value(token: str, key: str) -> str:
    """
    Strictly extracts a specific key from a token.
    Throws CREDENTIALS_EXCEPTION if the token is invalid or the key is missing.
    """
    payload: dict[str, Any] = decode_token(token)
    value = payload.get(key)
    
    if not value: 
        raise CredentialsException()
        
    return value


def extract_sub(token: str) -> str:
    return extract_value(token, "sub")
    

def extract_jti(token: str) -> str:
    return extract_value(token, "jti")


def extract_value_if_exists(token: str, key: str) -> str | None:
    """
    Safely attempts to extract a specific key from a token.
    Returns None if the token is invalid, expired, or the key is missing.
    """
    try:
        payload: dict[str, Any] = decode_token(token)
        return payload.get(key)
    except Exception:
        return None


def calculate_ttl(token: str | None) -> int:
    """
    Calculates the remaining Time-To-Live (TTL) of a token in seconds.
    Safely ignores the expiration check to read the 'exp' claim.
    """
    if not token:  
        return 0
    
    try:
        payload = jwt.decode(
            token,
            Constants.SECRET_KEY,
            algorithms=[Constants.ALGORITHM],
            options={"verify_exp": False}
        )
        
        exp_timestamp = payload.get("exp")
        if not exp_timestamp:
            return 0
            
        current_timestamp = datetime.now(timezone.utc).timestamp()
        remaining_seconds = int(exp_timestamp - current_timestamp)
        
        return max(0, remaining_seconds)
        
    except jwt.PyJWTError:
        return 0