# Momentum Trading System - Setup Guide

This guide will walk you through setting up the momentum trading system step by step.

## 🎯 Prerequisites

Before starting, ensure you have:
- Python 3.8 or higher installed
- Basic familiarity with Django and command line
- API access to Massive (for market data)
- SnapTrade account (for trading - optional for development)

## 📋 Step-by-Step Setup

### Step 1: Environment Setup

1. **Navigate to the project directory**
   ```bash
   cd project1
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   
   # On macOS/Linux:
   source venv/bin/activate
   
   # On Windows:
   venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

### Step 2: Environment Configuration

1. **Copy environment template**
   ```bash
   cp .env.example .env
   ```

2. **Edit .env file with your settings**
   ```bash
   # Example .env configuration
   SECRET_KEY=your-django-secret-key-here
   DEBUG=True
   
   # API Keys
   MASSIVE_API_KEY=your_massive_api_key
   SNAPTRADE_CLIENT_ID=your_snaptrade_client_id
   SNAPTRADE_CLIENT_SECRET=your_snaptrade_client_secret
   ```

### Step 3: Database Setup

1. **Run database migrations**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

2. **Create superuser account**
   ```bash
   python manage.py createsuperuser
   ```
   Follow the prompts to create your admin account.

### Step 4: Initial Data Setup

1. **Load initial stock universe and backfill data**
   ```bash
   # This will take some time as it downloads historical data
   python manage.py backfill_data --update-universe --days 420
   ```

2. **Calculate initial momentum scores**
   ```bash
   python manage.py update_momentum_scores
   ```

### Step 5: Portfolio Creation

1. **Start the Django server**
   ```bash
   python manage.py runserver
   ```

2. **Access Django admin**
   - Go to `http://localhost:8000/admin/`
   - Login with your superuser credentials

3. **Create a portfolio**
   - Navigate to "Portfolios" → "Add Portfolio"
   - Fill in:
     - Name: "My Momentum Portfolio"
     - Initial Cash: 100000
     - Current Cash: 100000
     - Description: "Demo momentum trading portfolio"
   - Save the portfolio

### Step 6: Test the System

1. **Access the dashboard**
   - Go to `http://localhost:8000/`
   - You should see the momentum trading dashboard

2. **Run a test rebalance (dry run)**
   ```bash
   python manage.py execute_rebalance --portfolio "My Momentum Portfolio" --dry-run
   ```

## 🔧 Configuration Options

### Trading Strategy Parameters

Edit these in `momentum_trader/settings.py`:

```python
# Momentum calculation settings
MOMENTUM_LOOKBACK_MONTHS = 12    # Look back 12 months
MOMENTUM_SKIP_MONTHS = 1         # Skip most recent month
REBALANCE_FREQUENCY = 'weekly'   # Rebalance frequency
TOP_QUINTILE_THRESHOLD = 20      # Top 20% threshold
```

### Database Configuration

For production, consider using PostgreSQL:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'momentum_trader',
        'USER': 'your_db_user',
        'PASSWORD': 'your_db_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

## 🔄 Daily Operations

### Automated Daily Workflow

Create a shell script for daily operations:

```bash
#!/bin/bash
# daily_update.sh

echo "Starting daily momentum trading update..."

# Activate virtual environment
source venv/bin/activate

# Update momentum scores
echo "Calculating momentum scores..."
python manage.py update_momentum_scores

# Check if rebalancing is needed and execute
echo "Checking for rebalancing..."
python manage.py execute_rebalance --portfolio "My Momentum Portfolio"

# Sync portfolio positions
echo "Syncing portfolio..."
python manage.py sync_portfolio --portfolio "My Momentum Portfolio" --update-trades

echo "Daily update complete!"
```

### Weekly Operations

```bash
#!/bin/bash
# weekly_maintenance.sh

# Backup database
echo "Creating database backup..."
python manage.py dumpdata > backup_$(date +%Y%m%d).json

# Update stock universe (add new stocks)
echo "Updating stock universe..."
python manage.py backfill_data --update-universe --days 30

echo "Weekly maintenance complete!"
```

## 📊 Monitoring & Alerts

### Key Metrics to Monitor

1. **Data Quality**
   - Number of stocks with sufficient data (>280 days)
   - API call success rates
   - Data freshness

2. **Strategy Performance**
   - Portfolio value changes
   - Number of active positions
   - Trade execution success rates

3. **System Health**
   - Django application status
   - Database connectivity
   - API response times

### Setting Up Alerts

Consider implementing alerts for:
- Failed momentum calculations
- Trading execution errors
- Significant portfolio value changes
- API rate limit warnings

## 🚨 Troubleshooting

### Common Issues and Solutions

#### Issue: "Insufficient data for momentum calculation"
**Solution**: Ensure stocks have at least 280 days of price data
```bash
python manage.py backfill_data --days 420
```

#### Issue: "API rate limit exceeded"
**Solution**: Implement delays or reduce batch sizes
```bash
python manage.py backfill_data --batch-size 5
```

#### Issue: "Portfolio not found"
**Solution**: Verify portfolio name spelling and existence
```bash
# List all portfolios
python manage.py shell -c "from portfolio.models import Portfolio; print(Portfolio.objects.values_list('name', flat=True))"
```

#### Issue: "No momentum scores calculated"
**Solution**: Check data availability and run calculations
```bash
python manage.py update_momentum_scores --update-universe
```

### Debug Mode

Enable debug logging by adding to settings.py:

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': 'momentum_trader.log',
        },
    },
    'loggers': {
        'trading': {
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}
```

## 🔐 Security Considerations

### API Key Protection

1. Never commit API keys to version control
2. Use environment variables for sensitive data
3. Rotate API keys regularly
4. Monitor API usage for unusual activity

### Database Security

1. Use strong passwords for database users
2. Limit database access to necessary IPs only
3. Regular database backups
4. Encrypt sensitive data at rest

### Application Security

1. Keep Django and dependencies updated
2. Use HTTPS in production
3. Implement proper authentication
4. Regular security audits

## 📈 Performance Optimization

### Database Optimization

```python
# Add database indexes for frequently queried fields
class Meta:
    indexes = [
        models.Index(fields=['calculation_date', 'quintile']),
        models.Index(fields=['stock', 'date']),
    ]
```

### Caching Strategy

Consider implementing caching for:
- Momentum score calculations
- Portfolio performance metrics
- Stock price data

### Background Tasks

Use Celery for long-running tasks:
```python
# Example Celery task
@app.task
def calculate_momentum_scores_async():
    # Run momentum calculations in background
    pass
```

## 🎓 Learning Resources

### Django Resources
- [Django Documentation](https://docs.djangoproject.com/)
- [Django Best Practices](https://django-best-practices.readthedocs.io/)

### Financial Markets
- Academic papers on momentum investing
- Risk management principles
- Portfolio theory fundamentals

### API Documentation
- [Massive API Docs](https://massive.com/docs)
- [SnapTrade API Docs](https://docs.snaptrade.com/)

## 📞 Getting Help

If you encounter issues:
1. Check the troubleshooting section above
2. Review Django error logs
3. Verify API connectivity and credentials
4. Consult the freeCodeCamp course materials

Remember: This system is for educational purposes. Always paper trade before using real money!