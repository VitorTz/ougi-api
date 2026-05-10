from src.security.hashing import PasswordHasher, PasslibArgon2Hasher


_argon2_hasher = PasslibArgon2Hasher()


def get_password_hasher() -> PasswordHasher:
    return _argon2_hasher