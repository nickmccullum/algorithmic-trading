from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.core.paginator import Paginator
from .models import TradingAccount, Trade, Portfolio
from .services import SnapTradeService
from market_data.models import TradingSignal


def trading_dashboard(request):
    """Trading dashboard view"""
    accounts = TradingAccount.objects.filter(is_active=True)
    recent_trades = Trade.objects.select_related('etf', 'signal').order_by('-created_at')[:10]
    portfolio_positions = Portfolio.objects.select_related('etf').filter(quantity__gt=0)
    
    # Get pending signals that haven't been executed
    pending_signals = TradingSignal.objects.filter(executed=False).order_by('-signal_date')[:5]
    
    context = {
        'accounts': accounts,
        'recent_trades': recent_trades,
        'portfolio_positions': portfolio_positions,
        'pending_signals': pending_signals,
    }
    return render(request, 'trading/dashboard.html', context)


def trades_list(request):
    """List all trades"""
    trades = Trade.objects.select_related('etf', 'signal', 'account').order_by('-created_at')
    
    # Filter by status if provided
    status = request.GET.get('status')
    if status in ['PENDING', 'EXECUTED', 'FAILED', 'CANCELLED']:
        trades = trades.filter(status=status)
    
    # Filter by trade type if provided
    trade_type = request.GET.get('type')
    if trade_type in ['BUY', 'SELL']:
        trades = trades.filter(trade_type=trade_type)
    
    # Pagination
    paginator = Paginator(trades, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status': status,
        'trade_type': trade_type,
    }
    return render(request, 'trading/trades_list.html', context)


def portfolio_view(request):
    """Portfolio overview"""
    accounts = TradingAccount.objects.filter(is_active=True)
    
    portfolio_data = {}
    for account in accounts:
        positions = Portfolio.objects.filter(
            account=account,
            quantity__gt=0
        ).select_related('etf')
        portfolio_data[account] = positions
    
    context = {
        'portfolio_data': portfolio_data,
    }
    return render(request, 'trading/portfolio.html', context)


def execute_signal(request, signal_id):
    """Execute a trading signal"""
    if request.method == 'POST':
        try:
            signal = get_object_or_404(TradingSignal, id=signal_id)
            
            if signal.executed:
                return JsonResponse({
                    'status': 'error', 
                    'message': 'Signal already executed'
                })
            
            # Get default trading account
            account = TradingAccount.objects.filter(is_active=True).first()
            if not account:
                return JsonResponse({
                    'status': 'error', 
                    'message': 'No active trading account found'
                })
            
            snap_service = SnapTradeService()
            
            if signal.signal_type == 'BUY':
                result = snap_service.place_buy_order(account, signal.etf, 100, signal.close_price)
            else:  # SELL
                result = snap_service.place_sell_order(account, signal.etf, signal.close_price)
            
            if result.get('success'):
                signal.executed = True
                signal.save()
                
                messages.success(request, f'Successfully executed {signal.signal_type} order for {signal.etf.ticker}')
                return JsonResponse({'status': 'success', 'result': result})
            else:
                messages.error(request, f'Failed to execute order: {result.get("error")}')
                return JsonResponse({'status': 'error', 'message': result.get('error')})
                
        except Exception as e:
            messages.error(request, f'Error executing signal: {str(e)}')
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})


def sync_portfolio(request):
    """Sync portfolio with SnapTrade"""
    if request.method == 'POST':
        try:
            snap_service = SnapTradeService()
            results = snap_service.sync_all_portfolios()
            
            total_synced = sum(results.values())
            messages.success(request, f'Successfully synced {total_synced} portfolio positions')
            
            return JsonResponse({'status': 'success', 'results': results})
        except Exception as e:
            messages.error(request, f'Error syncing portfolio: {str(e)}')
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})
