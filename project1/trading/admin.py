from django.contrib import admin
from .models import Stock, PriceData, MomentumScore, TradingSignal, RebalanceEvent


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ('ticker', 'name', 'sector', 'is_active', 'created_at')
    list_filter = ('is_active', 'sector')
    search_fields = ('ticker', 'name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PriceData)
class PriceDataAdmin(admin.ModelAdmin):
    list_display = ('stock', 'date', 'close', 'volume')
    list_filter = ('date', 'stock')
    search_fields = ('stock__ticker',)
    readonly_fields = ('created_at',)
    date_hierarchy = 'date'


@admin.register(MomentumScore)
class MomentumScoreAdmin(admin.ModelAdmin):
    list_display = ('stock', 'calculation_date', 'momentum_score', 'rank', 'quintile', 'is_top_quintile')
    list_filter = ('calculation_date', 'quintile', 'is_top_quintile')
    search_fields = ('stock__ticker',)
    readonly_fields = ('created_at',)
    date_hierarchy = 'calculation_date'


@admin.register(TradingSignal)
class TradingSignalAdmin(admin.ModelAdmin):
    list_display = ('stock', 'signal_date', 'signal_type', 'is_executed', 'created_at')
    list_filter = ('signal_type', 'signal_date', 'is_executed')
    search_fields = ('stock__ticker',)
    readonly_fields = ('created_at', 'executed_at')
    date_hierarchy = 'signal_date'


@admin.register(RebalanceEvent)
class RebalanceEventAdmin(admin.ModelAdmin):
    list_display = ('date', 'execution_status', 'total_stocks_analyzed', 'buy_signals_generated', 'sell_signals_generated')
    list_filter = ('execution_status', 'date')
    readonly_fields = ('created_at', 'completed_at')
    date_hierarchy = 'date'
