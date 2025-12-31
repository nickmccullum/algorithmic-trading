from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
import uuid
import os
import logging
from decimal import Decimal
from snaptrade_client import SnapTrade
from trading.models import Stock, MomentumScore, TradingSignal, RebalanceEvent
from trading.services.momentum_calculator import get_momentum_calculator
from portfolio.models import Portfolio, Position, Trade

logger = logging.getLogger(__name__)


def dashboard(request):
    # Get latest momentum calculation date
    latest_momentum = MomentumScore.objects.order_by('-calculation_date').first()
    calculation_date = latest_momentum.calculation_date if latest_momentum else timezone.now().date()
    
    # Get momentum statistics
    momentum_calculator = get_momentum_calculator()
    momentum_stats = momentum_calculator.get_momentum_statistics(calculation_date)
    
    # Get top and bottom performers
    top_performers = MomentumScore.objects.filter(
        calculation_date=calculation_date,
        is_top_quintile=True
    ).select_related('stock').order_by('-momentum_score')[:10]
    
    bottom_performers = MomentumScore.objects.filter(
        calculation_date=calculation_date,
        quintile=5
    ).select_related('stock').order_by('momentum_score')[:10]
    
    # Get recent rebalance events
    recent_rebalances = RebalanceEvent.objects.order_by('-date')[:5]
    
    # Get active portfolios
    portfolios = Portfolio.objects.filter(is_active=True)
    
    context = {
        'calculation_date': calculation_date,
        'momentum_stats': momentum_stats,
        'top_performers': top_performers,
        'bottom_performers': bottom_performers,
        'recent_rebalances': recent_rebalances,
        'portfolios': portfolios,
    }
    
    return render(request, 'trading/dashboard.html', context)


def portfolio_detail(request, portfolio_id):
    portfolio = get_object_or_404(Portfolio, id=portfolio_id)
    
    # Get current positions
    positions = portfolio.positions.filter(quantity__gt=0).select_related('stock')
    
    # Get recent trades
    recent_trades = portfolio.trades.select_related('stock').order_by('-created_at')[:20]
    
    # Get recent signals
    recent_signals = TradingSignal.objects.filter(
        stock__in=[pos.stock for pos in positions]
    ).select_related('stock', 'momentum_score').order_by('-signal_date')[:10]
    
    # Calculate performance metrics
    total_positions_value = sum(pos.current_value for pos in positions)
    total_unrealized_pnl = sum(pos.unrealized_pnl for pos in positions)
    
    context = {
        'portfolio': portfolio,
        'positions': positions,
        'recent_trades': recent_trades,
        'recent_signals': recent_signals,
        'total_positions_value': total_positions_value,
        'total_unrealized_pnl': total_unrealized_pnl,
    }
    
    return render(request, 'trading/portfolio_detail.html', context)


def momentum_scores(request):
    # Get latest calculation date
    latest_date = request.GET.get('date')
    if latest_date:
        from datetime import datetime
        calculation_date = datetime.strptime(latest_date, '%Y-%m-%d').date()
    else:
        calculation_date = timezone.now().date()
    
    if not latest_date:
        latest_momentum = MomentumScore.objects.order_by('-calculation_date').first()
        calculation_date = latest_momentum.calculation_date if latest_momentum else timezone.now().date()
    
    # Get all scores for the date
    scores = MomentumScore.objects.filter(
        calculation_date=calculation_date
    ).select_related('stock').order_by('-momentum_score')
    
    # Get available dates for dropdown
    available_dates = MomentumScore.objects.values_list(
        'calculation_date', flat=True
    ).distinct().order_by('-calculation_date')[:30]
    
    context = {
        'scores': scores,
        'calculation_date': calculation_date,
        'available_dates': available_dates,
    }
    
    return render(request, 'trading/momentum_scores.html', context)


def trading_signals(request):
    # Get recent signals
    signals = TradingSignal.objects.select_related(
        'stock', 'momentum_score'
    ).order_by('-signal_date', '-created_at')
    
    # Group by signal type for summary
    buy_signals = signals.filter(signal_type='BUY')
    sell_signals = signals.filter(signal_type='SELL')
    pending_signals = signals.filter(is_executed=False)
    
    context = {
        'signals': signals,
        'buy_signals_count': buy_signals.count(),
        'sell_signals_count': sell_signals.count(),
        'pending_signals_count': pending_signals.count(),
    }
    
    return render(request, 'trading/trading_signals.html', context)


