import logging
import os
import secrets

from fastapi import Header, HTTPException, Request

from config.supabase import get_supabase

logger = logging.getLogger('uvicorn.error')

supabase = get_supabase()


async def get_authenticated_user(request: Request):
    """
    FastAPI dependency: extracts and validates a JWT token from the Authorization header.

    Returns:
        The authenticated Supabase user object.

    Raises:
        HTTPException 401: if token is missing, invalid, or expired.
    """
    authorization = request.headers.get("Authorization")
    if not authorization:
        raise HTTPException(status_code=401, detail="No auth token")

    token = authorization.replace('Bearer ', '')

    try:
        auth_response = supabase.auth.get_user(token)
        if not auth_response or not auth_response.user:
            raise HTTPException(status_code=401, detail="Invalid token")
        return auth_response.user

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"get_authenticated_user(): Error getting user: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid token")


def require_api_key(*allowed_env_vars: str):
    """
    Build a FastAPI dependency that checks the X-API-Key header against the
    keys held in the given environment variables.

    Keys are read on each request, so a rotated key takes effect on restart
    without code changes. If none of the env vars are set, every request is
    rejected (fail closed) rather than leaving the API open by accident.
    """
    async def verify_api_key(x_api_key: str | None = Header(default=None)):
        valid_keys = [os.environ[v] for v in allowed_env_vars if os.environ.get(v)]
        if not valid_keys:
            logger.error(f"require_api_key(): none of {allowed_env_vars} are set; rejecting request")
            raise HTTPException(status_code=401, detail="Invalid API key")
        if not x_api_key or not any(secrets.compare_digest(x_api_key, k) for k in valid_keys):
            raise HTTPException(status_code=401, detail="Invalid API key")

    return verify_api_key
