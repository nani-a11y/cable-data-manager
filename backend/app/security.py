from datetime import datetime, timedelta, timezone
import jwt
from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()
ALGORITHM = "HS256"

def hash_password(password: str) -> str:
    return password_hash.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)

def validate_admin_password(password: str) -> None:
    if not password or not password.strip():
        raise ValueError("Password must not be empty or whitespace-only.")
    pwd = password.strip()
    if len(pwd) < 12:
        raise ValueError(f"Password must be at least 12 characters long (provided {len(pwd)}).")
    if len(pwd) > 128:
        raise ValueError("Password must not exceed 128 characters.")

    known_insecure_passwords = {
        "insecure-default-password-replace-in-env",
        "admin12345678",
        "administrator",
        "cablemanager12",
        "password12345",
        "123456789012",
        "qwertyuiopas",
        "change_this_admin_password",
    }
    pwd_lower = pwd.lower()
    if (
        pwd_lower in known_insecure_passwords
        or "replace-in-env" in pwd_lower
        or "change_this" in pwd_lower
        or "admin123" in pwd_lower
        or "password123" in pwd_lower
    ):
        raise ValueError("Password is a known insecure default or placeholder.")

    if len(set(pwd)) < 4:
        raise ValueError("Password lacks sufficient character variety.")

def create_access_token(subject: str) -> str:
    from .config import settings

    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "exp": expires, "iat": datetime.now(timezone.utc)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    from .config import settings

    return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
