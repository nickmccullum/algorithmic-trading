from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
import pandas as pd
import numpy as np


class Stock(models.Model):
    ticker = models.CharField(max_length=10, unique=True, db_index=True)
    name = models.CharField(max_length=255, blank=True)
    sector = models.CharField(max_length=100, blank=True)
    market_cap = models.BigIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'stocks'
        ordering = ['ticker']

    def __str__(self):
        return f"{self.ticker} - {self.name}"

    def get_latest_price_data(self):
        return self.price_data.filter(
            date__gte=timezone.now().date() - timedelta(days=400)
        ).order_by('-date')

    def calculate_momentum_score(self, calculation_date=None):
        if calculation_date is None:
            calculation_date = timezone.now().date()
        
        # Get 12 months ago and 1 month ago dates
        twelve_months_ago = calculation_date - timedelta(days=365)
        one_month_ago = calculation_date - timedelta(days=30)
        
        try:
            # Get price 12 months ago
            price_12m = self.price_data.filter(
                date__gte=twelve_months_ago,
                date__lte=twelve_months_ago + timedelta(days=7)
            ).first()
            
            # Get price 1 month ago
            price_1m = self.price_data.filter(
                date__gte=one_month_ago,
                date__lte=one_month_ago + timedelta(days=7)
            ).first()
            
            if price_12m and price_1m:
                momentum = (price_1m.close - price_12m.close) / price_12m.close
                return momentum
            return None
        except Exception:
            return None


class PriceData(models.Model):
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='price_data')
    date = models.DateField(db_index=True)
    open_price = models.DecimalField(max_digits=12, decimal_places=4)
    high = models.DecimalField(max_digits=12, decimal_places=4)
    low = models.DecimalField(max_digits=12, decimal_places=4)
    close = models.DecimalField(max_digits=12, decimal_places=4)
    volume = models.BigIntegerField()
    adjusted_close = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'price_data'
        unique_together = ('stock', 'date')
        ordering = ['-date']
        indexes = [
            models.Index(fields=['stock', 'date']),
            models.Index(fields=['date']),
        ]

    def __str__(self):
        return f"{self.stock.ticker} - {self.date} - ${self.close}"


class MomentumScore(models.Model):
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='momentum_scores')
    calculation_date = models.DateField(db_index=True)
    momentum_score = models.DecimalField(max_digits=10, decimal_places=6)
    rank = models.IntegerField(null=True, blank=True)
    quintile = models.IntegerField(null=True, blank=True)
    is_top_quintile = models.BooleanField(default=False)
    period_start = models.DateField()
    period_end = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'momentum_scores'
        unique_together = ('stock', 'calculation_date')
        ordering = ['-calculation_date', '-momentum_score']
        indexes = [
            models.Index(fields=['calculation_date', 'quintile']),
            models.Index(fields=['calculation_date', 'is_top_quintile']),
        ]

    def __str__(self):
        return f"{self.stock.ticker} - {self.calculation_date} - {self.momentum_score:.4f}"

    @classmethod
    def calculate_quintiles_for_date(cls, calculation_date=None):
        if calculation_date is None:
            calculation_date = timezone.now().date()
        
        # Get all momentum scores for the calculation date
        scores = cls.objects.filter(calculation_date=calculation_date).order_by('-momentum_score')
        
        if not scores.exists():
            return
        
        total_stocks = scores.count()
        quintile_size = total_stocks // 5
        
        # Update quintiles and rankings
        for i, score in enumerate(scores):
            score.rank = i + 1
            quintile = min(5, (i // quintile_size) + 1) if quintile_size > 0 else 1
            score.quintile = quintile
            score.is_top_quintile = (score.quintile == 1)
            score.save(update_fields=['rank', 'quintile', 'is_top_quintile'])


class TradingSignal(models.Model):
    SIGNAL_TYPES = [
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
        ('HOLD', 'Hold'),
    ]
    
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='trading_signals')
    signal_date = models.DateField(db_index=True)
    signal_type = models.CharField(max_length=4, choices=SIGNAL_TYPES)
    momentum_score = models.ForeignKey(MomentumScore, on_delete=models.CASCADE, null=True)
    target_quantity = models.IntegerField(null=True, blank=True)
    target_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    reason = models.TextField(blank=True)
    is_executed = models.BooleanField(default=False)
    executed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'trading_signals'
        ordering = ['-signal_date', '-created_at']
        indexes = [
            models.Index(fields=['signal_date', 'signal_type']),
            models.Index(fields=['is_executed']),
        ]

    def __str__(self):
        return f"{self.signal_type} {self.stock.ticker} on {self.signal_date}"


class RebalanceEvent(models.Model):
    date = models.DateField(db_index=True)
    total_stocks_analyzed = models.IntegerField()
    buy_signals_generated = models.IntegerField()
    sell_signals_generated = models.IntegerField()
    total_portfolio_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    execution_status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('IN_PROGRESS', 'In Progress'),
            ('COMPLETED', 'Completed'),
            ('FAILED', 'Failed'),
        ],
        default='PENDING'
    )
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'rebalance_events'
        ordering = ['-date']

    def __str__(self):
        return f"Rebalance on {self.date} - {self.execution_status}"