def api_momentum_data(request):
    """API endpoint for momentum chart data"""
    days = int(request.GET.get('days', 30))
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)
    
    # Get momentum scores over time
    scores_by_date = {}
    scores = MomentumScore.objects.filter(
        calculation_date__gte=start_date,
        calculation_date__lte=end_date
    ).values('calculation_date', 'momentum_score', 'stock__ticker')
    
    for score in scores:
        date_str = score['calculation_date'].isoformat()
        if date_str not in scores_by_date:
            scores_by_date[date_str] = []
        scores_by_date[date_str].append({
            'ticker': score['stock__ticker'],
            'momentum': float(score['momentum_score'])
        })
    
    return JsonResponse(scores_by_date)


def api_portfolio_performance(request, portfolio_id):
    """API endpoint for portfolio performance chart"""
    portfolio = get_object_or_404(Portfolio, id=portfolio_id)
    days = int(request.GET.get('days', 30))
    
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)
    
    # Get performance metrics
    metrics = portfolio.performance_metrics.filter(
        date__gte=start_date,
        date__lte=end_date
    ).order_by('date')
    
    data = {
        'dates': [metric.date.isoformat() for metric in metrics],
        'values': [float(metric.total_value) for metric in metrics],
        'returns': [float(metric.cumulative_return or 0) for metric in metrics],
    }
    
    return JsonResponse(data)


def create_portfolio(request):
    portfolios = Portfolio.objects.filter(is_active=True)
    
    # This view now only shows the form
    # Actual portfolio creation happens in snaptrade_callback after OAuth
    context = {
        'portfolios': portfolios,
    }
    return render(request, 'trading/create_portfolio.html', context)


def portfolio_list(request):
    portfolios = Portfolio.objects.filter(is_active=True).order_by('name')
    
    context = {
        'portfolios': portfolios,
    }
    return render(request, 'trading/portfolio_list.html', context)


def delete_portfolio(request, portfolio_id):
    portfolio = get_object_or_404(Portfolio, id=portfolio_id)
    portfolios = Portfolio.objects.filter(is_active=True)
    
    if request.method == 'POST':
        # Check if this is a confirmation
        if request.POST.get('confirm_delete') == 'yes':
            portfolio_name = portfolio.name
            
            # Soft delete - mark as inactive instead of hard delete
            portfolio.is_active = False
            portfolio.save()
            
            messages.success(request, f'Portfolio "{portfolio_name}" has been deleted successfully.')
            return redirect('trading:portfolio_list')
        else:
            messages.error(request, 'Portfolio deletion was cancelled.')
            return redirect('trading:portfolio_detail', portfolio_id=portfolio.id)
    
    # Calculate statistics for confirmation dialog
    total_positions = portfolio.positions.filter(quantity__gt=0).count()
    total_trades = portfolio.trades.count()
    
    context = {
        'portfolio': portfolio,
        'portfolios': portfolios,
        'total_positions': total_positions,
        'total_trades': total_trades,
    }
    return render(request, 'trading/delete_portfolio.html', context)


