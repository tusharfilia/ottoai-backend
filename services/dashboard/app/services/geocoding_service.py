"""
Geocoding service for converting addresses to geographic coordinates.
"""
from typing import Optional, Tuple
import re
from urllib.parse import quote

import requests
from app.config import settings
from app.core.pii_masking import PIISafeLogger

logger = PIISafeLogger(__name__)


class GeocodingService:
    """
    Geocoding service using Google Maps Geocoding API.
    
    Falls back to other providers if Google is not configured.
    """
    
    def __init__(self):
        self.google_api_key = getattr(settings, 'GOOGLE_MAPS_API_KEY', None)
        self.use_google = bool(self.google_api_key)
    
    def geocode_address(
        self,
        address: str,
        company_id: Optional[str] = None
    ) -> Optional[Tuple[float, float]]:
        """
        Geocode an address to lat/lng coordinates.
        
        Args:
            address: Full address string (e.g., "123 Main St, City, State ZIP")
            company_id: Optional tenant ID for logging
        
        Returns:
            Tuple of (latitude, longitude) or None if geocoding fails
        """
        if not address or not address.strip():
            logger.warning(f"Empty address provided for geocoding (company: {company_id})")
            return None
        
        # Try Google Maps first
        if self.use_google:
            try:
                result = self._geocode_google(address)
                if result:
                    logger.info(f"Geocoded address via Google Maps: {address[:50]}... -> {result}")
                    return result
            except Exception as e:
                logger.warning(f"Google Maps geocoding failed: {str(e)}, trying fallback")
        
        # Fallback: Use Nominatim (OpenStreetMap) - free, no API key needed
        try:
            result = self._geocode_nominatim(address)
            if result:
                logger.info(f"Geocoded address via Nominatim: {address[:50]}... -> {result}")
                return result
        except Exception as e:
            logger.error(f"Geocoding failed for address {address[:50]}...: {str(e)}")
            return None
        
        return None
    
    def _geocode_google(self, address: str) -> Optional[Tuple[float, float]]:
        """Geocode using Google Maps API."""
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "address": address,
            "key": self.google_api_key
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("status") != "OK" or not data.get("results"):
            logger.warning(f"Google Maps geocoding returned status: {data.get('status')}")
            return None
        
        location = data["results"][0]["geometry"]["location"]
        return (location["lat"], location["lng"])
    
    def _geocode_nominatim(self, address: str) -> Optional[Tuple[float, float]]:
        """
        Geocode using Nominatim (OpenStreetMap) - free alternative.
        
        Note: Nominatim has rate limits (1 request/second recommended).
        Use for development/testing or when Google Maps API key is not available.
        """
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": address,
            "format": "json",
            "limit": 1
        }
        headers = {
            "User-Agent": "OttoAI-Geocoding-Service/1.0"  # Required by Nominatim
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if not data:
            logger.warning(f"Nominatim geocoding returned no results for: {address[:50]}...")
            return None
        
        result = data[0]
        return (float(result["lat"]), float(result["lon"]))
    
    def reverse_geocode(
        self,
        lat: float,
        lng: float
    ) -> Optional[str]:
        """
        Reverse geocode coordinates to address.
        
        Args:
            lat: Latitude
            lng: Longitude
        
        Returns:
            Address string or None if reverse geocoding fails
        """
        if self.use_google:
            try:
                return self._reverse_geocode_google(lat, lng)
            except Exception as e:
                logger.warning(f"Google reverse geocoding failed: {str(e)}")
        
        # Fallback to Nominatim
        try:
            return self._reverse_geocode_nominatim(lat, lng)
        except Exception as e:
            logger.error(f"Reverse geocoding failed: {str(e)}")
            return None
    
    def _reverse_geocode_google(self, lat: float, lng: float) -> Optional[str]:
        """Reverse geocode using Google Maps API."""
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "latlng": f"{lat},{lng}",
            "key": self.google_api_key
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("status") != "OK" or not data.get("results"):
            return None
        
        return data["results"][0]["formatted_address"]
    
    def _reverse_geocode_nominatim(self, lat: float, lng: float) -> Optional[str]:
        """Reverse geocode using Nominatim."""
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            "lat": lat,
            "lon": lng,
            "format": "json"
        }
        headers = {
            "User-Agent": "OttoAI-Geocoding-Service/1.0"
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if not data.get("display_name"):
            return None
        
        return data["display_name"]


# Global geocoding service instance
geocoding_service = GeocodingService()

