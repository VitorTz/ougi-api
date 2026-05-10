from typing import Optional, Protocol
from passlib.context import CryptContext


class PasswordHasher(Protocol):

    def get_password_hash(self, password: str) -> Optional[str]:
        pass

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        pass


class PasslibArgon2Hasher:

    def __init__(self) -> None:
        self.pwd_context = CryptContext(
            schemes=["argon2"],
            deprecated="auto"
        )

    def get_password_hash(self, password: str) -> Optional[str]:
        if not password: return None
        return self.pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:    
        try:      
            return self.pwd_context.verify(plain_password, hashed_password)
        except Exception:
            return False


class PasslibBcryptHasher:

    def __init__(self) -> None:
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def get_password_hash(self, password: str) -> Optional[str]:
        if not password: return None
        return self.pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:    
        try:      
            return self.pwd_context.verify(plain_password, hashed_password)
        except Exception:
            return False