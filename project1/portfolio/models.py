from django.db import models
from django.utils import timezone
from decimal import Decimal
from trading.models import Stock


class Portfolio(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    initial_cash = models.DecimalField(max_digits=15, decimal_places=2)
    current_cash = models.DecimalField(max_digits=15, decimal_places=2)
    total_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    snaptrade_user_id = models.CharField(max_length=100, blank=True)
    snaptrade_account_id = models.CharField(max_length=100, blank=True)
    snaptrade_user_secret = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'portfolios'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} - ${self.total_value:,.2f}"

    def calculate_total_value(self):
        positions_value = sum(
            position.current_value for position in self.positions.filter(quantity__gt=0)
        )
        self.total_value = self.current_cash + positions_value
        return self.total_value

    def get_current_positions(self):
        return self.positions.filter(quantity__gt=0).select_related('stock')


class Position(models.Model):
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='positions')
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=0)
    average_cost = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    current_price = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    current_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    unrealized_pnl = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    unrealized_pnl_percent = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'positions'
        unique_together = ('portfolio', 'stock')
        ordering = ['-current_value']

    def __str__(self):
        return f"{self.portfolio.name} - {self.stock.ticker} - {self.quantity} shares"

    def update_current_value(self, current_price=None):
        if current_price:
            self.current_price = current_price
        
        if self.current_price and self.quantity > 0:
            self.current_value = Decimal(str(self.quantity)) * self.current_price
            cost_basis = Decimal(str(self.quantity)) * self.average_cost
            self.unrealized_pnl = self.current_value - cost_basis
            
            if cost_basis > 0:
                self.unrealized_pnl_percent = (self.unrealized_pnl / cost_basis) * 100
        else:
            self.current_value = 0
            self.unrealized_pnl = 0
            self.unrealized_pnl_percent = 0

    def add_shares(self, quantity, price):
        if self.quantity > 0:
            total_cost = (self.quantity * self.average_cost) + (quantity * price)
            total_shares = self.quantity + quantity
            self.average_cost = total_cost / total_shares
        else:
            self.average_cost = price
        
        self.quantity += quantity
        self.update_current_value(price)

    def remove_shares(self, quantity, price):
        if quantity >= self.quantity:
            self.quantity = 0
            self.average_cost = 0
            self.current_value = 0
            self.unrealized_pnl = 0
            self.unrealized_pnl_percent = 0
        else:
            self.quantity -= quantity
            self.update_current_value(price)


class Trade(models.Model):
    TRADE_TYPES = [
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SUBMITTED', 'Submitted'),
        ('FILLED', 'Filled'),
        ('PARTIALLY_FILLED', 'Partially Filled'),
        ('CANCELLED', 'Cancelled'),
        ('REJECTED', 'Rejected'),
    ]

    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='trades')
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE)
    trade_type = models.CharField(max_length=4, choices=TRADE_TYPES)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    filled_quantity = models.IntegerField(default=0)
    filled_price = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    order_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    external_order_id = models.CharField(max_length=100, blank=True)
    snaptrade_order_id = models.CharField(max_length=100, blank=True)
    commission = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    error_message = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    filled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'trades'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['portfolio', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"{self.trade_type} {self.quantity} {self.stock.ticker} - {self.status}"

    def calculate_order_value(self):
        if self.price and self.quantity:
            self.order_value = Decimal(str(self.quantity)) * self.price
        return self.order_value

    def update_position(self):
        if self.status != 'FILLED' or not self.filled_price:
            return

        position, created = Position.objects.get_or_create(
            portfolio=self.portfolio,
            stock=self.stock,
            defaults={'quantity': 0, 'average_cost': 0}
        )

        if self.trade_type == 'BUY':
            position.add_shares(self.filled_quantity, self.filled_price)
        elif self.trade_type == 'SELL':
            position.remove_shares(self.filled_quantity, self.filled_price)

        position.save()

        # Update portfolio cash
        if self.trade_type == 'BUY':
            self.portfolio.current_cash -= (self.filled_quantity * self.filled_price + self.commission)
        elif self.trade_type == 'SELL':
            self.portfolio.current_cash += (self.filled_quantity * self.filled_price - self.commission)
        
        self.portfolio.save()


class PerformanceMetric(models.Model):
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='performance_metrics')
    date = models.DateField()
    total_value = models.DecimalField(max_digits=15, decimal_places=2)
    cash_value = models.DecimalField(max_digits=15, decimal_places=2)
    positions_value = models.DecimalField(max_digits=15, decimal_places=2)
    daily_return = models.DecimalField(max_digits=8, decimal_places=6, null=True, blank=True)
    cumulative_return = models.DecimalField(max_digits=8, decimal_places=6, null=True, blank=True)
    total_trades = models.IntegerField(default=0)
    winning_trades = models.IntegerField(default=0)
    losing_trades = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'performance_metrics'
        unique_together = ('portfolio', 'date')
        ordering = ['-date']
        indexes = [
            models.Index(fields=['portfolio', 'date']),
        ]

    def __str__(self):
        return f"{self.portfolio.name} - {self.date} - ${self.total_value:,.2f}"

    def calculate_daily_return(self, previous_value):
        if previous_value and previous_value > 0:
            self.daily_return = ((self.total_value - previous_value) / previous_value) * 100
        else:
            self.daily_return = 0

    def calculate_cumulative_return(self, initial_value):
        if initial_value and initial_value > 0:
            self.cumulative_return = ((self.total_value - initial_value) / initial_value) * 100
        else:
            self.cumulative_return = 0
