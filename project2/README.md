# Index Trend Trading System

A Django-based algorithmic trading system that implements the 50/200 moving average crossover strategy for index ETF trading using Massive API for market data and SnapTrade for order execution.

## Strategy Overview

**50/200 Moving Average Strategy:**
- **Buy Signal (Golden Cross):** When the 50-day moving average crosses above the 200-day moving average
- **Sell Signal (Death Cross):** When the 50-day moving average crosses below the 200-day moving average

## Index-to-ETF Mapping

| Index | Massive Ticker | ETF to Trade | Description |
|-------|----------------|--------------|-------------|
| S&P 500 | `I:SPX` | SPY | Tracks the 500 largest U.S. companies |
| NASDAQ-100 | `I:NDX` | QQQ | Tracks the 100 largest non-financial NASDAQ companies |
| Dow Jones Industrial | `I:DJI` | DIA | Tracks 30 large-cap U.S. blue-chip companies |
| Russell 2000 | `I:RUT` | IWM | Tracks 2,000 small-cap U.S. companies |

## Installation & Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Keys

Edit `index_trading/settings.py` and add your API keys:

```python
# API Keys
MASSIVE_API_KEY = 'your_massive_api_key_here'
SNAPTRADE_CONSUMER_KEY = 'your_snaptrade_consumer_key_here'
SNAPTRADE_CLIENT_ID = 'your_snaptrade_client_id_here'
```

### 3. Database Setup

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

### 4. Initialize Default Indices and ETFs

```bash
python manage.py setup_indices
```

### 5. Start the Development Server

```bash
python manage.py runserver
```

Access the application at `http://localhost:8000`

## Features

### Market Data Management
- **Fetch Market Data:** Retrieves historical OHLC data from Massive API
- **Calculate Moving Averages:** Computes 50-day and 200-day moving averages
- **Signal Detection:** Identifies golden cross and death cross patterns
- **Real-time Monitoring:** Dashboard view of all indices and recent signals

### Trading Operations
- **Automated Execution:** Execute buy/sell orders based on detected signals
- **Portfolio Management:** Track current positions and average costs
- **Order History:** Complete trading history with status tracking
- **SnapTrade Integration:** Seamless broker integration for live trading

### Web Interface
- **Market Data Dashboard:** Overview of indices, signals, and data management
- **Trading Dashboard:** Portfolio overview, pending signals, and trade execution
- **Signal History:** Detailed view of all detected trading signals
- **Admin Interface:** Easy configuration of indices, ETFs, and accounts

## Usage Workflow

### 1. Data Collection
1. Navigate to the Market Data dashboard
2. Click "Fetch Market Data" to retrieve latest index prices
3. Click "Calculate Moving Averages" to compute MAs
4. Click "Detect Signals" to identify trading opportunities

### 2. Trading Execution
1. Go to the Trading dashboard
2. Review pending signals in the "Pending Trading Signals" section
3. Click "Execute" on desired signals to place trades
4. Monitor portfolio positions and trade history

### 3. Portfolio Management
1. Use "Sync Portfolio" to update positions from SnapTrade
2. View current holdings in the Portfolio section
3. Monitor trade execution status and history

## API Requirements

### Massive API
- Used for fetching historical index data
- Requires API key from [Massive.com](https://massive.com)
- Endpoint: `/v2/aggs/ticker/{indicesTicker}/range/{multiplier}/{timespan}/{from}/{to}`

### SnapTrade API
- Used for order execution and portfolio management
- Requires Consumer Key and Client ID from [SnapTrade](https://snaptrade.com)
- Handles buy/sell orders and position synchronization

## Data Models

### Core Models
- **Index:** Stores index information and Massive tickers
- **ETF:** Maps indices to tradeable ETFs
- **MarketData:** Historical OHLC data for indices
- **MovingAverage:** Calculated 50-day and 200-day moving averages
- **TradingSignal:** Detected buy/sell signals with execution status

### Trading Models
- **TradingAccount:** SnapTrade account configuration
- **Trade:** Individual trade records with execution details
- **Portfolio:** Current ETF positions and average costs

## Management Commands

- `python manage.py setup_indices` - Initialize default indices and ETFs
- `python manage.py makemigrations` - Create database migrations
- `python manage.py migrate` - Apply database migrations

## Security Notes

- Store API keys as environment variables in production
- Use HTTPS for all live trading operations
- Implement proper authentication for production deployments
- Monitor API rate limits and usage

## Directory Structure

```
project2/
├── index_trading/          # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── ...
├── market_data/            # Market data management app
│   ├── models.py          # Index, ETF, MarketData models
│   ├── services.py        # Massive API and calculation services
│   ├── views.py           # Market data views
│   ├── admin.py           # Admin configuration
│   └── templates/         # Market data templates
├── trading/                # Trading operations app
│   ├── models.py          # Trading, Portfolio models
│   ├── services.py        # SnapTrade API service
│   ├── views.py           # Trading views
│   └── templates/         # Trading templates
├── templates/              # Base templates
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Technology Stack

- **Backend:** Django 5.2.5
- **Database:** SQLite (development), PostgreSQL (production recommended)
- **Frontend:** Bootstrap 5, HTML/CSS/JavaScript
- **APIs:** Massive API (market data), SnapTrade API (trading)
- **Data Processing:** pandas, numpy

## Support

For issues and questions:
1. Check the Django admin interface for data configuration
2. Review API key configuration in settings.py
3. Monitor Django logs for error details
4. Verify API connectivity and rate limits