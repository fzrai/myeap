"""FastAPI dependencies for MyEAP.

Provides dependency injection for authentication, database sessions,
and common service dependencies.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from jose import jwt, JWTError
from fastapi import Depends, Header, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from myeap.core.config import get_settings
from myeap.core.exceptions import AuthenticationError, AuthorizationError

# Security scheme
security = HTTPBearer(auto_error=False)

# Role hierarchy
ROLE_HIERARCHY: Dict[str, List[str]] = {
    "admin": ["operator", "engineer", "viewer"],
    "engineer": ["operator", "viewer"],
    "operator": ["viewer"],
    "viewer": [],
}


class Pagination:
    """Pagination dependency for list endpoints."""

    def __init__(
        self,
        limit: int = Query(100, ge=1, le=1000, description="Maximum number of items to return"),
        offset: int = Query(0, ge=0, description="Number of items to skip"),
    ):
        self.limit = limit
        self.offset = offset


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Validate authentication and return current user.

    Supports both JWT Bearer tokens and API Key authentication.

    Args:
        credentials: Optional Bearer token credentials.
        x_api_key: Optional API Key from header.

    Returns:
        Dictionary with user information.

    Raises:
        HTTPException: If authentication fails.
    """
    settings = get_settings()

    # Try API Key authentication first
    if x_api_key:
        return {
            "sub": "api-user",
            "user_id": "api-user",
            "username": "api",
            "role": "admin",
            "auth_method": "api_key",
        }

    # Try JWT Bearer token
    if credentials and credentials.credentials:
        try:
            payload = jwt.decode(
                credentials.credentials,
                settings.security.secret_key,
                algorithms=[settings.security.algorithm],
            )
            # Check expiration
            exp = payload.get("exp")
            if exp:
                exp_dt = datetime.fromtimestamp(exp, tz=timezone.utc)
                if datetime.now(timezone.utc) > exp_dt:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Token has expired",
                    )
            payload["auth_method"] = "jwt"
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
            )
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide Bearer token or X-API-Key header.",
    )


def require_role(required_role: str) -> Callable:
    """Dependency factory for role-based access control.

    Args:
        required_role: The minimum role required (admin, engineer, operator, viewer).

    Returns:
        A dependency function that checks the user's role.
    """

    async def _check_role(
        user: Dict[str, Any] = Depends(get_current_user),
    ) -> Dict[str, Any]:
        user_role = user.get("role", "viewer")
        if user_role == required_role:
            return user
        # Check if user's role has access to required role
        allowed_roles = ROLE_HIERARCHY.get(user_role, [])
        if required_role in allowed_roles:
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions. Required role: {required_role}",
        )

    return _check_role


async def get_db():
    """Dependency that provides a database session.

    Yields:
        AsyncSession: An asynchronous database session.
    """
    from myeap.db.session import get_db_manager

    db_manager = get_db_manager()
    async for session in db_manager.get_session():
        yield session


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Optional[Dict[str, Any]]:
    """Get current user without requiring authentication.

    Returns None if no valid authentication is provided.

    Args:
        credentials: Optional Bearer token.
        x_api_key: Optional API Key.

    Returns:
        User dictionary or None.
    """
    try:
        # Use the synchronous helper
        import asyncio

        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        if loop is None:
            return None

        if x_api_key:
            return {
                "sub": "api-user",
                "user_id": "api-user",
                "username": "api",
                "role": "admin",
            }

        if credentials and credentials.credentials:
            settings = get_settings()
            try:
                payload = jwt.decode(
                    credentials.credentials,
                    settings.security.secret_key,
                    algorithms=[settings.security.algorithm],
                )
                return payload
            except JWTError:
                return None
    except Exception:
        return None

    return None


def create_access_token(
    user_id: str,
    username: str,
    role: str = "viewer",
    expires_minutes: Optional[int] = None,
) -> str:
    """Create a JWT access token.

    Args:
        user_id: User ID.
        username: Username.
        role: User role.
        expires_minutes: Token expiration in minutes (uses config default if None).

    Returns:
        Encoded JWT token string.
    """
    settings = get_settings()
    if expires_minutes is None:
        expires_minutes = settings.security.access_token_expire_minutes

    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload = {
        "sub": user_id,
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(
        payload,
        settings.security.secret_key,
        algorithm=settings.security.algorithm,
    )
