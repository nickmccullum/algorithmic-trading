from django.shortcuts import render
from django.http import JsonResponse
from django.contrib import messages
from django.core.paginator import Paginator
from .models import Index, MarketData, MovingAverage, TradingSignal
from .services import MassiveAPIService, MovingAverageService, TradingSignalService
from datetime import datetime, timedelta


def dashboard(request):
    """Main dashboard view"""
    indices = Index.objects.all()
    recent_signals = TradingSignal.objects.select_related('index', 'etf').order_by('-signal_date')[:10]
    
    context = {
        'indices': indices,
        'recent_signals': recent_signals,
    }
    return render(request, 'market_data/dashboard.html', context)


def index_detail(request, index_id):
    """Detail view for a specific index"""
    index = Index.objects.get(id=index_id)
    
    # Get recent market data
    recent_data = MarketData.objects.filter(index=index).order_by('-date')[:30]
    
    # Get recent moving averages
    recent_ma = MovingAverage.objects.filter(
        index=index,
        ma_50__isnull=False,
        ma_200__isnull=False
    ).order_by('-date')[:30]
    
    # Get recent signals
    recent_signals = TradingSignal.objects.filter(index=index).order_by('-signal_date')[:10]
    
    # Get current MA values for crossover status
    latest_ma = MovingAverage.objects.filter(
        index=index,
        ma_50__isnull=False,
        ma_200__isnull=False
    ).order_by('-date').first()
    
    current_trend = None
    if latest_ma:
        if latest_ma.ma_50 > latest_ma.ma_200:
            current_trend = 'bullish'
        else:
            current_trend = 'bearish'
    
    context = {
        'index': index,
        'recent_data': recent_data,
        'recent_ma': recent_ma,
        'recent_signals': recent_signals,
        'current_trend': current_trend,
        'latest_ma': latest_ma,
    }
    return render(request, 'market_data/index_detail.html', context)


def fetch_data(request):
    """Fetch market data from Massive API"""
    if request.method == 'POST':
        try:
            massive_service = MassiveAPIService()
            results = massive_service.fetch_all_indices_data()
            
            total_records = sum(results.values())
            messages.success(request, f'Successfully fetched {total_records} new market data records')
            
            return JsonResponse({'status': 'success', 'results': results})
        except Exception as e:
            messages.error(request, f'Error fetching data: {str(e)}')
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})


def calculate_ma(request):
    """Calculate moving averages"""
    if request.method == 'POST':
        try:
            ma_service = MovingAverageService()
            results = ma_service.calculate_all_moving_averages()
            
            total_records = sum(results.values())
            messages.success(request, f'Successfully calculated {total_records} new moving average records')
            
            return JsonResponse({'status': 'success', 'results': results})
        except Exception as e:
            messages.error(request, f'Error calculating moving averages: {str(e)}')
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})


def detect_signals(request):
    """Detect trading signals"""
    if request.method == 'POST':
        try:
            signal_service = TradingSignalService()
            results = signal_service.detect_all_signals()
            
            total_signals = sum(results.values())
            messages.success(request, f'Successfully detected {total_signals} new trading signals')
            
            return JsonResponse({'status': 'success', 'results': results})
        except Exception as e:
            messages.error(request, f'Error detecting signals: {str(e)}')
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})


def signals_list(request):
    """List all trading signals"""
    signals = TradingSignal.objects.select_related('index', 'etf').order_by('-signal_date')
    
    # Filter by signal type if provided
    signal_type = request.GET.get('type')
    if signal_type in ['BUY', 'SELL']:
        signals = signals.filter(signal_type=signal_type)
    
    # Pagination
    paginator = Paginator(signals, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'signal_type': signal_type,
    }
    return render(request, 'market_data/signals_list.html', context)
