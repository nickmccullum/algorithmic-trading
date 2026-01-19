from django.contrib import admin
from .models import TradingAccount, Trade, Portfolio


@admin.register(TradingAccount)
class TradingAccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'account_id', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'account_id')


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'trade_type', 'etf', 'quantity', 'price', 'status', 'account')
    list_filter = ('trade_type', 'status', 'etf', 'account', 'executed_at')
    search_fields = ('etf__ticker', 'account__name', 'order_id')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ('account', 'etf', 'quantity', 'avg_cost', 'last_updated')
    list_filter = ('account', 'etf', 'last_updated')
    search_fields = ('account__name', 'etf__ticker')
    ordering = ('-last_updated',)
