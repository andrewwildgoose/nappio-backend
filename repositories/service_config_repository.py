import logging

from config.supabase import get_supabase

logger = logging.getLogger('uvicorn.error')

supabase = get_supabase()

def get_service_areas() -> list[str]:
    """Retrieve Postcode prefixes for service areas from the database."""
    try:
        service_areas_dict = supabase.table('service_areas').select('postcode_prefix').execute()
        service_areas = [item['postcode_prefix'] for item in service_areas_dict.data if item.get('postcode_prefix')]
        logger.debug(f"get_service_areas(): Retrieved service_areas: {service_areas}")
        return service_areas
    except Exception as e:
        logger.error(f"get_service_areas(): Error retrieving service_areas: {str(e)}")
        raise Exception(f"Error retrieving service_areas: {str(e)}")