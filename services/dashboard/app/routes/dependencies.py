from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Optional
import os
from openai import OpenAI
from app.services.bland_ai import BlandAI
from app.utils.date_calculator import DateCalculator
import requests
import json
from jose import jwt, JWTError
import logging
import time
import base64

logger = logging.getLogger(__name__)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
bland_ai = BlandAI()
date_calculator = DateCalculator()


# Get Clerk API key from environment variable - ensure this is set in production
CLERK_SECRET_KEY = os.environ.get("CLERK_SECRET_KEY")
CLERK_PUBLISHABLE_KEY = os.environ.get("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY")
CLERK_API_URL = "https://api.clerk.com/v1"

# For Clerk, we need to set the Frontend API URL
CLERK_FRONTEND_API = "https://elegant-bluebird-22.clerk.accounts.dev"
CLERK_JWKS_URL = f"{CLERK_FRONTEND_API}/.well-known/jwks.json"

logger.info(f"CLERK_PUBLISHABLE_KEY environment variable: {'SET' if CLERK_PUBLISHABLE_KEY else 'NOT SET'}")
if CLERK_PUBLISHABLE_KEY:
    logger.info(f"Key format: {CLERK_PUBLISHABLE_KEY[:10]}...")
logger.info(f"Using JWKS URL: {CLERK_JWKS_URL}")

# Cache for JWKs to avoid repeated requests
jwks_cache = {"keys": None, "last_updated": 0}
JWKS_CACHE_TTL = 3600  # 1 hour

async def get_jwks():
    """Fetch and cache the Clerk JWKs (JSON Web Key Set)"""
    global jwks_cache
    current_time = time.time()
    
    # If keys are cached and still fresh, use them
    if jwks_cache["keys"] and (current_time - jwks_cache["last_updated"]) < JWKS_CACHE_TTL:
        return jwks_cache["keys"]
    
    try:
        # Fetch JWKs from Clerk
        logger.info(f"Fetching JWKs from {CLERK_JWKS_URL}")
        response = requests.get(CLERK_JWKS_URL)
        response.raise_for_status()
        
        jwks = response.json()
        jwks_cache["keys"] = jwks
        jwks_cache["last_updated"] = current_time
        logger.info(f"Successfully cached JWKs with {len(jwks.get('keys', []))} keys")
        return jwks
    except Exception as e:
        logger.error(f"Failed to fetch JWKs: {e}")
        # Don't crash the application if JWKs can't be fetched
        # Just return an empty set which will cause auth to fail
        return {"keys": []}

def find_jwk(kid, jwks):
    """Find the JWK with matching kid in the JWKS"""
    for jwk in jwks.get('keys', []):
        if jwk.get('kid') == kid:
            return jwk
    return None

async def get_user_from_clerk_token(authorization: Optional[str] = Header(None)):
    """
    Validate Clerk JWT token and return user information using the approach
    recommended in Clerk documentation.
    """
    if not authorization:
        logger.warning("Missing Authorization header")
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    if not authorization.startswith("Bearer "):
        logger.warning("Invalid Authorization format")
        raise HTTPException(status_code=401, detail="Invalid authorization format. Must be Bearer token")
    
    token = authorization.replace("Bearer ", "")
    logger.info(f"Token received, length: {len(token)}")
    
    # Special case for development tokens (if specified)
    if os.environ.get("ENVIRONMENT") == "development" and os.environ.get("ALLOW_DEV_TOKEN") == "true":
        dev_token = os.environ.get("DEV_USER_TOKEN")
        if token == dev_token:
            logger.warning("Using development token - NEVER USE THIS IN PRODUCTION")
            return {
                "id": "dev_user_id",
                "first_name": "Dev",
                "last_name": "User",
                "email": "dev@example.com",
            }
    
    try:
        # First, decode token header (without verification) to get the kid
        token_parts = token.split('.')
        if len(token_parts) != 3:
            logger.warning(f"Token does not have 3 parts (header.payload.signature)")
            raise HTTPException(status_code=401, detail="Invalid token format")
        
        # Get token header
        header_b64 = token_parts[0]
        # Add padding if needed
        header_b64 += '=' * (4 - len(header_b64) % 4) if len(header_b64) % 4 != 0 else ''
        header_bytes = base64.urlsafe_b64decode(header_b64)
        header = json.loads(header_bytes.decode('utf-8'))
        
        kid = header.get('kid')
        if not kid:
            logger.warning("No 'kid' found in JWT header")
            raise HTTPException(status_code=401, detail="Invalid token: No key ID found")
        
        # Get the JWKS
        jwks = await get_jwks()
        
        # Find the key with matching kid
        jwk = find_jwk(kid, jwks)
        if not jwk:
            logger.warning(f"No key found for kid: {kid}")
            raise HTTPException(status_code=401, detail="Invalid token: Key not found")
        
        # Use python-jose to decode and verify the token
        try:
            # Convert JWK to PEM format
            payload = jwt.decode(
                token,
                jwk,  # python-jose can handle the raw JWK
                algorithms=["RS256"],
                audience=None,  # Clerk doesn't use audience
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_nbf": True
                }
            )
            
            # Extract user info
            user_id = payload.get('sub')
            if not user_id:
                logger.warning("No user ID in token")
                raise HTTPException(status_code=401, detail="Invalid token: No user ID")
            
            # Basic user info from the token
            user_data = {
                "id": user_id,
                "first_name": payload.get("first_name", ""),
                "last_name": payload.get("last_name", ""),
                "email": payload.get("email", ""),
            }
            
            # If we need more user info, fetch from Clerk API
            if (not user_data["first_name"] or not user_data["email"]) and CLERK_SECRET_KEY:
                try:
                    headers = {
                        "Authorization": f"Bearer {CLERK_SECRET_KEY}",
                        "Content-Type": "application/json"
                    }
                    
                    user_url = f"{CLERK_API_URL}/users/{user_id}"
                    logger.info(f"Fetching additional user data from {user_url}")
                    user_response = requests.get(user_url, headers=headers)
                    
                    if user_response.status_code == 200:
                        clerk_user_data = user_response.json()
                        logger.info("Successfully fetched user data from Clerk API")
                        
                        # Extract email from email_addresses array
                        email_addresses = clerk_user_data.get("email_addresses", [])
                        primary_email = None
                        if email_addresses and len(email_addresses) > 0:
                            for email in email_addresses:
                                if email.get("id"):
                                    primary_email = email.get("email_address")
                                    break
                        
                        user_data.update({
                            "first_name": clerk_user_data.get("first_name", ""),
                            "last_name": clerk_user_data.get("last_name", ""),
                            "email": primary_email or user_data["email"],
                        })
                except Exception as e:
                    logger.warning(f"Failed to fetch additional user data: {e}")
                    # Continue with basic user data from token
            
            return user_data
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            raise HTTPException(status_code=401, detail="Token expired")
        except JWTError as e:
            logger.warning(f"Invalid token: {e}")
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
        except Exception as e:
            logger.error(f"Error processing token: {str(e)}")
            raise HTTPException(status_code=401, detail="Error processing token")
    
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(status_code=401, detail="Authentication failed")
