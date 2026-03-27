from django.conf import settings
from massive import RESTClient
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
import time
from urllib3.exceptions import MaxRetryError
from massive.exceptions import BadResponse

logger = logging.getLogger(__name__)


class MassiveAPIClient:
    def __init__(self, api_key: str = None, requests_per_minute: int = 5):
        self.api_key = api_key or settings.MASSIVE_API_KEY
        if not self.api_key:
            raise ValueError("Massive API key is required")
        self.client = RESTClient(self.api_key)
        self.requests_per_minute = requests_per_minute
        self.request_times = []
        self._cache = {}  # Simple in-memory cache

    def _rate_limit(self):
        """Implement rate limiting to avoid hitting API limits"""
        current_time = time.time()
        # Remove requests older than 1 minute
        self.request_times = [t for t in self.request_times if current_time - t < 60]
        
        if len(self.request_times) >= self.requests_per_minute:
            sleep_time = 60 - (current_time - self.request_times[0]) + 1
            if sleep_time > 0:
                logger.info(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
                time.sleep(sleep_time)
        
        self.request_times.append(current_time)

    def _get_cache_key(self, ticker: str, start_date: str, end_date: str) -> str:
        """Generate cache key for API requests"""
        return f"{ticker}:{start_date}:{end_date}"

    def fetch_stock_data(
        self, 
        ticker: str, 
        start_date: str, 
        end_date: str,
        multiplier: int = 1,
        timespan: str = "day",
        adjusted: bool = True,
        limit: int = 50000,
        use_cache: bool = True,
        max_retries: int = 3,
        retry_delay: int = 60
    ) -> List[Dict]:
        cache_key = self._get_cache_key(ticker, start_date, end_date)
        
        # Check cache first
        if use_cache and cache_key in self._cache:
            logger.info(f"Using cached data for {ticker}")
            return self._cache[cache_key]
        
        # Apply rate limiting
        self._rate_limit()
        
        for attempt in range(max_retries):
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
                
                # Cache the result
                if use_cache:
                    self._cache[cache_key] = aggs
                
                logger.info(f"Fetched {len(aggs)} data points for {ticker}")
                return aggs
                
            except MaxRetryError as e:
                if "429" in str(e) and attempt < max_retries - 1:
                    logger.warning(f"Rate limited on attempt {attempt + 1} for {ticker}, retrying in {retry_delay} seconds")
                    time.sleep(retry_delay)
                    continue
                else:
                    logger.error(f"Max retries exceeded for {ticker}: {str(e)}")
                    raise
            except (ValueError, TypeError, BadResponse) as e:
                logger.error(f"Error fetching data for {ticker}: {str(e)}")
                raise

    def fetch_multiple_stocks(
        self, 
        tickers: List[str], 
        start_date: str, 
        end_date: str,
        adjusted: bool = True,
        batch_size: int = 10,
        delay_between_batches: int = 12
    ) -> Dict[str, List[Dict]]:
        """
        Fetch data for multiple stocks with intelligent batching and rate limiting.
        
        Args:
            tickers: List of stock tickers
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            adjusted: Whether to use adjusted prices
            batch_size: Number of stocks to process in each batch
            delay_between_batches: Seconds to wait between batches
        """
        results = {}
        total_tickers = len(tickers)
        
        logger.info(f"Fetching data for {total_tickers} stocks in batches of {batch_size}")
        
        # Process tickers in batches
        for i in range(0, total_tickers, batch_size):
            batch_tickers = tickers[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total_tickers + batch_size - 1) // batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch_tickers)} stocks)")
            
            for ticker in batch_tickers:
                try:
                    results[ticker] = self.fetch_stock_data(
                        ticker=ticker,
                        start_date=start_date,
                        end_date=end_date,
                        adjusted=adjusted
                    )
                    logger.info(f"Successfully fetched data for {ticker}")
                except (MaxRetryError, ValueError, TypeError, BadResponse) as e:
                    logger.error(f"Failed to fetch data for {ticker}: {str(e)}")
                    results[ticker] = []
            
            # Delay between batches to avoid rate limits
            if i + batch_size < total_tickers:
                logger.info(f"Waiting {delay_between_batches} seconds before next batch...")
                time.sleep(delay_between_batches)
                
        return results

    def fetch_bulk_momentum_data(
        self, 
        tickers: List[str], 
        calculation_date: datetime = None
    ) -> Dict[str, Dict[str, Optional[float]]]:
        """
        TRUE bulk fetch using Massive's grouped daily API - only 2 API calls total!
        Fetches all tickers for 12-month and 1-month dates simultaneously.
        
        Returns:
            Dict with ticker as key and dict with 'price_12m' and 'price_1m' as values
        """
        if calculation_date is None:
            calculation_date = datetime.now().date()
        
        twelve_months_ago = calculation_date - timedelta(days=365)
        one_month_ago = calculation_date - timedelta(days=30)
        
        logger.info(f"TRUE bulk fetching momentum data for {len(tickers)} stocks using grouped daily API")
        logger.info(f"Target dates: 12m={twelve_months_ago}, 1m={one_month_ago}")
        
        momentum_data = {}
        
        # Initialize all tickers with None values
        for ticker in tickers:
            momentum_data[ticker] = {'price_12m': None, 'price_1m': None}
        
        try:
            # Apply rate limiting before API calls
            self._rate_limit()
            
            # CALL 1: Get all stocks' prices for 12 months ago (1 API call)
            logger.info(f"Fetching grouped daily data for 12 months ago ({twelve_months_ago})")
            twelve_month_data = self.client.get_grouped_daily_aggs(
                date=twelve_months_ago,
                adjusted=True
            )
            
            # Process 12-month data
            twelve_month_prices = {}
            for agg in twelve_month_data:
                if hasattr(agg, 'ticker') and agg.ticker in tickers:
                    twelve_month_prices[agg.ticker] = float(agg.close)
            
            logger.info(f"Found 12-month prices for {len(twelve_month_prices)} stocks")
            
            # Apply rate limiting before second API call
            self._rate_limit()
            
            # CALL 2: Get all stocks' prices for 1 month ago (1 API call)
            logger.info(f"Fetching grouped daily data for 1 month ago ({one_month_ago})")
            one_month_data = self.client.get_grouped_daily_aggs(
                date=one_month_ago,
                adjusted=True
            )
            
            # Process 1-month data
            one_month_prices = {}
            for agg in one_month_data:
                if hasattr(agg, 'ticker') and agg.ticker in tickers:
                    one_month_prices[agg.ticker] = float(agg.close)
            
            logger.info(f"Found 1-month prices for {len(one_month_prices)} stocks")
            
            # Combine results
            for ticker in tickers:
                momentum_data[ticker] = {
                    'price_12m': twelve_month_prices.get(ticker),
                    'price_1m': one_month_prices.get(ticker)
                }
                
                logger.debug(f"Momentum data for {ticker}: "
                           f"12m=${momentum_data[ticker]['price_12m']}, "
                           f"1m=${momentum_data[ticker]['price_1m']}")
            
            # Handle weekend/holiday fallback if needed
            missing_tickers = [t for t in tickers if not momentum_data[t]['price_12m'] or not momentum_data[t]['price_1m']]
            if missing_tickers:
                logger.info(f"Handling {len(missing_tickers)} stocks with missing data using fallback dates")
                momentum_data = self._handle_missing_data_fallback(momentum_data, missing_tickers, calculation_date)
            
            logger.info(f"Successfully fetched momentum data using only 2 API calls!")
            
        except Exception as e:
            logger.error(f"Error with grouped daily API, falling back to individual calls: {str(e)}")
            # Fallback to the old method if grouped daily fails
            return self._fetch_bulk_momentum_data_fallback(tickers, calculation_date)
        
        return momentum_data

    def _handle_missing_data_fallback(
        self, 
        momentum_data: Dict[str, Dict[str, Optional[float]]], 
        missing_tickers: List[str], 
        calculation_date: datetime
    ) -> Dict[str, Dict[str, Optional[float]]]:
        """
        Handle missing data by trying nearby dates (weekends/holidays)
        """
        twelve_months_ago = calculation_date - timedelta(days=365)
        one_month_ago = calculation_date - timedelta(days=30)
        
        # Try dates within a 7-day window
        for days_offset in [1, 2, 3, -1, -2, -3, 4, 5, 6, 7, -4, -5, -6, -7]:
            if not missing_tickers:
                break
                
            # Try 12-month fallback
            fallback_12m_date = twelve_months_ago + timedelta(days=days_offset)
            try:
                self._rate_limit()
                fallback_12m_data = self.client.get_grouped_daily_aggs(
                    date=fallback_12m_date,
                    adjusted=True
                )
                
                for agg in fallback_12m_data:
                    if hasattr(agg, 'ticker') and agg.ticker in missing_tickers:
                        if not momentum_data[agg.ticker]['price_12m']:
                            momentum_data[agg.ticker]['price_12m'] = float(agg.close)
                            logger.debug(f"Found 12m price for {agg.ticker} on {fallback_12m_date}")
            except:
                pass
            
            # Try 1-month fallback
            fallback_1m_date = one_month_ago + timedelta(days=days_offset)
            try:
                self._rate_limit()
                fallback_1m_data = self.client.get_grouped_daily_aggs(
                    date=fallback_1m_date,
                    adjusted=True
                )
                
                for agg in fallback_1m_data:
                    if hasattr(agg, 'ticker') and agg.ticker in missing_tickers:
                        if not momentum_data[agg.ticker]['price_1m']:
                            momentum_data[agg.ticker]['price_1m'] = float(agg.close)
                            logger.debug(f"Found 1m price for {agg.ticker} on {fallback_1m_date}")
            except:
                pass
            
            # Update missing tickers list
            missing_tickers = [t for t in missing_tickers 
                             if not momentum_data[t]['price_12m'] or not momentum_data[t]['price_1m']]
        
        return momentum_data

    def _fetch_bulk_momentum_data_fallback(
        self, 
        tickers: List[str], 
        calculation_date: datetime
    ) -> Dict[str, Dict[str, Optional[float]]]:
        """
        Fallback to the old method if grouped daily API fails
        """
        logger.warning("Using fallback method - this will be slower")
        
        twelve_months_ago = calculation_date - timedelta(days=365)
        one_month_ago = calculation_date - timedelta(days=30)
        
        # Use broader date range to capture both periods in one API call
        start_date = twelve_months_ago - timedelta(days=30)  # Buffer for weekends/holidays
        end_date = calculation_date + timedelta(days=7)  # Buffer for current date
        
        logger.info(f"Fallback: fetching momentum data for {len(tickers)} stocks from {start_date} to {end_date}")
        
        # Fetch all data with batching
        all_data = self.fetch_multiple_stocks(
            tickers=tickers,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            batch_size=5,  # Smaller batch size for bulk operations
            delay_between_batches=15
        )
        
        # Extract prices for momentum calculation
        momentum_data = {}
        
        for ticker in tickers:
            data = all_data.get(ticker, [])
            if not data:
                momentum_data[ticker] = {'price_12m': None, 'price_1m': None}
                continue
            
            # Convert to DataFrame for easier date filtering
            df = pd.DataFrame(data)
            if df.empty:
                momentum_data[ticker] = {'price_12m': None, 'price_1m': None}
                continue
            
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            
            # Find closest prices to target dates
            price_12m = self._find_closest_price(df, twelve_months_ago)
            price_1m = self._find_closest_price(df, one_month_ago)
            
            momentum_data[ticker] = {
                'price_12m': price_12m,
                'price_1m': price_1m
            }
            
            logger.debug(f"Momentum data for {ticker}: 12m=${price_12m}, 1m=${price_1m}")
        
        return momentum_data

    def _find_closest_price(self, df: pd.DataFrame, target_date: datetime, tolerance_days: int = 7) -> Optional[float]:
        """Find the closest price to a target date within tolerance"""
        if df.empty:
            return None
        
        target_date = pd.Timestamp(target_date)
        df['date_diff'] = abs(df['date'] - target_date)
        
        # Filter within tolerance
        tolerance = pd.Timedelta(days=tolerance_days)
        within_tolerance = df[df['date_diff'] <= tolerance]
        
        if within_tolerance.empty:
            return None
        
        # Return closest price
        closest_row = within_tolerance.loc[within_tolerance['date_diff'].idxmin()]
        return float(closest_row['close'])

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