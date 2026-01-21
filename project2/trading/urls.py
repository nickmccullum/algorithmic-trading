from django.urls import path
from . import views

app_name = 'trading'

urlpatterns = [
    path('', views.trading_dashboard, name='dashboard'),
    path('trades/', views.trades_list, name='trades_list'),
    path('portfolio/', views.portfolio_view, name='portfolio'),
    path('execute-signal/<int:signal_id>/', views.execute_signal, name='execute_signal'),
    path('sync-portfolio/', views.sync_portfolio, name='sync_portfolio'),
]