def initiate_snaptrade_auth(request):
    """Initiate SnapTrade OAuth flow using official SDK"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    # Check if SnapTrade credentials are configured
    client_id = settings.SNAPTRADE_CLIENT_ID
    consumer_key = settings.SNAPTRADE_CLIENT_SECRET
    
    if not client_id or not consumer_key:
        return JsonResponse({
            'success': False,
            'error': 'SnapTrade API credentials not configured. Please set SNAPTRADE_CLIENT_ID and SNAPTRADE_CLIENT_SECRET in your environment variables.'
        })
    
    # Initialize SnapTrade client
    snaptrade = SnapTrade(
        consumer_key=consumer_key,
        client_id=client_id,
    )
    
    # Generate a unique user ID for SnapTrade
    user_id = str(uuid.uuid4())
    
    # Store user ID in session for callback
    request.session['snaptrade_user_id'] = user_id
    request.session['portfolio_creation_data'] = {
        'name': request.POST.get('name'),
        'description': request.POST.get('description', ''),
        'selected_brokerage': request.POST.get('selected_brokerage')
    }
    
    # Register user with SnapTrade using SDK
    register_response = snaptrade.authentication.register_snap_trade_user(
        body={
            'userId': user_id
        }
    )
    
    # Access response body (SDK returns ApiResponseFor200 object)
    user_secret = register_response.body['userSecret']
        
    request.session['snaptrade_user_secret'] = user_secret
    
    print(f"SnapTrade user registered successfully: {user_id}")
    
    # Generate OAuth URL
    redirect_uri = request.build_absolute_uri('/snaptrade/callback/')
    
    # Get brokerage and ensure it's correct format for SnapTrade
    selected_brokerage = request.POST.get('selected_brokerage', '').upper()
    if selected_brokerage == 'ALPACA':
        broker_value = 'ALPACA-PAPER'
    else:
        broker_value = selected_brokerage
        
    login_response = snaptrade.authentication.login_snap_trade_user(
        user_id=user_id,
        user_secret=user_secret,
        body={
            'broker': broker_value,
            'immediateRedirect': True,
            'customRedirect': redirect_uri,
            'connectionType': 'trade'  # Request trade permissions instead of read
        }
    )
    
    # Access response body (SDK returns ApiResponseFor200 object)
    auth_url = login_response.body['redirectURI']
    
    print(f"SnapTrade login URL generated: {auth_url}")
    
    return JsonResponse({
        'success': True,
        'auth_url': auth_url
    })


def snaptrade_callback(request):
    """Handle SnapTrade OAuth callback using official SDK"""
    user_id = request.session.get('snaptrade_user_id')
    user_secret = request.session.get('snaptrade_user_secret')
    portfolio_data = request.session.get('portfolio_creation_data')
    
    print(f"Callback received - user_id: {user_id}, has_secret: {bool(user_secret)}, has_portfolio_data: {bool(portfolio_data)}")
    
    if not user_id or not user_secret or not portfolio_data:
        print(f"Missing session data - user_id: {user_id}, user_secret: {bool(user_secret)}, portfolio_data: {portfolio_data}")
        messages.error(request, 'Invalid authentication session. Please try again.')
        return redirect('trading:create_portfolio')

    # Initialize SnapTrade client
    snaptrade = SnapTrade(
        consumer_key=settings.SNAPTRADE_CLIENT_SECRET,
        client_id=settings.SNAPTRADE_CLIENT_ID,
    )
    
    # Get user accounts using SDK
    accounts_response = snaptrade.account_information.list_user_accounts(
        user_id=user_id,
        user_secret=user_secret
    )
    
    # Access response body (SDK returns ApiResponseFor200 object)
    accounts_data = accounts_response.body
    print(f"Accounts response: {accounts_data}")
        
    if accounts_data and len(accounts_data) > 0:
        # Use first account
        account = accounts_data[0]
        account_id = account['id']
        
        print(f"Found SnapTrade account: {account_id}")
        
        # Get account balance using SDK
        balance_response = snaptrade.account_information.get_user_account_balance(
            user_id=user_id,
            user_secret=user_secret,
            account_id=account_id
        )
        
        # Access response body (SDK returns ApiResponseFor200 object)
        balance_data = balance_response.body
        print(f"Balance response: {balance_data}")
        
        # Extract cash and equity values - SnapTrade returns a list
        total_cash = 0
        total_equity = 0
        
        if isinstance(balance_data, list) and len(balance_data) > 0:
            # SnapTrade returns balance as a list, get the first USD account
            balance_item = balance_data[0]
            total_cash = float(balance_item.get('cash', 0))
            buying_power = float(balance_item.get('buying_power', 0))
            total_equity = max(total_cash, buying_power)  # Use buying power as total equity estimate
        else:
            # Fallback - use default values for paper trading
            total_cash = 100000.0  # Default paper trading amount
            total_equity = total_cash
        
        print(f"Account balance - Cash: ${total_cash}, Equity: ${total_equity}")
        
        # Create portfolio with real data
        print(f"Creating portfolio with data: {portfolio_data}")
        portfolio = Portfolio.objects.create(
            name=portfolio_data['name'],
            description=portfolio_data['description'],
            initial_cash=total_cash,
            current_cash=total_cash,
            total_value=total_equity,
            snaptrade_user_id=user_id,
            snaptrade_account_id=account_id,
            snaptrade_user_secret=user_secret
        )
        print(f"Portfolio created successfully: {portfolio.id} - {portfolio.name}")
        
        # Clean up session
        del request.session['snaptrade_user_id']
        del request.session['snaptrade_user_secret']
        del request.session['portfolio_creation_data']
        
        brokerage_name = portfolio_data['selected_brokerage'].title()
        
        # Render beautiful success page
        context = {
            'portfolio': portfolio,
            'brokerage_name': brokerage_name,
            'total_cash': total_cash,
            'total_equity': total_equity
        }
        return render(request, 'trading/snaptrade_success.html', context)
    else:
        messages.error(request, 'No accounts found. Please ensure your brokerage account is properly connected.')

    return redirect('trading:create_portfolio')


def execute_trade(request, portfolio_id):
    """Execute a manual trade for a portfolio"""
    portfolio = get_object_or_404(Portfolio, id=portfolio_id)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    stock_ticker = request.POST.get('ticker')
    trade_type = request.POST.get('trade_type')  # BUY or SELL
    quantity = int(request.POST.get('quantity', 0))
    
    if not stock_ticker or not trade_type or quantity <= 0:
        return JsonResponse({
            'success': False, 
            'error': 'Invalid trade parameters'
        })
    
    # Get or create stock
    stock, created = Stock.objects.get_or_create(
        ticker=stock_ticker.upper(),
        defaults={'name': stock_ticker.upper(), 'is_active': True}
    )
    
    # Get trading executor
    from trading.services.snaptrade_client import get_trading_executor
    trading_executor = get_trading_executor()
    
    # Execute trade based on type
    if trade_type == 'BUY':
        # Calculate total value for this trade
        from trading.services.massive_client import get_massive_client
        massive_client = get_massive_client()
        current_price = massive_client.get_price_on_date(stock_ticker, timezone.now())
        
        if not current_price:
            return JsonResponse({
                'success': False,
                'error': f'Could not get current price for {stock_ticker}'
            })
        
        total_value = Decimal(str(current_price)) * quantity
        
        # Check available cash
        available_cash = trading_executor.get_available_cash_for_trading(portfolio)
        if total_value > available_cash:
            return JsonResponse({
                'success': False,
                'error': f'Insufficient cash. Available: ${available_cash}, Required: ${total_value}'
            })
        
        # Create pending trade
        trade = Trade.objects.create(
            portfolio=portfolio,
            stock=stock,
            trade_type='BUY',
            quantity=quantity,
            price=Decimal(str(current_price)),
            status='PENDING'
        )
        
    elif trade_type == 'SELL':
        # Check if we have enough shares
        position = Position.objects.filter(
            portfolio=portfolio,
            stock=stock,
            quantity__gt=0
        ).first()
        
        if not position or position.quantity < quantity:
            available_qty = position.quantity if position else 0
            return JsonResponse({
                'success': False,
                'error': f'Insufficient shares. Available: {available_qty}, Required: {quantity}'
            })
        
        # Create pending trade
        trade = Trade.objects.create(
            portfolio=portfolio,
            stock=stock,
            trade_type='SELL',
            quantity=quantity,
            price=position.current_price,
            status='PENDING'
        )
    
    return JsonResponse({
        'success': True,
        'message': f'{trade_type} order for {quantity} shares of {stock_ticker} placed successfully',
        'trade_id': trade.id
    })


def execute_signal_trade(request, signal_id):
    """Execute a trade based on a trading signal"""
    signal = get_object_or_404(TradingSignal, id=signal_id)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    portfolio_id = request.POST.get('portfolio_id')
    if not portfolio_id:
        return JsonResponse({'success': False, 'error': 'Portfolio not specified'})
    
    try:
        portfolio = Portfolio.objects.get(id=portfolio_id, is_active=True)
    except Portfolio.DoesNotExist:
        return JsonResponse({'success': False, 'error': f'Portfolio with ID {portfolio_id} not found or not active'})
    
    # Get SnapTrade user secret from portfolio
    user_secret = portfolio.snaptrade_user_secret
    if not user_secret:
        return JsonResponse({
            'success': False,
            'error': 'Portfolio not connected to SnapTrade. Please reconnect your brokerage account.',
            'requires_auth': True
        })
    
    # Get trading executor
    from trading.services.snaptrade_client import get_trading_executor
    trading_executor = get_trading_executor()
    
    # Execute trade via SnapTrade
    if signal.signal_type == 'BUY':
        # Use the proper SnapTrade buy execution
        trades = trading_executor.execute_buy_orders(
            portfolio=portfolio,
            buy_list=[signal.stock],
            total_value=signal.target_value or Decimal('1000'),  # Use signal target value
            user_secret=user_secret
        )
    else:  # SELL
        # Use the proper SnapTrade sell execution  
        trades = trading_executor.execute_sell_orders(
            portfolio=portfolio,
            sell_list=[signal.stock],
            user_secret=user_secret
        )
    
    if not trades:
        return JsonResponse({
            'success': False,
            'error': f'Failed to execute {signal.signal_type} order for {signal.stock.ticker}'
        })
    
    trade = trades[0]  # Get the first (and likely only) trade
    
    # Mark signal as executed
    signal.is_executed = True
    signal.executed_at = timezone.now()
    signal.save()
    
    return JsonResponse({
        'success': True,
        'message': f'{signal.signal_type} order for {trade.quantity} shares of {signal.stock.ticker} submitted to broker successfully',
        'trade_id': trade.id,
        'external_order_id': trade.external_order_id,
        'status': trade.status
    })


def generate_signals(request):
    """Generate new trading signals based on current momentum data"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    # Import the strategy engine
    from trading.services.strategy_engine import MomentumTradingStrategy
    
    # Get active portfolios
    active_portfolios = Portfolio.objects.filter(is_active=True)
    
    if not active_portfolios.exists():
        return JsonResponse({
            'success': False,
            'error': 'No active portfolios found. Please create a portfolio first.'
        })
    
    # Use the first active portfolio for signal generation context
    portfolio = active_portfolios.first()
    
    # Check if portfolio has sufficient cash for trading
    if portfolio.current_cash <= 0:
        return JsonResponse({
            'success': False,
            'error': f'Portfolio "{portfolio.name}" has no available cash for trading. Please sync portfolio with broker or add funds.'
        })
    
    strategy = MomentumTradingStrategy(portfolio)
    
    # Generate trading signals only (don't execute trades automatically)
    buy_signals, sell_signals = strategy.generate_trading_signals()
    
    total_signals = len(buy_signals) + len(sell_signals)
    
    if total_signals == 0:
        return JsonResponse({
            'success': False,
            'error': 'No trading signals generated. This could be due to: no stocks in top/bottom quintiles, insufficient cash, or no current positions to rebalance.'
        })
    
    return JsonResponse({
        'success': True,
        'message': f'Successfully generated {total_signals} trading signals ({len(buy_signals)} buy, {len(sell_signals)} sell)',
        'signals_count': total_signals,
        'buy_signals': len(buy_signals),
        'sell_signals': len(sell_signals),
        'portfolio': portfolio.name
    })


