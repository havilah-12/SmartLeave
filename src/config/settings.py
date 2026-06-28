import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    # Environment
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    
    # API Keys
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    
    # Database Configuration
    DATABASE_URL = os.getenv("DATABASE_URL", "leave_app.db")
    
    # Agent Configuration
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_MIN_WAIT = int(os.getenv("RETRY_MIN_WAIT", "1"))
    RETRY_MAX_WAIT = int(os.getenv("RETRY_MAX_WAIT", "10"))
    
settings = Settings()

# Setup root logging
logging.basicConfig(
    level=logging.INFO if settings.ENVIRONMENT == "production" else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
logger.info(f"Initialized application config in {settings.ENVIRONMENT} mode.")
