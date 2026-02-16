import requests
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from config import Config

@dataclass
class Position:
    symbol: str
    quantity: float
    average_price: float
    current_price: float
    unrealized_pnl: float

@dataclass
class OrderLeg:
    action: str  # "BUY" or "SELL"
    option_symbol: str
    quantity: int
    instrument_type: str = "OPTION"

class SnapTradeClient:
    def __init__(self):
        self.consumer_key = Config.SNAPTRADE_CONSUMER_KEY
        self.client_id = Config.SNAPTRADE_CLIENT_ID
        self.user_id = Config.SNAPTRADE_USER_ID
        self.user_secret = Config.SNAPTRADE_USER_SECRET
        self.base_url = Config.SNAPTRADE_BASE_URL
        
        if not all([self.consumer_key, self.client_id, self.user_id, self.user_secret]):
            raise ValueError("All SnapTrade credentials are required")
    
    def _make_request(self, method: str, endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        
        headers = {
            "Content-Type": "application/json",
            "ClientID": self.client_id
        }
        
        auth = (self.consumer_key, self.user_secret)
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, auth=auth, params=data)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, auth=auth, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"SnapTrade API request failed: {e}")
    
    def get_accounts(self) -> List[Dict[str, Any]]:
        endpoint = f"/accounts/{self.user_id}"
        return self._make_request("GET", endpoint)
    
    def get_positions(self, account_id: str) -> List[Position]:
        endpoint = f"/accounts/{account_id}/positions"
        
        try:
            data = self._make_request("GET", endpoint)
            positions = []
            
            for pos_data in data:
                position = Position(
                    symbol=pos_data.get("symbol", ""),
                    quantity=float(pos_data.get("quantity", 0)),
                    average_price=float(pos_data.get("average_purchase_price", 0)),
                    current_price=float(pos_data.get("price", 0)),
                    unrealized_pnl=float(pos_data.get("unrealized_pnl", 0))
                )
                positions.append(position)
            
            return positions
        except Exception as e:
            raise Exception(f"Error fetching positions: {e}")
    
    def place_multileg_order(self, account_id: str, order_legs: List[OrderLeg], 
                           order_type: str = "Market", time_in_force: str = "Day") -> Dict[str, Any]:
        endpoint = f"/trade/place-multileg-order"
        
        legs_data = []
        for leg in order_legs:
            leg_data = {
                "action": leg.action,
                "option_symbol": leg.option_symbol,
                "quantity": leg.quantity,
                "instrument_type": leg.instrument_type
            }
            legs_data.append(leg_data)
        
        order_data = {
            "account_id": account_id,
            "order_type": order_type,
            "time_in_force": time_in_force,
            "legs": legs_data,
            "user_id": self.user_id
        }
        
        try:
            return self._make_request("POST", endpoint, order_data)
        except Exception as e:
            raise Exception(f"Error placing multileg order: {e}")
    
    def sell_covered_call(self, account_id: str, option_symbol: str, contracts: int = 1) -> Dict[str, Any]:
        order_leg = OrderLeg(
            action="SELL",
            option_symbol=option_symbol,
            quantity=contracts
        )
        
        return self.place_multileg_order(account_id, [order_leg])
    
    def buy_to_close_call(self, account_id: str, option_symbol: str, contracts: int = 1) -> Dict[str, Any]:
        order_leg = OrderLeg(
            action="BUY",
            option_symbol=option_symbol,
            quantity=contracts
        )
        
        return self.place_multileg_order(account_id, [order_leg])
    
    def roll_covered_call(self, account_id: str, old_option_symbol: str, new_option_symbol: str, 
                         contracts: int = 1) -> Dict[str, Any]:
        order_legs = [
            OrderLeg(action="BUY", option_symbol=old_option_symbol, quantity=contracts),
            OrderLeg(action="SELL", option_symbol=new_option_symbol, quantity=contracts)
        ]
        
        return self.place_multileg_order(account_id, order_legs)
    
    def get_option_positions(self, account_id: str, underlying_symbol: str) -> List[Position]:
        all_positions = self.get_positions(account_id)
        return [pos for pos in all_positions if underlying_symbol in pos.symbol and ("C" in pos.symbol or "P" in pos.symbol)]