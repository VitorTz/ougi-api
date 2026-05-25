from src.security.hashing import PasswordHasher, PasslibArgon2Hasher
from slowapi import Limiter
from src.util import extract_client_ip


# Concrete implementation instance for Argon2 hashing
_argon2_hasher = PasslibArgon2Hasher()

# Limiter instance configured to identify clients by their real IP address
_limiter = Limiter(key_func=extract_client_ip)


def get_password_hasher() -> PasswordHasher:
    """
    Dependency provider that returns the concrete PasswordHasher implementation.
    This abstraction allows for easy switching of hashing algorithms or mocking 
    for unit tests without altering business logic.
    """
    return _argon2_hasher


def get_limiter() -> Limiter:
    """
    Dependency provider that returns the global Rate Limiter instance.
    Ensures consistent rate limiting policy across the entire API.
    """
    return _limiter