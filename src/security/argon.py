from passlib.context import CryptContext
from typing import Optional


pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto"
)


def get_password_hash(password: str) -> Optional[str]:
    if not password: return None
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:    
    try:      
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False