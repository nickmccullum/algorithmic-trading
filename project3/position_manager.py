from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from snaptrade_client import SnapTradeClient, Position
from polygon_client import PolygonClient
from covered_call_analyzer import CoveredCallAnalyzer, CoveredCallOpportunity
from config import Config

@dataclass
class CoveredCallPosition:
    underlying_symbol: str
    stock_quantity: int
    option_symbol: str
    option_quantity: int
    strike_price: float
    expiration_date: str
    entry_premium: float
    current_premium: float
    days_to_expiration: int
    unrealized_pnl: float

class PositionManager:
    def __init__(self):
        self.snaptrade = SnapTradeClient()
        self.polygon = PolygonClient()
        self.analyzer = CoveredCallAnalyzer()
        self.rules = Config.COVERED_CALL_RULES
    
    def get_covered_call_positions(self, account_id: str) -> List[CoveredCallPosition]:
        try:
            all_positions = self.snaptrade.get_positions(account_id)
            
            stock_positions = {}
            option_positions = {}
            
            for position in all_positions:
                if "C" in position.symbol or "P" in position.symbol:
                    underlying = self._extract_underlying_from_option(position.symbol)
                    if underlying not in option_positions:
                        option_positions[underlying] = []
                    option_positions[underlying].append(position)
                else:
                    stock_positions[position.symbol] = position
            
            covered_call_positions = []
            
            for underlying, stock_pos in stock_positions.items():
                if underlying in option_positions:
                    call_options = [opt for opt in option_positions[underlying] 
                                  if "C" in opt.symbol and opt.quantity < 0]  # Short calls
                    
                    for call_option in call_options:
                        strike, exp_date = self._parse_option_symbol(call_option.symbol)
                        dte = self._calculate_dte(exp_date)
                        
                        cc_position = CoveredCallPosition(
                            underlying_symbol=underlying,
                            stock_quantity=int(stock_pos.quantity),
                            option_symbol=call_option.symbol,
                            option_quantity=abs(int(call_option.quantity)),
                            strike_price=strike,
                            expiration_date=exp_date,
                            entry_premium=call_option.average_price,
                            current_premium=call_option.current_price,
                            days_to_expiration=dte,
                            unrealized_pnl=call_option.unrealized_pnl
                        )
                        covered_call_positions.append(cc_position)
            
            return covered_call_positions
            
        except Exception as e:
            raise Exception(f"Error getting covered call positions: {e}")
    
    def check_management_rules(self, position: CoveredCallPosition) -> Tuple[bool, str]:
        profit_pct = (position.entry_premium - position.current_premium) / position.entry_premium
        
        if profit_pct >= self.rules["profit_target"]:
            return True, f"CLOSE: {profit_pct:.1%} profit target reached"
        
        if position.days_to_expiration <= self.rules["roll_dte"]:
            return True, f"ROLL: {position.days_to_expiration} DTE threshold reached"
        
        return False, "HOLD: No action needed"
    
    def suggest_roll_options(self, position: CoveredCallPosition) -> List[CoveredCallOpportunity]:
        try:
            stock_price = self.polygon.get_stock_price(position.underlying_symbol)
            
            if stock_price >= position.strike_price:
                # Stock is above strike, look for higher strikes or later expirations
                opportunities = self.analyzer.analyze_covered_calls(position.underlying_symbol)
                return [opp for opp in opportunities[:5] 
                       if opp.contract.strike >= position.strike_price]
            else:
                # Stock is below strike, can roll to same or different strike
                opportunities = self.analyzer.analyze_covered_calls(position.underlying_symbol)
                return opportunities[:5]
                
        except Exception as e:
            print(f"Error suggesting roll options: {e}")
            return []
    
    def close_position(self, account_id: str, position: CoveredCallPosition) -> bool:
        try:
            result = self.snaptrade.buy_to_close_call(
                account_id=account_id,
                option_symbol=position.option_symbol,
                contracts=position.option_quantity
            )
            return result.get("success", False)
        except Exception as e:
            print(f"Error closing position: {e}")
            return False
    
    def roll_position(self, account_id: str, old_position: CoveredCallPosition, 
                     new_opportunity: CoveredCallOpportunity) -> bool:
        try:
            result = self.snaptrade.roll_covered_call(
                account_id=account_id,
                old_option_symbol=old_position.option_symbol,
                new_option_symbol=new_opportunity.contract.ticker,
                contracts=old_position.option_quantity
            )
            return result.get("success", False)
        except Exception as e:
            print(f"Error rolling position: {e}")
            return False
    
    def _extract_underlying_from_option(self, option_symbol: str) -> str:
        # Parse option symbol to extract underlying
        # Format: AAPL241220C00150000 -> AAPL
        import re
        match = re.match(r'^([A-Z]+)', option_symbol)
        return match.group(1) if match else ""
    
    def _parse_option_symbol(self, option_symbol: str) -> Tuple[float, str]:
        # Parse option symbol to extract strike and expiration
        # Format: AAPL241220C00150000
        import re
        
        # Extract date part (6 digits: YYMMDD)
        date_match = re.search(r'(\d{6})', option_symbol)
        if date_match:
            date_str = date_match.group(1)
            year = 2000 + int(date_str[:2])
            month = int(date_str[2:4])
            day = int(date_str[4:6])
            exp_date = f"{year}-{month:02d}-{day:02d}"
        else:
            exp_date = "2024-01-01"  # Default
        
        # Extract strike (last 8 digits, divide by 1000)
        strike_match = re.search(r'(\d{8})$', option_symbol)
        if strike_match:
            strike = int(strike_match.group(1)) / 1000
        else:
            strike = 0.0
        
        return strike, exp_date
    
    def _calculate_dte(self, expiration_date: str) -> int:
        try:
            exp_date = datetime.strptime(expiration_date, "%Y-%m-%d")
            return (exp_date - datetime.now()).days
        except:
            return 0