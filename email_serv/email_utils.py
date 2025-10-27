import logging

logger = logging.getLogger('uvicorn.error')
logger.setLevel(logging.DEBUG)

def format_address_for_email(address: dict) -> str:
    """
    Format the address dictionary into a human-readable string for email content.
    """
    try:
        address_lines = [
            address.get("address_line_1", ""),
            address.get("address_line_2", ""),
            address.get('city', ''),
            address.get('postcode', ''),
            address.get("country", "")
        ]
        # Filter out empty lines and join with comma
        formatted_address = ",".join([line for line in address_lines if line])
        return formatted_address
    except Exception as e:
        logger.error(f"format_address_for_email(): Error formatting address: {str(e)}")
        return "Address formatting error"