import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from config import Config

@dataclass
class OptionContract:
    ticker: str
    contract_type: str
    strike: float
    expiration_date: str
    underlying_ticker: str

@dataclass
class OptionQuote:
    bid: float
    ask: float
    mid: float
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    implied_volatility: Optional[float] = None
    open_interest: Optional[int] = None
    volume: Optional[int] = None

class PolygonClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or Config.POLYGON_API_KEY
        self.base_url = Config.POLYGON_BASE_URL
        
        if not self.api_key:
            raise ValueError("Polygon API key is required")
    
    def _make_request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        if params is None:
            params = {}
        
        params["apikey"] = self.api_key
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"API request failed: {e}")
    
    def get_stock_price(self, ticker: str) -> float:
        endpoint = f"/v2/last/trade/{ticker}"
        
        try:
            data = self._make_request(endpoint)
            if data.get("status") == "OK" and data.get("results"):
                return data["results"]["p"]
            else:
                raise Exception(f"Failed to get stock price for {ticker}")
        except Exception as e:
            raise Exception(f"Error fetching stock price: {e}")
    
    def get_option_contracts(self, underlying_ticker: str, contract_type: str = "call", 
                           min_dte: int = 30, max_dte: int = 45) -> List[OptionContract]:
        endpoint = "/v3/reference/options/contracts"
        
        start_date = (datetime.now() + timedelta(days=min_dte)).strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=max_dte)).strftime("%Y-%m-%d")
        
        params = {
            "underlying_ticker": underlying_ticker,
            "contract_type": contract_type,
            "expiration_date.gte": start_date,
            "expiration_date.lte": end_date,
            "limit": 1000
        }
        
        try:
            data = self._make_request(endpoint, params)
            
            contracts = []
            if data.get("status") == "OK" and data.get("results"):
                for contract_data in data["results"]:
                    contract = OptionContract(
                        ticker=contract_data["ticker"],
                        contract_type=contract_data["contract_type"],
                        strike=float(contract_data["strike_price"]),
                        expiration_date=contract_data["expiration_date"],
                        underlying_ticker=contract_data["underlying_ticker"]
                    )
                    contracts.append(contract)
            
            return contracts
        except Exception as e:
            raise Exception(f"Error fetching option contracts: {e}")
    
    def get_option_quote(self, option_ticker: str) -> OptionQuote:
        endpoint = f"/v3/snapshot/options/{option_ticker}"
        
        try:
            data = self._make_request(endpoint)
            
            if data.get("status") == "OK" and data.get("results"):
                result = data["results"]
                
                quote_data = result.get("value", {})
                greeks = result.get("greeks", {})
                
                bid = quote_data.get("bid", 0)
                ask = quote_data.get("ask", 0)
                mid = (bid + ask) / 2 if bid and ask else 0
                
                quote = OptionQuote(
                    bid=bid,
                    ask=ask,
                    mid=mid,
                    delta=greeks.get("delta"),
                    gamma=greeks.get("gamma"),
                    theta=greeks.get("theta"),
                    vega=greeks.get("vega"),
                    implied_volatility=result.get("implied_volatility"),
                    open_interest=result.get("open_interest"),
                    volume=quote_data.get("volume")
                )
                
                return quote
            else:
                raise Exception(f"No quote data found for {option_ticker}")
        except Exception as e:
            raise Exception(f"Error fetching option quote: {e}")
    
    def get_options_chain(self, underlying_ticker: str) -> List[Dict[str, Any]]:
        endpoint = f"/v3/snapshot/options/{underlying_ticker}"
        
        try:
            data = self._make_request(endpoint)
            
            chain_data = []
            if data.get("status") == "OK" and data.get("results"):
                for option_data in data["results"]:
                    chain_data.append(option_data)
            
            return chain_data
        except Exception as e:
            raise Exception(f"Error fetching options chain: {e}")