import json
from datetime import datetime
import os
import requests
from dotenv import load_dotenv  
from .tracing import setup_tracing 
from .decorator import setup_decorator, anosys_logger, anosys_raw_logger

# Load environment variables from .env file
load_dotenv()
_tracing_initialized = False  # Global flag to ensure tracing setup is only run once

setup_api = setup_decorator  # new alias
__all__ = [
    "AnosysOpenAILogger",
    "anosys_logger",
    "anosys_raw_logger",
    "setup_decorator",
    "setup_api"
]

class AnosysOpenAILogger:
    """
    Logging utility that captures traces and spans, transforms them,
    and sends them to the Anosys API endpoint for ingestion/logging.
    """

    def __init__(self, get_user_context=None):
        global _tracing_initialized
        _tracing_initialized = False
        api_key = os.getenv('ANOSYS_API_KEY')
        if not api_key:
            print("[ERROR]‼️ ANOSYS_API_KEYnot found. Please obtain your API key from https://console.anosys.ai/collect/integrationoptions")

        # retrive AnoSys url from API key and build the logging endpoint URL
        try:
            response = requests.get(f"https://api.anosys.ai/api/resolveapikeys?apikey={api_key or 'AnoSys_mock_api_key'}", timeout=30)
            response.raise_for_status()  # Raises HTTPError for bad responses (e.g., 4xx/5xx)
            data = response.json()
            self.log_api_url = data.get("url", "https://www.anosys.ai")
        except requests.exceptions.RequestException as e:
            print(f"[ERROR]❌ Failed to resolve API key: {e}")
            self.log_api_url = "https://www.anosys.ai"

        # Optional function to provide user context (e.g., session_id, token)
        self.get_user_context = get_user_context or (lambda: None)

        if not _tracing_initialized:
            setup_decorator(self.log_api_url)
            setup_tracing(self.log_api_url)
            _tracing_initialized = True