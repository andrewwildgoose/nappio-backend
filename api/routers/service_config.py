import logging
import os

from fastapi import APIRouter, HTTPException

from models.service_config_models import ServiceAreas

from repositories.service_config_repository import get_service_areas



logger = logging.getLogger('uvicorn.error')

FRONTEND_URL = os.environ.get('FRONTEND_URL')

router = APIRouter(
    prefix="/api/v1/service",
    tags=["service_config"]
)

@router.get("/service-areas", response_model=ServiceAreas)
def service_areas():
    """Retrieve the service areas configuration."""
    try:
        service_areas_list = get_service_areas()
        service_areas = ServiceAreas(postcode_prefixes=service_areas_list)
        logger.debug(f"service_areas(): Retrieved service areas: {service_areas.postcode_prefixes}")
        return service_areas
    except Exception as e:
        logger.error(f"service_areas(): Error retrieving service areas: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))