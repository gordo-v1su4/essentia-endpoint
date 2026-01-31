#!/usr/bin/env python3
"""
Generate OpenAPI schema from the FastAPI application.

Usage:
    export API_KEYS="temp_key"
    python utils/generate_openapi.py
"""
import json
import sys
import os

# Add parent directory to path so we can import main
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app

def generate_openapi_schema():
    """Generate and save OpenAPI schema to docs/openapi.json"""

    # Generate OpenAPI schema
    openapi_schema = app.openapi()

    # Write to file
    output_path = 'docs/openapi.json'
    with open(output_path, 'w') as f:
        json.dump(openapi_schema, f, indent=2)

    print(f'✅ OpenAPI schema generated: {output_path}')
    print(f'   Version: {openapi_schema["info"]["version"]}')
    print(f'   Title: {openapi_schema["info"]["title"]}')
    print(f'   Endpoints: {len(openapi_schema["paths"])}')

    # List endpoints
    print('\n   Endpoints:')
    for path, methods in openapi_schema['paths'].items():
        for method in methods.keys():
            print(f'     {method.upper()} {path}')

    # Check for security schemes
    if 'components' in openapi_schema and 'securitySchemes' in openapi_schema['components']:
        print('\n   Security Schemes:')
        for scheme_name, scheme_data in openapi_schema['components']['securitySchemes'].items():
            print(f'     {scheme_name}: {scheme_data.get("type", "unknown")}')

if __name__ == "__main__":
    if not os.getenv("API_KEYS"):
        print("⚠️  Warning: API_KEYS environment variable not set")
        print("   Setting temporary key for schema generation...")
        os.environ["API_KEYS"] = "temp_key_for_schema_generation"

    generate_openapi_schema()
