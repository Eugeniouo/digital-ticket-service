from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from query_service.database.models.staff import StaffRole
from query_service.settings import settings

_password_hash = PasswordHash.recommended()

JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _password_hash.hash(password.strip())


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password.strip(), password_hash)


def create_access_token(
    staff_id: UUID,
    role: StaffRole,
    department_id: UUID | None,
) -> str:
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET is not set")

    now = datetime.now(UTC)
    payload = {
        "sub": str(staff_id),
        "role": role.value,
        "department_id": str(department_id) if department_id is not None else None,
        "iat": now,
        "exp": now + timedelta(seconds=settings.jwt_ttl_seconds),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, object]:
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET is not set")

    return jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
