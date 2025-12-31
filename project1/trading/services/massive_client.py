from django.conf import settings
from massive import RESTClient
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class MassiveAPIClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.MASSIVE_API_KEY
        if not self.api_key:
            raise ValueError("Massive API key is required")
        self.client = RESTClient(self.api_key)

    def fetch_stock_data(
        self, 
        ticker: str, 
        start_date: str, 
        end_date: str,
        multiplier: int = 1,
        timespan: str = "day",
        adjusted: bool = True,
        limit: int = 50000
    ) -> List[Dict]:
        try:
            aggs = []
            for agg in self.client.list_aggs(
                ticker,
                multiplier,
                timespan,
                start_date,
                end_date,
                adjusted=adjusted,
                limit=limit,
            ):
                aggs.append({
                    'date': datetime.fromtimestamp(agg.timestamp / 1000).date(),
                    'open': agg.open,
                    'high': agg.high,
                    'low': agg.low,
                    'close': agg.close,
                    'volume': agg.volume,
                    'vwap': getattr(agg, 'vwap', None),
                    'transactions': getattr(agg, 'transactions', None),
                })
            
            logger.info(f"Fetched {len(aggs)} data points for {ticker}")
            return aggs
            
        except (ValueError, TypeError) as e:
            logger.error(f"Error fetching data for {ticker}: {str(e)}")
            raise

    def fetch_multiple_stocks(
        self, 
        tickers: List[str], 
        start_date: str, 
        end_date: str,
        adjusted: bool = True
    ) -> Dict[str, List[Dict]]:
        results = {}
        
        for ticker in tickers:
            try:
                results[ticker] = self.fetch_stock_data(
                    ticker=ticker,
                    start_date=start_date,
                    end_date=end_date,
                    adjusted=adjusted
                )
                logger.info(f"Successfully fetched data for {ticker}")
            except (ValueError, TypeError) as e:
                logger.error(f"Failed to fetch data for {ticker}: {str(e)}")
                results[ticker] = []
                
        return results

    def get_historical_data_for_momentum(
        self, 
        ticker: str, 
        calculation_date: Optional[datetime] = None
    ) -> List[Dict]:
        if calculation_date is None:
            calculation_date = datetime.now().date()
        
        # Calculate required date range (14 months back for buffer)
        start_date = calculation_date - timedelta(days=420)  # ~14 months
        end_date = calculation_date
        
        return self.fetch_stock_data(
            ticker=ticker,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d')
        )

    def validate_stock_data_sufficiency(
        self, 
        data: List[Dict], 
        required_days: int = 280
    ) -> bool:
        if not data or len(data) < required_days:
            logger.warning(f"Insufficient data: {len(data) if data else 0} days, required: {required_days}")
            return False
        return True

    def get_sp500_tickers(self) -> List[str]:
        # For demonstration, returning a subset of S&P 500 tickers
        # In production, you might want to fetch this from an API or maintain a database table
        return [
            'AAPL', 'MSFT', 'AMZN', 'NVDA', 'GOOGL', 'GOOG', 'META', 'TSLA', 'BRK.B', 'UNH',
            'JNJ', 'JPM', 'V', 'PG', 'XOM', 'HD', 'CVX', 'MA', 'BAC', 'ABBV',
            'PFE', 'AVGO', 'KO', 'COST', 'DIS', 'TMO', 'WMT', 'DHR', 'NEE', 'VZ',
            'ABT', 'MRK', 'ADBE', 'CRM', 'NFLX', 'NKE', 'INTC', 'AMD', 'T', 'TXN',
            'COP', 'LLY', 'PM', 'RTX', 'HON', 'CMCSA', 'UPS', 'QCOM', 'SBUX', 'LOW'
        ]

    def create_dataframe_from_aggs(self, aggs: List[Dict]) -> pd.DataFrame:
        if not aggs:
            return pd.DataFrame()
        
        df = pd.DataFrame(aggs)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        df.sort_index(inplace=True)
        
        return df

    def calculate_returns(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        
        df = df.copy()
        df['daily_return'] = df['close'].pct_change()
        df['cumulative_return'] = (1 + df['daily_return']).cumprod() - 1
        
        return df

    def get_price_on_date(
        self, 
        ticker: str, 
        target_date: datetime, 
        tolerance_days: int = 7
    ) -> Optional[float]:
        start_date = target_date - timedelta(days=tolerance_days)
        end_date = target_date + timedelta(days=tolerance_days)
        
        try:
            data = self.fetch_stock_data(
                ticker=ticker,
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )
            
            if not data:
                return None
            
            # Find the closest date
            target_date_obj = target_date if hasattr(target_date, 'date') else target_date
            if hasattr(target_date_obj, 'date'):
                target_date_obj = target_date_obj.date()
                
            closest_data = min(
                data, 
                key=lambda x: abs((x['date'] - target_date_obj).days)
            )
            
            return float(closest_data['close'])
            
        except (ValueError, TypeError) as e:
            logger.error(f"Error getting price for {ticker} on {target_date}: {str(e)}")
            return None


def get_massive_client() -> MassiveAPIClient:
    return MassiveAPIClient()