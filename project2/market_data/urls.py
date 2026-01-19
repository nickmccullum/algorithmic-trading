from django.urls import path
from . import views

app_name = 'market_data'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('index/<int:index_id>/', views.index_detail, name='index_detail'),
    path('fetch-data/', views.fetch_data, name='fetch_data'),
    path('calculate-ma/', views.calculate_ma, name='calculate_ma'),
    path('detect-signals/', views.detect_signals, name='detect_signals'),
    path('signals/', views.signals_list, name='signals_list'),
]