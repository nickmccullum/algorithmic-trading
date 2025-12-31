from django.urls import path
from . import views

app_name = 'trading'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('portfolio/<int:portfolio_id>/', views.portfolio_detail, name='portfolio_detail'),
    path('portfolio/<int:portfolio_id>/delete/', views.delete_portfolio, name='delete_portfolio'),
    path('portfolios/', views.portfolio_list, name='portfolio_list'),
    path('portfolios/create/', views.create_portfolio, name='create_portfolio'),
    path('momentum/', views.momentum_scores, name='momentum_scores'),
    path('signals/', views.trading_signals, name='trading_signals'),
    
    # SnapTrade integration
    path('snaptrade/auth/', views.initiate_snaptrade_auth, name='snaptrade_auth'),
    path('snaptrade/callback/', views.snaptrade_callback, name='snaptrade_callback'),
    
    # Trading endpoints
    path('portfolio/<int:portfolio_id>/trade/', views.execute_trade, name='execute_trade'),
    path('signal/<int:signal_id>/execute/', views.execute_signal_trade, name='execute_signal_trade'),
    path('signals/generate/', views.generate_signals, name='generate_signals'),
    path('signals/delete-pending/', views.delete_pending_signals, name='delete_pending_signals'),
    path('momentum/recalculate/', views.recalculate_momentum, name='recalculate_momentum'),
    
    # API endpoints
    path('api/momentum-data/', views.api_momentum_data, name='api_momentum_data'),
    path('api/portfolio/<int:portfolio_id>/performance/', views.api_portfolio_performance, name='api_portfolio_performance'),
    path('api/portfolios/', views.api_portfolios, name='api_portfolios'),
]