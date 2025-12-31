from django.conf import settings
from typing import List, Dict, Optional
import logging
from decimal import Decimal
from datetime import datetime
from snaptrade_client import SnapTrade

from portfolio.models import Portfolio, Position, Trade
from trading.models import Stock

logger = logging.getLogger(__name__)


class TradingExecutor:
    def __init__(self):
        # Initialize SnapTrade SDK client
        self.snaptrade = SnapTrade(
            consumer_key=settings.SNAPTRADE_CLIENT_SECRET,
            client_id=settings.SNAPTRADE_CLIENT_ID,
        )

    def sync_portfolio_positions(self, portfolio: Portfolio, user_secret: str = None) -> List[Position]:
        if not portfolio.snaptrade_user_id or not portfolio.snaptrade_account_id:
            raise ValueError("Portfolio must have SnapTrade user and account IDs")
        
        if not user_secret:
            raise ValueError("SnapTrade user secret is required for API operations")

        try:
            # Get positions from SnapTrade using SDK
            positions_response = self.snaptrade.account_information.get_user_account_positions(
                user_id=portfolio.snaptrade_user_id,
                user_secret=user_secret,
                account_id=portfolio.snaptrade_account_id
            )

            # Access response body (SDK returns ApiResponseFor200 object)
            positions_data = positions_response.body
            synced_positions = []
            
            for pos_data in positions_data:
                # SnapTrade has nested symbol structure: symbol -> symbol -> raw_symbol
                symbol = pos_data.get('symbol', {}).get('symbol', {}).get('raw_symbol', '')
                quantity = float(pos_data.get('units', 0))
                average_cost = float(pos_data.get('average_purchase_price', 0))
                current_price = float(pos_data.get('price', 0))

                if not symbol or quantity <= 0:
                    continue

                # Get or create stock
                stock, _ = Stock.objects.get_or_create(
                    ticker=symbol,
                    defaults={'name': symbol, 'is_active': True}
                )

                # Update or create position
                position, created = Position.objects.update_or_create(
                    portfolio=portfolio,
                    stock=stock,
                    defaults={
                        'quantity': quantity,
                        'average_cost': Decimal(str(average_cost)),
                        'current_price': Decimal(str(current_price))
                    }
                )

                position.update_current_value()
                position.save()
                synced_positions.append(position)

                logger.info(f"{'Created' if created else 'Updated'} position: {symbol} - {quantity} shares")

            # Update portfolio cash balance using SDK
            balance_response = self.snaptrade.account_information.get_user_account_balance(
                user_id=portfolio.snaptrade_user_id,
                user_secret=user_secret,
                account_id=portfolio.snaptrade_account_id
            )

            # Access response body (SDK returns ApiResponseFor200 object)
            balance_data = balance_response.body
            if balance_data and isinstance(balance_data, list) and len(balance_data) > 0:
                # SnapTrade returns balance as a list, get the first USD account
                balance_item = balance_data[0]
                cash_balance = float(balance_item.get('cash', 0))
                portfolio.current_cash = Decimal(str(cash_balance))
                portfolio.calculate_total_value()
                portfolio.save()
                logger.info(f"Updated portfolio cash balance to ${cash_balance}")

            return synced_positions

        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Error syncing portfolio positions: {str(e)}")
            raise

    def execute_buy_orders(self, portfolio: Portfolio, buy_list: List[Stock], total_value: Decimal, user_secret: str = None) -> List[Trade]:
        if not buy_list:
            return []
        
        if not user_secret:
            raise ValueError("SnapTrade user secret is required for trading operations")

        # Calculate equal weight allocation
        allocation_per_stock = total_value / len(buy_list)
        executed_trades = []

        for stock in buy_list:
            try:
                # Get current price (simplified - in production, use real-time quotes)
                current_price = self._get_current_stock_price(stock.ticker)
                if not current_price:
                    logger.warning(f"Could not get current price for {stock.ticker}")
                    continue

                # Calculate quantity to buy
                quantity = int(allocation_per_stock / current_price)
                if quantity <= 0:
                    continue

                # Create trade record
                trade = Trade.objects.create(
                    portfolio=portfolio,
                    stock=stock,
                    trade_type='BUY',
                    quantity=quantity,
                    price=current_price,
                    status='PENDING'
                )

                # Place order via SnapTrade SDK using place_force_order
                order_response = self.snaptrade.trading.place_force_order(
                    user_id=portfolio.snaptrade_user_id,
                    user_secret=user_secret,
                    body={
                        'account_id': portfolio.snaptrade_account_id,
                        'action': 'BUY',
                        'order_type': 'Market',
                        'price': None,  # Market order
                        'stop': None,
                        'time_in_force': 'Day',
                        'units': quantity,
                        'symbol': stock.ticker
                    }
                )

                # Handle response body (SDK returns ApiResponseFor200 object)
                order_result = order_response.body if hasattr(order_response, 'body') else order_response

                # Update trade with order details
                trade.external_order_id = order_result.get('id', '') if isinstance(order_result, dict) else ''
                trade.status = 'SUBMITTED'
                trade.submitted_at = datetime.now()
                trade.save()

                executed_trades.append(trade)
                logger.info(f"Submitted buy order: {quantity} shares of {stock.ticker}")

            except (ValueError, TypeError, KeyError) as e:
                logger.error(f"Error executing buy order for {stock.ticker}: {str(e)}")

        return executed_trades

    def execute_sell_orders(self, portfolio: Portfolio, sell_list: List[Stock], user_secret: str = None) -> List[Trade]:
        if not sell_list:
            return []
        
        if not user_secret:
            raise ValueError("SnapTrade user secret is required for trading operations")

        executed_trades = []
        current_positions = {
            pos.stock.ticker: pos for pos in portfolio.get_current_positions()
        }

        for stock in sell_list:
            if stock.ticker not in current_positions:
                continue

            position = current_positions[stock.ticker]
            if position.quantity <= 0:
                continue

            try:
                # Create trade record
                trade = Trade.objects.create(
                    portfolio=portfolio,
                    stock=stock,
                    trade_type='SELL',
                    quantity=position.quantity,
                    price=position.current_price,
                    status='PENDING'
                )

                # Place sell order via SnapTrade SDK using place_force_order
                order_response = self.snaptrade.trading.place_force_order(
                    user_id=portfolio.snaptrade_user_id,
                    user_secret=user_secret,
                    body={
                        'account_id': portfolio.snaptrade_account_id,
                        'action': 'SELL',
                        'order_type': 'Market',
                        'price': None,  # Market order
                        'stop': None,
                        'time_in_force': 'Day',
                        'units': int(position.quantity),
                        'symbol': stock.ticker
                    }
                )

                # Handle response body (SDK returns ApiResponseFor200 object)
                order_result = order_response.body if hasattr(order_response, 'body') else order_response

                # Update trade with order details
                trade.external_order_id = order_result.get('id', '') if isinstance(order_result, dict) else ''
                trade.status = 'SUBMITTED'
                trade.submitted_at = datetime.now()
                trade.save()

                executed_trades.append(trade)
                logger.info(f"Submitted sell order: {position.quantity} shares of {stock.ticker}")

            except (ValueError, TypeError, KeyError) as e:
                logger.error(f"Error executing sell order for {stock.ticker}: {str(e)}")

        return executed_trades

    def update_trade_status(self, trade: Trade, user_secret: str = None) -> bool:
        if not trade.external_order_id or trade.status in ['FILLED', 'CANCELLED', 'REJECTED']:
            return False
        
        if not user_secret:
            raise ValueError("SnapTrade user secret is required for trade status updates")

        try:
            # Get order status using SnapTrade SDK
            order_status = self.snaptrade.trading.get_order_status(
                user_id=trade.portfolio.snaptrade_user_id,
                user_secret=user_secret,
                account_id=trade.portfolio.snaptrade_account_id,
                order_id=trade.external_order_id
            )

            old_status = trade.status
            trade.status = order_status.get('state', trade.status)
            
            if order_status.get('filled_units'):
                trade.filled_quantity = float(order_status['filled_units'])
            
            if order_status.get('executed_price'):
                trade.filled_price = Decimal(str(order_status['executed_price']))
            
            if trade.status == 'FILLED':
                trade.filled_at = datetime.now()
                trade.update_position()

            trade.save()

            if old_status != trade.status:
                logger.info(f"Trade {trade.id} status updated: {old_status} -> {trade.status}")

            return True

        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Error updating trade status for trade {trade.id}: {str(e)}")
            return False

    def _get_current_stock_price(self, ticker: str) -> Optional[Decimal]:
        # Simplified implementation - in production, use real-time price feed
        try:
            from trading.services.massive_client import get_massive_client
            massive_client = get_massive_client()
            price = massive_client.get_price_on_date(ticker, datetime.now())
            return Decimal(str(price)) if price else None
        except (ValueError, TypeError) as e:
            logger.error(f"Error getting current price for {ticker}: {str(e)}")
            return None

    def get_available_cash_for_trading(self, portfolio: Portfolio) -> Decimal:
        # Reserve 5% cash buffer
        return portfolio.current_cash * Decimal('0.95')


def get_trading_executor() -> TradingExecutor:
    return TradingExecutor()