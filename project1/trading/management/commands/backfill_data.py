from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import datetime, timedelta
from trading.services.momentum_calculator import get_momentum_calculator
from trading.models import Stock, PriceData
from decimal import Decimal


class Command(BaseCommand):
    help = 'Backfill historical price data for stocks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tickers',
            type=str,
            nargs='+',
            help='Specific stock tickers to backfill (optional)',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=420,
            help='Number of days to backfill (default: 420)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Number of stocks to process per batch (default: 10)',
        )
        parser.add_argument(
            '--update-universe',
            action='store_true',
            help='Update the stock universe before backfilling',
        )

    def handle(self, *args, **options):
        try:
            momentum_calculator = get_momentum_calculator()

            # Update stock universe if requested
            if options['update_universe']:
                self.stdout.write('Updating stock universe...')
                stocks = momentum_calculator.update_stock_universe()
                self.stdout.write(
                    self.style.SUCCESS(f'Updated stock universe with {len(stocks)} stocks')
                )

            # Get stocks to process
            if options['tickers']:
                stocks = Stock.objects.filter(
                    ticker__in=options['tickers'],
                    is_active=True
                )
                if not stocks:
                    raise CommandError('No matching active stocks found')
            else:
                stocks = Stock.objects.filter(is_active=True)

            total_stocks = len(stocks)
            batch_size = options['batch_size']
            days_back = options['days']

            self.stdout.write(f'Backfilling {days_back} days of data for {total_stocks} stocks')

            total_new_records = 0
            processed_stocks = 0

            # Process stocks in batches
            for i in range(0, total_stocks, batch_size):
                batch = stocks[i:i + batch_size]
                
                for stock in batch:
                    try:
                        # Check current data availability
                        existing_count = stock.price_data.count()
                        
                        self.stdout.write(f'Processing {stock.ticker} (current: {existing_count} records)')
                        
                        # Backfill data
                        new_records = momentum_calculator.backfill_price_data(stock, days_back)
                        total_new_records += new_records
                        processed_stocks += 1
                        
                        if new_records > 0:
                            self.stdout.write(
                                f'  Added {new_records} new records for {stock.ticker}'
                            )
                        else:
                            self.stdout.write(f'  No new records needed for {stock.ticker}')
                        
                        # Validate data sufficiency for momentum calculation
                        total_records = stock.price_data.count()
                        if total_records < 280:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'  Warning: {stock.ticker} has only {total_records} records '
                                    '(minimum 280 recommended for momentum calculation)'
                                )
                            )

                    except (ValueError, TypeError) as e:
                        self.stdout.write(
                            self.style.ERROR(f'Error processing {stock.ticker}: {str(e)}')
                        )

                # Progress update
                self.stdout.write(
                    f'Batch complete: {min(i + batch_size, total_stocks)}/{total_stocks} stocks processed'
                )

            # Summary
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nBackfill complete: {total_new_records} new records added '
                    f'across {processed_stocks} stocks'
                )
            )

            # Show data statistics
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=days_back)
            
            total_records = PriceData.objects.filter(
                date__gte=start_date,
                date__lte=end_date
            ).count()
            
            stocks_with_data = PriceData.objects.filter(
                date__gte=start_date,
                date__lte=end_date
            ).values('stock').distinct().count()

            self.stdout.write(f'\nData Statistics:')
            self.stdout.write(f'Date range: {start_date} to {end_date}')
            self.stdout.write(f'Total price records: {total_records:,}')
            self.stdout.write(f'Stocks with data: {stocks_with_data}')

            # Check for stocks with insufficient data
            insufficient_data_stocks = []
            for stock in stocks:
                recent_data_count = stock.price_data.filter(
                    date__gte=start_date
                ).count()
                if recent_data_count < 280:
                    insufficient_data_stocks.append((stock.ticker, recent_data_count))

            if insufficient_data_stocks:
                self.stdout.write(
                    self.style.WARNING(
                        f'\nStocks with insufficient data ({len(insufficient_data_stocks)}):'
                    )
                )
                for ticker, count in insufficient_data_stocks[:10]:  # Show first 10
                    self.stdout.write(f'  {ticker}: {count} records')

        except ValueError as e:
            raise CommandError(f'Error backfilling data: {str(e)}')