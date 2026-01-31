#!/usr/bin/env python3
"""
Generate a secure API key for the Essentia API.

Usage:
    python utils/generate_key.py

This will generate a cryptographically secure API key using the secrets module.
"""
import secrets


def generate_api_key() -> str:
    """
    Generate a cryptographically secure API key.

    Returns:
        A URL-safe base64-encoded random string (43 characters)
    """
    return secrets.token_urlsafe(32)


if __name__ == "__main__":
    key = generate_api_key()
    print(f"Generated API Key: {key}")
    print()
    print("Add to your environment:")
    print(f'  API_KEYS="{key}"')
    print()
    print("Or add to existing keys:")
    print(f'  API_KEYS="existing_key1,existing_key2,{key}"')
