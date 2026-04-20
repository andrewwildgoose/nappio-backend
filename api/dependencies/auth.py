import logging

from fastapi import HTTPException, Request

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
