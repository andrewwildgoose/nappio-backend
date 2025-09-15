import os
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions
import logging


# Set up logging
logger = logging.getLogger('uvicorn.error')

class SupabaseConfig:
    _instance = None
    _client = None

    _supabase_url = os.environ.get('SUPABASE_URL')
    _supabase_key = os.environ.get('SUPABASE_KEY')    

    @classmethod
    def get_client(cls) -> Client:
        """
        Get or create a Supabase client instance.
        Uses the Singleton pattern to ensure only one client exists.
        """
        try:
            if cls._client is None:
                # Get configuration from environment variables


                if not cls._supabase_url or not cls._supabase_key:
                    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables")

                # Create the client
                try:
                    cls._client = create_client(
                        cls._supabase_url, 
                        cls._supabase_key
                        )
                    logger.info("Supabase client initialized successfully")
                except Exception as e:
                    logger.error(f"Failed to initialize Supabase client: {str(e)}")
                    raise

            return cls._client
        except Exception as e:
            logger.error(f"Error in get_client(): {str(e)}")
            raise

    @classmethod
    def get_service_role_client(cls) -> Client:
        """
        Get the Supabase service role client instance.
        """
        try:
            service_role_key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
            if not service_role_key:
                raise ValueError("SUPABASE_SERVICE_ROLE_KEY must be set in environment variables")

            admin_supabase = create_client(
                cls._supabase_url, 
                service_role_key,
                options=ClientOptions(
                    auto_refresh_token=False,
                    persist_session=False,
                )
            )
        
            return admin_supabase

        except Exception as e:
            logger.error(f"Error in get_service_role_client(): {str(e)}")
            raise


# Create a convenience function to get the client
def get_supabase() -> Client:
    """
    Convenience function to get the Supabase client instance.
    """
    try:
        logger.info("get_supabase() called")
        return SupabaseConfig.get_client()
    except Exception as e:
        logger.error(f"Error in get_supabase(): {str(e)}")
        raise
    
def get_supabase_service_role() -> Client:
    """
    Convenience function to get the Supabase service role client.
    """
    try:
        logger.info("get_supabase_service_role() called")
        return SupabaseConfig.get_service_role_client()
    except Exception as e:
        logger.error(f"Error in get_supabase_service_role(): {str(e)}")
        raise