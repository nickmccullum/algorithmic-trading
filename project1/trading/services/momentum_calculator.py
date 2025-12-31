from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np
import logging

from trading.models import Stock, PriceData, MomentumScore
from trading.services.massive_client import get_massive_client

logger = logging.getLogger(__name__)


class MomentumCalculator:
    def __init__(self):
        self.massive_client = get_massive_client()
        self.lookback_months = getattr(settings, 'MOMENTUM_LOOKBACK_MONTHS', 12)
        self.skip_months = getattr(settings, 'MOMENTUM_SKIP_MONTHS', 1)

    def calculate_momentum_for_stock(
        self, 
        stock: Stock, 
        calculation_date: datetime = None
    ) -> Optional[Decimal]:
        if calculation_date is None:
            calculation_date = timezone.now().date()

        # Get required dates
        twelve_months_ago = calculation_date - timedelta(days=365)
        one_month_ago = calculation_date - timedelta(days=30)

        try:
            # Try to get prices from database first
            price_12m = self._get_price_from_db(stock, twelve_months_ago, tolerance_days=7)
            price_1m = self._get_price_from_db(stock, one_month_ago, tolerance_days=7)

            # If not in database, fetch from API
            if not price_12m:
                price_12m = self._get_price_from_api(stock.ticker, twelve_months_ago)
            
            if not price_1m:
                price_1m = self._get_price_from_api(stock.ticker, one_month_ago)

            if price_12m and price_1m and price_12m > 0:
                momentum = (price_1m - price_12m) / price_12m
                return Decimal(str(momentum))

            logger.warning(f"Could not calculate momentum for {stock.ticker}: "
                         f"price_12m={price_12m}, price_1m={price_1m}")
            return None

        except ValueError:
            logger.error(f"Error calculating momentum for {stock.ticker}: Invalid price data")
            return None

    def _get_price_from_db(
        self, 
        stock: Stock, 
        target_date: datetime, 
        tolerance_days: int = 7
    ) -> Optional[Decimal]:
        start_date = target_date - timedelta(days=tolerance_days)
        end_date = target_date + timedelta(days=tolerance_days)

        price_data = stock.price_data.filter(
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date').first()

        return price_data.close if price_data else None

    def _get_price_from_api(
        self, 
        ticker: str, 
        target_date: datetime
    ) -> Optional[Decimal]:
        try:
            price = self.massive_client.get_price_on_date(ticker, target_date)
            return Decimal(str(price)) if price else None
        except (ValueError, TypeError):
            logger.error(f"Error fetching price from API for {ticker}: Invalid API response")
            return None

    def calculate_momentum_scores_bulk(
        self, 
        stock_list: List[Stock] = None, 
        calculation_date: datetime = None
    ) -> List[MomentumScore]:
        if calculation_date is None:
            calculation_date = timezone.now().date()

        if stock_list is None:
            stock_list = Stock.objects.filter(is_active=True)

        momentum_scores = []
        
        logger.info(f"Calculating momentum scores for {len(stock_list)} stocks")

        for i, stock in enumerate(stock_list):
            try:
                momentum = self.calculate_momentum_for_stock(stock, calculation_date)
                
                if momentum is not None:
                    # Create or update momentum score
                    momentum_score, created = MomentumScore.objects.update_or_create(
                        stock=stock,
                        calculation_date=calculation_date,
                        defaults={
                            'momentum_score': momentum,
                            'period_start': calculation_date - timedelta(days=365),
                            'period_end': calculation_date - timedelta(days=30),
                        }
                    )
                    momentum_scores.append(momentum_score)
                    
                    if created:
                        logger.info(f"Created momentum score for {stock.ticker}: {momentum}")
                    else:
                        logger.info(f"Updated momentum score for {stock.ticker}: {momentum}")

                # Log progress every 10 stocks
                if (i + 1) % 10 == 0:
                    logger.info(f"Processed {i + 1}/{len(stock_list)} stocks")

            except (ValueError, TypeError):
                logger.error(f"Error processing {stock.ticker}: Invalid momentum calculation data")

        return momentum_scores

    def rank_stocks_by_momentum(
        self, 
        calculation_date: datetime = None
    ) -> List[MomentumScore]:
        if calculation_date is None:
            calculation_date = timezone.now().date()

        # Calculate quintiles for the date
        MomentumScore.calculate_quintiles_for_date(calculation_date)

        # Return ranked scores
        return MomentumScore.objects.filter(
            calculation_date=calculation_date
        ).order_by('-momentum_score')

    def get_top_quintile_stocks(
        self, 
        calculation_date: datetime = None
    ) -> List[Stock]:
        if calculation_date is None:
            calculation_date = timezone.now().date()

        momentum_scores = MomentumScore.objects.filter(
            calculation_date=calculation_date,
            is_top_quintile=True
        ).select_related('stock').order_by('-momentum_score')

        return [score.stock for score in momentum_scores]

    def get_bottom_quintile_stocks(
        self, 
        calculation_date: datetime = None
    ) -> List[Stock]:
        if calculation_date is None:
            calculation_date = timezone.now().date()

        momentum_scores = MomentumScore.objects.filter(
            calculation_date=calculation_date,
            quintile=5
        ).select_related('stock').order_by('momentum_score')

        return [score.stock for score in momentum_scores]

    def update_stock_universe(self, tickers: List[str] = None) -> List[Stock]:
        if tickers is None:
            tickers = self.massive_client.get_sp500_tickers()

        stocks = []
        for ticker in tickers:
            stock, created = Stock.objects.get_or_create(
                ticker=ticker,
                defaults={'name': ticker, 'is_active': True}
            )
            stocks.append(stock)
            
            if created:
                logger.info(f"Added new stock: {ticker}")

        return stocks

    def backfill_price_data(
        self, 
        stock: Stock, 
        days_back: int = 420
    ) -> int:
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days_back)

        try:
            # Check what data we already have
            existing_data = stock.price_data.filter(
                date__gte=start_date
            ).values_list('date', flat=True)
            
            # Fetch data from API
            api_data = self.massive_client.fetch_stock_data(
                ticker=stock.ticker,
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )

            new_records = 0
            for data_point in api_data:
                if data_point['date'] not in existing_data:
                    PriceData.objects.create(
                        stock=stock,
                        date=data_point['date'],
                        open_price=Decimal(str(data_point['open'])),
                        high=Decimal(str(data_point['high'])),
                        low=Decimal(str(data_point['low'])),
                        close=Decimal(str(data_point['close'])),
                        volume=data_point['volume'],
                        adjusted_close=Decimal(str(data_point['close']))
                    )
                    new_records += 1

            logger.info(f"Backfilled {new_records} price records for {stock.ticker}")
            return new_records

        except (ValueError, TypeError):
            logger.error(f"Error backfilling data for {stock.ticker}: Invalid price data format")
            return 0

    def get_momentum_statistics(
        self, 
        calculation_date: datetime = None
    ) -> Dict:
        if calculation_date is None:
            calculation_date = timezone.now().date()

        scores = MomentumScore.objects.filter(calculation_date=calculation_date)
        
        if not scores.exists():
            return {}

        momentum_values = [float(score.momentum_score) for score in scores]
        
        return {
            'total_stocks': len(momentum_values),
            'mean_momentum': np.mean(momentum_values),
            'median_momentum': np.median(momentum_values),
            'std_momentum': np.std(momentum_values),
            'min_momentum': min(momentum_values),
            'max_momentum': max(momentum_values),
            'top_quintile_threshold': np.percentile(momentum_values, 80),
            'bottom_quintile_threshold': np.percentile(momentum_values, 20)
        }

    def validate_momentum_calculation(
        self, 
        stock: Stock, 
        calculation_date: datetime = None
    ) -> Dict:
        if calculation_date is None:
            calculation_date = timezone.now().date()

        twelve_months_ago = calculation_date - timedelta(days=365)
        one_month_ago = calculation_date - timedelta(days=30)

        validation_result = {
            'stock': stock.ticker,
            'calculation_date': calculation_date,
            'has_sufficient_data': False,
            'price_12m': None,
            'price_1m': None,
            'momentum_score': None,
            'data_points_available': 0
        }

        # Check data availability
        data_count = stock.price_data.filter(
            date__gte=twelve_months_ago,
            date__lte=calculation_date
        ).count()
        
        validation_result['data_points_available'] = data_count
        validation_result['has_sufficient_data'] = data_count >= 280

        # Get prices and calculate momentum
        try:
            validation_result['momentum_score'] = self.calculate_momentum_for_stock(
                stock, calculation_date
            )
        except (ValueError, TypeError) as e:
            validation_result['error'] = str(e)

        return validation_result


def get_momentum_calculator() -> MomentumCalculator:
    return MomentumCalculator()