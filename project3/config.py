import os
from typing import Dict, Any

class Config:
    POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
    SNAPTRADE_CONSUMER_KEY = os.getenv("SNAPTRADE_CONSUMER_KEY")
    SNAPTRADE_CLIENT_ID = os.getenv("SNAPTRADE_CLIENT_ID")
    SNAPTRADE_USER_ID = os.getenv("SNAPTRADE_USER_ID")
    SNAPTRADE_USER_SECRET = os.getenv("SNAPTRADE_USER_SECRET")
    
    POLYGON_BASE_URL = "https://api.polygon.io"
    SNAPTRADE_BASE_URL = "https://api.snaptrade.com/api/v1"
    
    COVERED_CALL_RULES = {
        "min_delta": 0.15,
        "max_delta": 0.30,
        "min_dte": 30,
        "max_dte": 45,
        "profit_target": 0.50,
        "roll_dte": 21,
    }