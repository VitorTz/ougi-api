from datetime import datetime, timezone, timedelta
from fastapi.exceptions import HTTPException
from typing import Optional, Any
from fastapi import status
from src.schemas.token import AccessTokenCreate, RefreshTokenCreate
from src.constants import Constants
from uuid import UUID
from src import util
import jwt



CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)
    
    
def create_jwt_access_token(user_id: UUID | str, role: str) -> AccessTokenCreate:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=Constants.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "exp": expires_at
    }
    
    jwt_token = jwt.encode(
        payload,
        Constants.SECRET_KEY,
        algorithm=Constants.ALGORITHM
    )
    
    return AccessTokenCreate(jwt_token=jwt_token, expires_at=expires_at)


def extract_jwt_token(jwt_token: str) -> dict[str, Any]:
    if not jwt_token: raise CREDENTIALS_EXCEPTION
    try:
        payload = jwt.decode(
            jwt_token,
            Constants.SECRET_KEY,
            algorithms=[Constants.ALGORITHM]
        )
    except Exception:
        raise CREDENTIALS_EXCEPTION
    if not payload:
        raise CREDENTIALS_EXCEPTION
    return payload
    
    
def extract_user_id_from_jwt_access_token(access_token: str) -> str:
    payload: dict = extract_jwt_token(access_token)    
        
    if payload.get("type") != "access":
        raise CREDENTIALS_EXCEPTION
    
    user_id = payload.get("sub")
            
    if not user_id:
        raise CREDENTIALS_EXCEPTION
    
    return user_id
    
    
def create_jwt_refresh_token(user_id: str, family_id: Optional[UUID] = None) -> RefreshTokenCreate:
    token_id = util.generate_cosmic_id()
    expires_at = datetime.now(timezone.utc) + timedelta(days=Constants.REFRESH_TOKEN_EXPIRE_DAYS)
    family_id = util.generate_cosmic_id() if not family_id else family_id
    
    payload = {
        "sub": str(token_id),
        "user_id": str(user_id),
        "family_id": str(family_id),
        "exp": expires_at,
        "type": "refresh"
    }
    
    jwt_token: str = jwt.encode(
        payload,
        Constants.SECRET_KEY,
        algorithm=Constants.ALGORITHM
    )
    
    return RefreshTokenCreate(
        token_id=token_id,
        expires_at=expires_at,
        family_id=family_id,
        replaced_by=None,
        jwt_token=jwt_token
    )
    
    
def extract_jwt_refresh_token_id(jwt_refresh_token: str) -> str:
    payload = extract_jwt_token(jwt_refresh_token)
    
    if payload.get("type") != "refresh":
        raise CREDENTIALS_EXCEPTION

    refresh_token_id: str = payload.get("sub")
            
    if not refresh_token_id:
        raise CREDENTIALS_EXCEPTION
    
    return refresh_token_id
    
    
def extract_jwt_refresh_token_family_id(jwt_refresh_token: str) -> str:
    payload = extract_jwt_token(jwt_refresh_token)
    
    if payload.get("type") != "refresh":
        raise CREDENTIALS_EXCEPTION

    family_id: str = payload.get("family_id")
            
    if not family_id:
        raise CREDENTIALS_EXCEPTION
    
    return family_id


def calculate_token_ttl(token: str | None) -> int:
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
        
    except Exception:
        return 0