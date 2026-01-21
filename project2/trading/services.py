from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from snaptrade_python_sdk import SnapTrade
from .models import TradingAccount, Trade, Portfolio
from market_data.models import ETF


class SnapTradeService:
    def __init__(self):
        # Initialize SnapTrade client
        self.client = SnapTrade(
            consumer_key=getattr(settings, 'SNAPTRADE_CONSUMER_KEY', 'your_consumer_key'),
            client_id=getattr(settings, 'SNAPTRADE_CLIENT_ID', 'your_client_id'),
        )
    
    def get_user_id(self, account):
        """Get SnapTrade user ID for account"""
        return f"user_{account.id}"
    
    def place_buy_order(self, account, etf, quantity, limit_price=None):
        """Place a buy order for an ETF"""
        try:
            user_id = self.get_user_id(account)
            
            # Create trade record
            trade = Trade.objects.create(
                account=account,
                etf=etf,
                trade_type='BUY',
                quantity=quantity,
                price=limit_price,
                status='PENDING'
            )
            
            # Place order via SnapTrade API
            order_request = {
                "account_id": account.account_id,
                "universal_symbol": {
                    "symbol": etf.ticker,
                    "exchange": "NYSE",  # Adjust based on ETF exchange
                },
                "order_type": "Limit" if limit_price else "Market",
                "time_in_force": "Day",
                "action": "BUY",
                "units": quantity,
            }
            
            if limit_price:
                order_request["price"] = float(limit_price)
            
            response = self.client.trading.place_order(
                body=order_request,
                user_id=user_id,
                user_secret=account.account_id,  # Using account_id as user_secret for simplicity
            )
            
            # Update trade record with order ID
            if hasattr(response, 'order_id'):
                trade.order_id = response.order_id
                trade.status = 'EXECUTED'
                trade.executed_at = timezone.now()
                trade.save()
                
                # Update portfolio
                self._update_portfolio(account, etf, quantity, limit_price or response.price, 'BUY')
                
                return {
                    'success': True,
                    'order_id': response.order_id,
                    'trade_id': trade.id
                }
            else:
                trade.status = 'FAILED'
                trade.save()
                return {
                    'success': False,
                    'error': 'Order placement failed'
                }
                
        except Exception as e:
            if 'trade' in locals():
                trade.status = 'FAILED'
                trade.save()
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def place_sell_order(self, account, etf, limit_price=None):
        """Place a sell order for all holdings of an ETF"""
        try:
            # Get current portfolio position
            portfolio = Portfolio.objects.filter(
                account=account,
                etf=etf,
                quantity__gt=0
            ).first()
            
            if not portfolio:
                return {
                    'success': False,
                    'error': f'No holdings found for {etf.ticker}'
                }
            
            user_id = self.get_user_id(account)
            quantity = portfolio.quantity
            
            # Create trade record
            trade = Trade.objects.create(
                account=account,
                etf=etf,
                trade_type='SELL',
                quantity=quantity,
                price=limit_price,
                status='PENDING'
            )
            
            # Place order via SnapTrade API
            order_request = {
                "account_id": account.account_id,
                "universal_symbol": {
                    "symbol": etf.ticker,
                    "exchange": "NYSE",  # Adjust based on ETF exchange
                },
                "order_type": "Limit" if limit_price else "Market",
                "time_in_force": "Day",
                "action": "SELL",
                "units": quantity,
            }
            
            if limit_price:
                order_request["price"] = float(limit_price)
            
            response = self.client.trading.place_order(
                body=order_request,
                user_id=user_id,
                user_secret=account.account_id,
            )
            
            # Update trade record with order ID
            if hasattr(response, 'order_id'):
                trade.order_id = response.order_id
                trade.status = 'EXECUTED'
                trade.executed_at = timezone.now()
                trade.save()
                
                # Update portfolio
                self._update_portfolio(account, etf, quantity, limit_price or response.price, 'SELL')
                
                return {
                    'success': True,
                    'order_id': response.order_id,
                    'trade_id': trade.id
                }
            else:
                trade.status = 'FAILED'
                trade.save()
                return {
                    'success': False,
                    'error': 'Order placement failed'
                }
                
        except Exception as e:
            if 'trade' in locals():
                trade.status = 'FAILED'
                trade.save()
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def _update_portfolio(self, account, etf, quantity, price, action):
        """Update portfolio position after trade"""
        portfolio, created = Portfolio.objects.get_or_create(
            account=account,
            etf=etf,
            defaults={'quantity': 0, 'avg_cost': Decimal('0.00')}
        )
        
        if action == 'BUY':
            # Calculate new average cost
            total_cost = (portfolio.quantity * (portfolio.avg_cost or 0)) + (quantity * Decimal(str(price)))
            total_quantity = portfolio.quantity + quantity
            
            portfolio.quantity = total_quantity
            portfolio.avg_cost = total_cost / total_quantity if total_quantity > 0 else Decimal('0.00')
        
        elif action == 'SELL':
            portfolio.quantity -= quantity
            if portfolio.quantity <= 0:
                portfolio.quantity = 0
                portfolio.avg_cost = Decimal('0.00')
        
        portfolio.last_updated = timezone.now()
        portfolio.save()
    
    def sync_portfolio(self, account):
        """Sync portfolio positions with SnapTrade"""
        try:
            user_id = self.get_user_id(account)
            
            # Get positions from SnapTrade
            positions = self.client.account_information.get_user_account_positions(
                user_id=user_id,
                user_secret=account.account_id,
                account_id=account.account_id,
            )
            
            synced_count = 0
            
            for position in positions:
                # Find corresponding ETF
                etf = ETF.objects.filter(ticker=position.symbol).first()
                if etf:
                    portfolio, created = Portfolio.objects.get_or_create(
                        account=account,
                        etf=etf,
                        defaults={
                            'quantity': 0,
                            'avg_cost': Decimal('0.00')
                        }
                    )
                    
                    portfolio.quantity = int(position.units)
                    if hasattr(position, 'average_purchase_price') and position.average_purchase_price:
                        portfolio.avg_cost = Decimal(str(position.average_purchase_price))
                    
                    portfolio.last_updated = timezone.now()
                    portfolio.save()
                    synced_count += 1
            
            return synced_count
            
        except Exception as e:
            print(f"Error syncing portfolio for {account.name}: {e}")
            return 0
    
    def sync_all_portfolios(self):
        """Sync all active trading accounts"""
        results = {}
        
        for account in TradingAccount.objects.filter(is_active=True):
            count = self.sync_portfolio(account)
            results[account.name] = count
        
        return results
    
    def get_account_info(self, account):
        """Get account information from SnapTrade"""
        try:
            user_id = self.get_user_id(account)
            
            account_info = self.client.account_information.get_user_account_details(
                user_id=user_id,
                user_secret=account.account_id,
                account_id=account.account_id,
            )
            
            return {
                'success': True,
                'account_info': account_info
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }