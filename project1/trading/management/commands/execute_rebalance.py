from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import datetime
from trading.services.strategy_engine import get_strategy_engine
from portfolio.models import Portfolio


class Command(BaseCommand):
    help = 'Execute portfolio rebalancing based on momentum strategy'

    def add_arguments(self, parser):
        parser.add_argument(
            '--portfolio',
            type=str,
            required=True,
            help='Portfolio name to rebalance',
        )
        parser.add_argument(
            '--date',
            type=str,
            help='Rebalance date (YYYY-MM-DD format). Defaults to today.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate rebalance without executing trades',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force rebalance even if not scheduled',
        )

    def handle(self, *args, **options):
        try:
            # Get portfolio
            try:
                portfolio = Portfolio.objects.get(name=options['portfolio'])
            except Portfolio.DoesNotExist:
                raise CommandError(f'Portfolio "{options["portfolio"]}" not found')

            # Parse rebalance date
            calculation_date = timezone.now().date()
            if options['date']:
                try:
                    calculation_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
                except ValueError:
                    raise CommandError('Invalid date format. Use YYYY-MM-DD.')

            self.stdout.write(f'Rebalancing portfolio "{portfolio.name}" for {calculation_date}')

            # Initialize strategy engine
            strategy_engine = get_strategy_engine(portfolio)

            # Validate setup
            validation = strategy_engine.validate_strategy_setup()
            if not validation['is_valid']:
                self.stdout.write(self.style.ERROR('Strategy setup validation failed:'))
                for issue in validation['issues']:
                    self.stdout.write(f'  - {issue}')
                raise CommandError('Fix validation issues before proceeding')

            if validation['warnings']:
                self.stdout.write(self.style.WARNING('Warnings:'))
                for warning in validation['warnings']:
                    self.stdout.write(f'  - {warning}')

            # Check if rebalance is needed
            if not options['force'] and not strategy_engine.should_rebalance():
                self.stdout.write(
                    self.style.WARNING(
                        'Rebalance not scheduled based on frequency settings. Use --force to override.'
                    )
                )
                return

            # Sync current positions
            self.stdout.write('Syncing current positions...')
            try:
                synced_positions = strategy_engine.trading_executor.sync_portfolio_positions(portfolio)
                self.stdout.write(f'Synced {len(synced_positions)} positions')
            except (ValueError, TypeError) as e:
                self.stdout.write(
                    self.style.WARNING(f'Could not sync positions: {str(e)}')
                )

            if options['dry_run']:
                self.stdout.write(self.style.WARNING('DRY RUN - No trades will be executed'))
                
                # Generate signals but don't execute
                buy_signals, sell_signals = strategy_engine.generate_trading_signals(calculation_date)
                
                self.stdout.write(f'\nGenerated {len(sell_signals)} sell signals:')
                for signal in sell_signals[:10]:  # Show first 10
                    self.stdout.write(
                        f'  SELL {signal.stock.ticker}: {signal.target_quantity} shares '
                        f'(${signal.target_value:.2f}) - {signal.reason}'
                    )
                
                self.stdout.write(f'\nGenerated {len(buy_signals)} buy signals:')
                for signal in buy_signals[:10]:  # Show first 10
                    self.stdout.write(
                        f'  BUY {signal.stock.ticker}: ${signal.target_value:.2f} - {signal.reason}'
                    )
                
                # Clean up signals since this was a dry run
                for signal in buy_signals + sell_signals:
                    signal.delete()
                
                return

            # Execute rebalance
            self.stdout.write('Executing rebalance...')
            rebalance_event = strategy_engine.execute_rebalance(calculation_date)

            # Display results
            self.stdout.write('\nRebalance Results:')
            self.stdout.write(f'Status: {rebalance_event.execution_status}')
            self.stdout.write(f'Stocks analyzed: {rebalance_event.total_stocks_analyzed}')
            self.stdout.write(f'Buy signals: {rebalance_event.buy_signals_generated}')
            self.stdout.write(f'Sell signals: {rebalance_event.sell_signals_generated}')
            
            if rebalance_event.total_portfolio_value:
                self.stdout.write(f'Portfolio value: ${rebalance_event.total_portfolio_value:,.2f}')

            if rebalance_event.execution_status == 'COMPLETED':
                self.stdout.write(self.style.SUCCESS('Rebalance completed successfully'))
            elif rebalance_event.execution_status == 'FAILED':
                self.stdout.write(self.style.ERROR(f'Rebalance failed: {rebalance_event.error_message}'))

            # Show current portfolio status
            portfolio.refresh_from_db()
            active_positions = portfolio.positions.filter(quantity__gt=0).count()
            self.stdout.write(f'\nCurrent portfolio status:')
            self.stdout.write(f'Cash: ${portfolio.current_cash:,.2f}')
            self.stdout.write(f'Total value: ${portfolio.total_value:,.2f}')
            self.stdout.write(f'Active positions: {active_positions}')

        except ValueError as e:
            raise CommandError(f'Error executing rebalance: {str(e)}')