def delete_pending_signals(request):
    """Delete all pending (unexecuted) trading signals"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    # Count pending signals before deletion
    pending_signals = TradingSignal.objects.filter(is_executed=False)
    signals_count = pending_signals.count()
    
    if signals_count == 0:
        return JsonResponse({
            'success': False,
            'error': 'No pending signals to delete'
        })
    
    # Delete all pending signals
    deleted_count = pending_signals.delete()[0]
    
    return JsonResponse({
        'success': True,
        'message': f'Successfully deleted {deleted_count} pending trading signals',
        'signals_deleted': deleted_count
    })



def api_portfolios(request):
    """API endpoint to get available portfolios"""
    portfolios = Portfolio.objects.filter(is_active=True).order_by('name')
    
    portfolio_data = []
    for portfolio in portfolios:
        portfolio_data.append({
            'id': portfolio.id,
            'name': portfolio.name,
            'total_value': float(portfolio.total_value),
            'current_cash': float(portfolio.current_cash)
        })
    
    return JsonResponse({
        'portfolios': portfolio_data
    })


def recalculate_momentum(request):
    """Recalculate momentum scores for all stocks"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    from trading.services.momentum_calculator import get_momentum_calculator
    from trading.models import Stock
    
    # Get momentum calculator
    momentum_calculator = get_momentum_calculator()
    
    # Get calculation date (today or specified date)
    calculation_date = timezone.now().date()
    
    # Get all active stocks
    active_stocks = Stock.objects.filter(is_active=True)
    
    # Calculate momentum scores for all stocks
    momentum_scores = momentum_calculator.calculate_momentum_scores_bulk(
        stock_list=list(active_stocks),
        calculation_date=calculation_date
    )
    
    # Rank stocks and calculate quintiles
    ranked_scores = momentum_calculator.rank_stocks_by_momentum(calculation_date)
    
    return JsonResponse({
        'success': True,
        'message': f'Successfully recalculated momentum scores for {len(momentum_scores)} stocks',
        'scores_updated': len(momentum_scores),
        'calculation_date': calculation_date.isoformat()
    })