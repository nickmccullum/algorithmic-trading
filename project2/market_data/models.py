from django.db import models
from django.utils import timezone


class Index(models.Model):
    name = models.CharField(max_length=100)
    massive_ticker = models.CharField(max_length=20, unique=True)
    description = models.TextField()
    
    def __str__(self):
        return f"{self.name} ({self.massive_ticker})"


class ETF(models.Model):
    index = models.OneToOneField(Index, on_delete=models.CASCADE)
    ticker = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    
    def __str__(self):
        return f"{self.name} ({self.ticker})"


class MarketData(models.Model):
    index = models.ForeignKey(Index, on_delete=models.CASCADE)
    date = models.DateField()
    open_price = models.DecimalField(max_digits=12, decimal_places=2)
    high_price = models.DecimalField(max_digits=12, decimal_places=2)
    low_price = models.DecimalField(max_digits=12, decimal_places=2)
    close_price = models.DecimalField(max_digits=12, decimal_places=2)
    volume = models.BigIntegerField()
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        unique_together = ('index', 'date')
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.index.massive_ticker} - {self.date}"


class MovingAverage(models.Model):
    index = models.ForeignKey(Index, on_delete=models.CASCADE)
    date = models.DateField()
    ma_50 = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    ma_200 = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        unique_together = ('index', 'date')
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.index.massive_ticker} MA - {self.date}"


class TradingSignal(models.Model):
    SIGNAL_TYPES = [
        ('BUY', 'Golden Cross - Buy Signal'),
        ('SELL', 'Death Cross - Sell Signal'),
    ]
    
    index = models.ForeignKey(Index, on_delete=models.CASCADE)
    etf = models.ForeignKey(ETF, on_delete=models.CASCADE)
    signal_type = models.CharField(max_length=4, choices=SIGNAL_TYPES)
    signal_date = models.DateField()
    ma_50 = models.DecimalField(max_digits=12, decimal_places=4)
    ma_200 = models.DecimalField(max_digits=12, decimal_places=4)
    close_price = models.DecimalField(max_digits=12, decimal_places=2)
    executed = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-signal_date']
    
    def __str__(self):
        return f"{self.signal_type} - {self.etf.ticker} on {self.signal_date}"
