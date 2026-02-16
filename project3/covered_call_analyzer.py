from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import math

from polygon_client import PolygonClient, OptionContract, OptionQuote
from config import Config

@dataclass
class CoveredCallOpportunity:
    contract: OptionContract
    quote: OptionQuote
    stock_price: float
    moneyness: float
    dte: int
    annual_return: float
    return_if_assigned: float
    breakeven: float
    max_profit: float
    max_loss: float
    probability_profit: float
    score: float

class CoveredCallAnalyzer:
    def __init__(self):
        self.polygon_client = PolygonClient()
        self.rules = Config.COVERED_CALL_RULES
    
    def _calculate_days_to_expiration(self, expiration_date: str) -> int:
        exp_date = datetime.strptime(expiration_date, "%Y-%m-%d")
        current_date = datetime.now()
        return (exp_date - current_date).days
    
    def _calculate_moneyness(self, stock_price: float, strike_price: float) -> float:
        return strike_price / stock_price
    
    def _calculate_annual_return(self, premium: float, stock_price: float, dte: int) -> float:
        if dte <= 0:
            return 0
        return (premium / stock_price) * (365 / dte)
    
    def _calculate_return_if_assigned(self, premium: float, stock_price: float, strike_price: float) -> float:
        if stock_price == 0:
            return 0
        capital_gain = max(0, strike_price - stock_price)
        return (premium + capital_gain) / stock_price
    
    def _calculate_probability_profit(self, delta: Optional[float]) -> float:
        if delta is None:
            return 0.5
        return 1 - abs(delta)
    
    def _score_opportunity(self, opportunity: CoveredCallOpportunity) -> float:
        delta_score = 0
        if opportunity.quote.delta:
            target_delta = (self.rules["min_delta"] + self.rules["max_delta"]) / 2
            delta_diff = abs(opportunity.quote.delta - target_delta)
            delta_score = max(0, 1 - (delta_diff / target_delta))
        
        return_score = min(opportunity.annual_return / 0.15, 1.0)
        
        probability_score = opportunity.probability_profit
        
        dte_score = 0
        if self.rules["min_dte"] <= opportunity.dte <= self.rules["max_dte"]:
            dte_center = (self.rules["min_dte"] + self.rules["max_dte"]) / 2
            dte_diff = abs(opportunity.dte - dte_center)
            dte_score = max(0, 1 - (dte_diff / dte_center))
        
        volume_score = 0
        if opportunity.quote.volume:
            volume_score = min(opportunity.quote.volume / 10, 1.0)
        
        open_interest_score = 0
        if opportunity.quote.open_interest:
            open_interest_score = min(opportunity.quote.open_interest / 100, 1.0)
        
        weights = {
            'delta': 0.25,
            'return': 0.25,
            'probability': 0.20,
            'dte': 0.15,
            'volume': 0.10,
            'open_interest': 0.05
        }
        
        score = (
            delta_score * weights['delta'] +
            return_score * weights['return'] +
            probability_score * weights['probability'] +
            dte_score * weights['dte'] +
            volume_score * weights['volume'] +
            open_interest_score * weights['open_interest']
        )
        
        return score
    
    def analyze_covered_calls(self, ticker: str, shares_owned: int = 100) -> List[CoveredCallOpportunity]:
        try:
            stock_price = self.polygon_client.get_stock_price(ticker)
            print(f"Current stock price for {ticker}: ${stock_price:.2f}")
        except Exception as e:
            raise Exception(f"Failed to get stock price for {ticker}: {e}")
        
        try:
            contracts = self.polygon_client.get_option_contracts(
                underlying_ticker=ticker,
                contract_type="call",
                min_dte=self.rules["min_dte"],
                max_dte=self.rules["max_dte"]
            )
            print(f"Found {len(contracts)} call contracts")
        except Exception as e:
            raise Exception(f"Failed to get option contracts: {e}")
        
        opportunities = []
        
        for contract in contracts:
            try:
                quote = self.polygon_client.get_option_quote(contract.ticker)
                
                if quote.bid <= 0 or quote.ask <= 0:
                    continue
                
                if quote.delta is None or not (self.rules["min_delta"] <= abs(quote.delta) <= self.rules["max_delta"]):
                    continue
                
                dte = self._calculate_days_to_expiration(contract.expiration_date)
                if not (self.rules["min_dte"] <= dte <= self.rules["max_dte"]):
                    continue
                
                moneyness = self._calculate_moneyness(stock_price, contract.strike)
                annual_return = self._calculate_annual_return(quote.mid, stock_price, dte)
                return_if_assigned = self._calculate_return_if_assigned(quote.mid, stock_price, contract.strike)
                breakeven = stock_price - quote.mid
                max_profit = quote.mid + max(0, contract.strike - stock_price)
                max_loss = stock_price - quote.mid
                probability_profit = self._calculate_probability_profit(quote.delta)
                
                opportunity = CoveredCallOpportunity(
                    contract=contract,
                    quote=quote,
                    stock_price=stock_price,
                    moneyness=moneyness,
                    dte=dte,
                    annual_return=annual_return,
                    return_if_assigned=return_if_assigned,
                    breakeven=breakeven,
                    max_profit=max_profit,
                    max_loss=max_loss,
                    probability_profit=probability_profit,
                    score=0  # Will be calculated next
                )
                
                opportunity.score = self._score_opportunity(opportunity)
                opportunities.append(opportunity)
                
            except Exception as e:
                print(f"Error processing contract {contract.ticker}: {e}")
                continue
        
        opportunities.sort(key=lambda x: x.score, reverse=True)
        return opportunities
    
    def get_best_covered_call(self, ticker: str, shares_owned: int = 100) -> Optional[CoveredCallOpportunity]:
        opportunities = self.analyze_covered_calls(ticker, shares_owned)
        return opportunities[0] if opportunities else None