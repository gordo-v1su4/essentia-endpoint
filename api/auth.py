"""
Authentication module for Essentia API.

Provides API key validation using FastAPI dependency injection.
"""
import os
import secrets
from typing import Set
from fastapi import HTTPException, status
from fastapi.security import APIKeyHeader


def load_api_keys() -> Set[str]:
    """
    Load API keys from environment variable.

    Returns:
        Set of valid API keys

    Raises:
        ValueError: If API_KEYS environment variable is not set or empty
    """
    keys_str = os.getenv("API_KEYS", "")
    if not keys_str:
        raise ValueError(
            "API_KEYS environment variable not set. "
            "Please set API_KEYS with comma-separated API keys."
        )

    # Split by comma and strip whitespace
    keys = set(key.strip() for key in keys_str.split(",") if key.strip())

    if not keys:
        raise ValueError("API_KEYS environment variable is empty")

    return keys


# Load valid API keys once at startup
VALID_API_KEYS: Set[str] = load_api_keys()

# Define API Key security scheme for OpenAPI documentation
api_key_header = APIKeyHeader(
    name="X-API-Key",
    description="API Key required for authentication. Contact the administrator to receive your API key.",
    auto_error=False
)


async def verify_api_key(
    x_api_key: str = api_key_header
) -> str:
    """
    FastAPI dependency to verify API key from request header.

    Args:
        x_api_key: API key from X-API-Key header

    Returns:
        The validated API key

    Raises:
        HTTPException: 401 if API key is invalid or missing
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Use constant-time comparison to prevent timing attacks
    is_valid = any(
        secrets.compare_digest(x_api_key, valid_key)
        for valid_key in VALID_API_KEYS
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return x_api_key
