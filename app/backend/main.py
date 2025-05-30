import os
from dotenv import load_dotenv

from app import create_app
from load_azd_env import load_azd_env

# WEBSITE_HOSTNAME is always set by App Service, RUNNING_IN_PRODUCTION is set in main.bicep
RUNNING_ON_AZURE = os.getenv("WEBSITE_HOSTNAME") is not None or os.getenv("RUNNING_IN_PRODUCTION") is not None

if not RUNNING_ON_AZURE:
    try:
        # Try to load environment variables using azd
        load_azd_env()
    except Exception as e:
        print("Could not load azd environment, falling back to .env file")
        # Fall back to loading from .env file directly
        load_dotenv()

app = create_app()
