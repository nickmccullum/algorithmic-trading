from datetime import datetime, timedelta
from decimal import Decimal
from massive import RESTClient
from django.conf import settings
from .models import Index, MarketData, MovingAverage, TradingSignal, ETF
import pandas as pd


class MassiveAPIService:
    def __init__(self):
        self.client = RESTClient(getattr(settings, 'MASSIVE_API_KEY', 'your_api_key_here'))
    
    def fetch_index_data(self, index, start_date, end_date):
        """Fetch historical data for an index from Massive API"""
        try:
            aggs = []
            for agg in self.client.list_aggs(
                index.massive_ticker,
                1,
                "day",
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
                limit=50000,
            ):
                aggs.append(agg)
            
            # Save data to database
            market_data_objects = []
            for agg in aggs:
                market_data, created = MarketData.objects.get_or_create(
                    index=index,
                    date=datetime.fromtimestamp(agg.timestamp / 1000).date(),
                    defaults={
                        'open_price': Decimal(str(agg.open)),
                        'high_price': Decimal(str(agg.high)),
                        'low_price': Decimal(str(agg.low)),
                        'close_price': Decimal(str(agg.close)),
                        'volume': agg.volume,
                    }
                )
                if created:
                    market_data_objects.append(market_data)
            
            return len(market_data_objects)
        
        except Exception as e:
            print(f"Error fetching data for {index.massive_ticker}: {e}")
            return 0
    
    def fetch_all_indices_data(self, days_back=300):
        """Fetch data for all configured indices"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days_back)
        
        results = {}
        for index in Index.objects.all():
            count = self.fetch_index_data(index, start_date, end_date)
            results[index.massive_ticker] = count
        
        return results


class MovingAverageService:
    @staticmethod
    def calculate_moving_averages(index, days_back=300):
        """Calculate 50-day and 200-day moving averages for an index"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days_back)
        
        # Get market data ordered by date
        market_data = MarketData.objects.filter(
            index=index,
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date')
        
        if market_data.count() < 200:
            print(f"Insufficient data for {index.massive_ticker}. Need at least 200 days.")
            return 0
        
        # Convert to DataFrame for easier calculation
        data = []
        for md in market_data:
            data.append({
                'date': md.date,
                'close': float(md.close_price)
            })
        
        df = pd.DataFrame(data)
        df['ma_50'] = df['close'].rolling(window=50).mean()
        df['ma_200'] = df['close'].rolling(window=200).mean()
        
        # Save moving averages to database
        created_count = 0
        for _, row in df.iterrows():
            if pd.notna(row['ma_50']) and pd.notna(row['ma_200']):
                moving_avg, created = MovingAverage.objects.get_or_create(
                    index=index,
                    date=row['date'],
                    defaults={
                        'ma_50': Decimal(str(round(row['ma_50'], 4))),
                        'ma_200': Decimal(str(round(row['ma_200'], 4))),
                    }
                )
                if created:
                    created_count += 1
        
        return created_count
    
    @staticmethod
    def calculate_all_moving_averages(days_back=300):
        """Calculate moving averages for all indices"""
        results = {}
        for index in Index.objects.all():
            count = MovingAverageService.calculate_moving_averages(index, days_back)
            results[index.massive_ticker] = count
        return results


class TradingSignalService:
    @staticmethod
    def detect_crossovers(index, days_back=30):
        """Detect golden cross and death cross signals for an index"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days_back)
        
        # Get moving averages data
        ma_data = MovingAverage.objects.filter(
            index=index,
            date__gte=start_date,
            date__lte=end_date,
            ma_50__isnull=False,
            ma_200__isnull=False
        ).order_by('date')
        
        if ma_data.count() < 2:
            return []
        
        signals = []
        ma_list = list(ma_data)
        
        for i in range(1, len(ma_list)):
            prev_ma = ma_list[i-1]
            curr_ma = ma_list[i]
            
            # Golden Cross: 50-day MA crosses above 200-day MA
            if (prev_ma.ma_50 <= prev_ma.ma_200 and 
                curr_ma.ma_50 > curr_ma.ma_200):
                
                # Get the corresponding market data for close price
                market_data = MarketData.objects.filter(
                    index=index,
                    date=curr_ma.date
                ).first()
                
                if market_data:
                    signal = TradingSignal(
                        index=index,
                        etf=index.etf,
                        signal_type='BUY',
                        signal_date=curr_ma.date,
                        ma_50=curr_ma.ma_50,
                        ma_200=curr_ma.ma_200,
                        close_price=market_data.close_price
                    )
                    signals.append(signal)
            
            # Death Cross: 50-day MA crosses below 200-day MA
            elif (prev_ma.ma_50 >= prev_ma.ma_200 and 
                  curr_ma.ma_50 < curr_ma.ma_200):
                
                market_data = MarketData.objects.filter(
                    index=index,
                    date=curr_ma.date
                ).first()
                
                if market_data:
                    signal = TradingSignal(
                        index=index,
                        etf=index.etf,
                        signal_type='SELL',
                        signal_date=curr_ma.date,
                        ma_50=curr_ma.ma_50,
                        ma_200=curr_ma.ma_200,
                        close_price=market_data.close_price
                    )
                    signals.append(signal)
        
        # Save signals to database
        for signal in signals:
            # Check if signal already exists
            existing_signal = TradingSignal.objects.filter(
                index=signal.index,
                signal_type=signal.signal_type,
                signal_date=signal.signal_date
            ).first()
            
            if not existing_signal:
                signal.save()
        
        return signals
    
    @staticmethod
    def detect_all_signals(days_back=30):
        """Detect signals for all indices"""
        results = {}
        for index in Index.objects.all():
            signals = TradingSignalService.detect_crossovers(index, days_back)
            results[index.massive_ticker] = len(signals)
        return results