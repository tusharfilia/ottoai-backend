from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/reviews", tags=["reviews"])

# Review follow-up trigger endpoints
# This router can be extended with review endpoints as needed
