#!/usr/bin/env python
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'momentum_trader.settings')
django.setup()

from portfolio.models import Portfolio
from trading.services.snaptrade_client import get_trading_executor

def sync_portfolio_with_snaptrade(portfolio_id):
    """Sync a specific portfolio with SnapTrade"""
    try:
        portfolio = Portfolio.objects.get(id=portfolio_id, is_active=True)
        
        if not portfolio.snaptrade_user_secret:
            print(f"Portfolio '{portfolio.name}' is not connected to SnapTrade")
            return False
            
        print(f"Syncing portfolio '{portfolio.name}' (ID: {portfolio_id}) with SnapTrade...")
        print(f"Before sync - Cash: ${portfolio.current_cash}, Total: ${portfolio.total_value}")
        
        trading_executor = get_trading_executor()
        positions = trading_executor.sync_portfolio_positions(
            portfolio=portfolio,
            user_secret=portfolio.snaptrade_user_secret
        )
        
        # Refresh from database
        portfolio.refresh_from_db()
        
        print(f"After sync - Cash: ${portfolio.current_cash}, Total: ${portfolio.total_value}")
        print(f"Synced {len(positions)} positions:")
        for pos in positions:
            print(f"  - {pos.stock.ticker}: {pos.quantity} shares @ ${pos.current_price} = ${pos.current_value}")
            
        return True
        
    except Portfolio.DoesNotExist:
        print(f"Portfolio with ID {portfolio_id} not found or not active")
        return False
    except Exception as e:
        print(f"Error syncing portfolio: {str(e)}")
        return False

def sync_all_active_portfolios():
    """Sync all active portfolios that have SnapTrade connections"""
    portfolios = Portfolio.objects.filter(is_active=True, snaptrade_user_secret__isnull=False)
    
    if not portfolios:
        print("No active portfolios with SnapTrade connections found")
        return
    
    print(f"Found {portfolios.count()} portfolios to sync...")
    
    for portfolio in portfolios:
        print(f"\n{'='*50}")
        sync_portfolio_with_snaptrade(portfolio.id)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        portfolio_id = int(sys.argv[1])
        sync_portfolio_with_snaptrade(portfolio_id)
    else:
        sync_all_active_portfolios()