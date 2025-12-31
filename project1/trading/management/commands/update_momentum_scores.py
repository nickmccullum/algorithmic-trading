from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import datetime
from trading.services.momentum_calculator import get_momentum_calculator
from trading.models import Stock


class Command(BaseCommand):
    help = 'Calculate momentum scores for all active stocks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Calculation date (YYYY-MM-DD format). Defaults to today.',
        )
        parser.add_argument(
            '--tickers',
            type=str,
            nargs='+',
            help='Specific stock tickers to update (optional)',
        )
        parser.add_argument(
            '--update-universe',
            action='store_true',
            help='Update the stock universe before calculating momentum',
        )

    def handle(self, *args, **options):
        try:
            # Parse calculation date
            calculation_date = timezone.now().date()
            if options['date']:
                try:
                    calculation_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
                except ValueError:
                    raise CommandError('Invalid date format. Use YYYY-MM-DD.')

            self.stdout.write(f'Calculating momentum scores for {calculation_date}')

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

            self.stdout.write(f'Processing {len(stocks)} stocks...')

            # Calculate momentum scores
            momentum_scores = momentum_calculator.calculate_momentum_scores_bulk(
                stock_list=list(stocks),
                calculation_date=calculation_date
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully calculated {len(momentum_scores)} momentum scores'
                )
            )

            # Rank stocks and calculate quintiles
            ranked_scores = momentum_calculator.rank_stocks_by_momentum(calculation_date)

            # Display statistics
            stats = momentum_calculator.get_momentum_statistics(calculation_date)
            if stats:
                self.stdout.write('\nMomentum Statistics:')
                self.stdout.write(f"Total stocks: {stats['total_stocks']}")
                self.stdout.write(f"Mean momentum: {stats['mean_momentum']:.4f}")
                self.stdout.write(f"Median momentum: {stats['median_momentum']:.4f}")
                self.stdout.write(f"Top quintile threshold: {stats['top_quintile_threshold']:.4f}")

            # Show top 5 and bottom 5 stocks
            self.stdout.write('\nTop 5 momentum stocks:')
            for score in ranked_scores[:5]:
                self.stdout.write(
                    f"  {score.stock.ticker}: {score.momentum_score:.4f} (Rank {score.rank})"
                )

            self.stdout.write('\nBottom 5 momentum stocks:')
            for score in ranked_scores[-5:]:
                self.stdout.write(
                    f"  {score.stock.ticker}: {score.momentum_score:.4f} (Rank {score.rank})"
                )

        except ValueError as e:
            raise CommandError(f'Error calculating momentum scores: {str(e)}')