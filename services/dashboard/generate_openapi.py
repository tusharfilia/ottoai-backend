#!/usr/bin/env python3
"""
Generate OpenAPI spec from FastAPI app without running the server.

Usage:
    python generate_openapi.py [--output openapi.json]
    
Outputs OpenAPI spec JSON to stdout or file.
"""
import sys
import json
import argparse
from pathlib import Path

# Add the current directory to the path so we can import app
sys.path.insert(0, str(Path(__file__).parent))

try:
    from app.main import app
    from fastapi.openapi.utils import get_openapi
except ImportError as e:
    print(f"❌ Error importing FastAPI app: {e}", file=sys.stderr)
    print("\nMake sure you're in the services/dashboard directory.", file=sys.stderr)
    sys.exit(1)


def generate_openapi(output_file=None):
    """Generate OpenAPI spec from FastAPI app."""
    try:
        # Generate OpenAPI schema
        openapi_schema = get_openapi(
            title=app.title,
            version="1.0.0",
            description="Otto Backend API - FastAPI application",
            routes=app.routes,
        )
        
        # Output to file or stdout
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(openapi_schema, f, indent=2)
            print(f"✅ OpenAPI spec exported to: {output_file}")
        else:
            # Output to stdout
            print(json.dumps(openapi_schema, indent=2))
        
        # Print stats
        endpoint_count = len([p for p in openapi_schema.get("paths", {}).keys()])
        print(f"\n📊 API Statistics:", file=sys.stderr)
        print(f"  Total Paths: {endpoint_count}", file=sys.stderr)
        print(f"  Tags: {len(openapi_schema.get('tags', []))}", file=sys.stderr)
        
        return openapi_schema
        
    except Exception as e:
        print(f"❌ Error generating OpenAPI spec: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate OpenAPI spec from FastAPI app")
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output file path (default: stdout)",
        default=None
    )
    
    args = parser.parse_args()
    generate_openapi(args.output)

