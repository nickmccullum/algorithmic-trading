from django.contrib import admin
from .models import Index, ETF, MarketData, MovingAverage, TradingSignal


@admin.register(Index)
class IndexAdmin(admin.ModelAdmin):
    list_display = ('name', 'massive_ticker', 'description')
    search_fields = ('name', 'massive_ticker')
    list_filter = ('name',)


@admin.register(ETF)
class ETFAdmin(admin.ModelAdmin):
    list_display = ('ticker', 'name', 'index')
    search_fields = ('ticker', 'name')
    list_filter = ('index',)


@admin.register(MarketData)
class MarketDataAdmin(admin.ModelAdmin):
    list_display = ('index', 'date', 'close_price', 'volume', 'created_at')
    list_filter = ('index', 'date')
    search_fields = ('index__name', 'index__massive_ticker')
    date_hierarchy = 'date'
    ordering = ('-date',)


@admin.register(MovingAverage)
class MovingAverageAdmin(admin.ModelAdmin):
    list_display = ('index', 'date', 'ma_50', 'ma_200', 'created_at')
    list_filter = ('index', 'date')
    search_fields = ('index__name', 'index__massive_ticker')
    date_hierarchy = 'date'
    ordering = ('-date',)


@admin.register(TradingSignal)
class TradingSignalAdmin(admin.ModelAdmin):
    list_display = ('signal_type', 'etf', 'signal_date', 'close_price', 'executed', 'created_at')
    list_filter = ('signal_type', 'executed', 'etf', 'signal_date')
    search_fields = ('etf__ticker', 'index__name')
    date_hierarchy = 'signal_date'
    ordering = ('-signal_date',)
    actions = ['mark_as_executed']

    def mark_as_executed(self, request, queryset):
        queryset.update(executed=True)
    mark_as_executed.short_description = "Mark selected signals as executed"
