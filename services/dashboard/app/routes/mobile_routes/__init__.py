from fastapi import APIRouter
from . import appointments, twilio, audio_routes, location_geofence_stuff

# Create a router for mobile routes with /mobile prefix
mobile_router = APIRouter(prefix="/mobile", tags=["mobile"])

# Include sub-routers
mobile_router.include_router(appointments.router)
mobile_router.include_router(twilio.router)
mobile_router.include_router(audio_routes.router)
mobile_router.include_router(location_geofence_stuff.router)

# Add more routers here as needed 