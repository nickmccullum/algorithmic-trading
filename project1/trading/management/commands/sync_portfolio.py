from django.core.management.base import BaseCommand, CommandError
from trading.services.snaptrade_client import get_trading_executor
from portfolio.models import Portfolio, Trade


class Command(BaseCommand):
    help = 'Sync portfolio positions and update trade statuses'

    def add_arguments(self, parser):
        parser.add_argument(
            '--portfolio',
            type=str,
            required=True,
            help='Portfolio name to sync',
        )
        parser.add_argument(
            '--update-trades',
            action='store_true',
            help='Update status of pending trades',
        )

    def handle(self, *args, **options):
        try:
            # Get portfolio
            try:
                portfolio = Portfolio.objects.get(name=options['portfolio'])
            except Portfolio.DoesNotExist:
                raise CommandError(f'Portfolio "{options["portfolio"]}" not found')

            self.stdout.write(f'Syncing portfolio "{portfolio.name}"')

            # Check portfolio configuration
            if not portfolio.snaptrade_user_id or not portfolio.snaptrade_account_id:
                raise CommandError(
                    'Portfolio missing SnapTrade configuration. '
                    'Set snaptrade_user_id and snaptrade_account_id.'
                )

            trading_executor = get_trading_executor()

            # Sync positions
            self.stdout.write('Syncing positions from SnapTrade...')
            try:
                synced_positions = trading_executor.sync_portfolio_positions(portfolio)
                
                self.stdout.write(f'Successfully synced {len(synced_positions)} positions')
                
                # Display current positions
                if synced_positions:
                    self.stdout.write('\nCurrent positions:')
                    for position in synced_positions:
                        if position.quantity > 0:
                            pnl_color = self.style.SUCCESS if position.unrealized_pnl >= 0 else self.style.ERROR
                            self.stdout.write(
                                f'  {position.stock.ticker}: {position.quantity} shares @ '
                                f'${position.average_cost:.2f}, Current: ${position.current_price:.2f}, '
                                f'P&L: {pnl_color(f"${position.unrealized_pnl:.2f} ({position.unrealized_pnl_percent:.2f}%)")}'
                            )
                else:
                    self.stdout.write('  No active positions')

            except (ValueError, TypeError) as e:
                self.stdout.write(
                    self.style.ERROR(f'Failed to sync positions: {str(e)}')
                )

            # Update trade statuses if requested
            if options['update_trades']:
                self.stdout.write('\nUpdating trade statuses...')
                
                pending_trades = Trade.objects.filter(
                    portfolio=portfolio,
                    status__in=['SUBMITTED', 'PARTIALLY_FILLED']
                )
                
                updated_trades = 0
                for trade in pending_trades:
                    try:
                        was_updated = trading_executor.update_trade_status(trade)
                        if was_updated:
                            updated_trades += 1
                            self.stdout.write(
                                f'  Updated trade {trade.id}: {trade.trade_type} '
                                f'{trade.stock.ticker} - {trade.status}'
                            )
                    except (ValueError, TypeError) as e:
                        self.stdout.write(
                            self.style.WARNING(
                                f'  Failed to update trade {trade.id}: {str(e)}'
                            )
                        )

                self.stdout.write(f'Updated {updated_trades} trade statuses')

            # Update portfolio totals
            old_total = portfolio.total_value
            portfolio.calculate_total_value()
            portfolio.save()

            # Display portfolio summary
            self.stdout.write('\nPortfolio Summary:')
            self.stdout.write(f'Cash: ${portfolio.current_cash:,.2f}')
            self.stdout.write(f'Total Value: ${portfolio.total_value:,.2f}')
            
            if old_total > 0:
                value_change = portfolio.total_value - old_total
                change_color = self.style.SUCCESS if value_change >= 0 else self.style.ERROR
                self.stdout.write(
                    f'Value Change: {change_color(f"${value_change:,.2f}")}'
                )

            active_positions = portfolio.positions.filter(quantity__gt=0).count()
            self.stdout.write(f'Active Positions: {active_positions}')

            # Recent trades summary
            recent_trades = portfolio.trades.order_by('-created_at')[:5]
            if recent_trades:
                self.stdout.write('\nRecent Trades (last 5):')
                for trade in recent_trades:
                    status_color = (
                        self.style.SUCCESS if trade.status == 'FILLED'
                        else self.style.WARNING if trade.status in ['SUBMITTED', 'PARTIALLY_FILLED']
                        else self.style.ERROR
                    )
                    self.stdout.write(
                        f'  {trade.created_at.strftime("%Y-%m-%d %H:%M")} - '
                        f'{trade.trade_type} {trade.quantity} {trade.stock.ticker} - '
                        f'{status_color(trade.status)}'
                    )

            self.stdout.write(self.style.SUCCESS('\nSync completed successfully'))

        except ValueError as e:
            raise CommandError(f'Error syncing portfolio: {str(e)}')