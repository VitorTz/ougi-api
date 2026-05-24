from src.security.hashing import PasswordHasher, PasslibArgon2Hasher
from slowapi import Limiter
from src.util import extract_client_ip


_argon2_hasher = PasslibArgon2Hasher()
_limiter = Limiter(key_func=extract_client_ip)


def get_password_hasher() -> PasswordHasher:
    return _argon2_hasher


def get_limiter() -> Limiter:
    return _limiter
