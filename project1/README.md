# Momentum Trading System

A comprehensive algorithmic trading system built with Django that implements a momentum-based stock selection strategy using Massive API for market data and SnapTrade for order execution.

## 🚀 Features

- **Momentum Strategy**: 12-month momentum calculation with 1-month skip to avoid short-term reversal
- **Automated Rebalancing**: Weekly/monthly portfolio rebalancing based on momentum rankings
- **Top Quintile Selection**: Automatically buy stocks in the top 20% momentum performers
- **Risk Management**: Sell positions that drop out of the top quintile
- **Real-time Data**: Integration with Massive API for historical and current market data
- **Order Execution**: SnapTrade integration for automated trade execution
- **Web Dashboard**: Clean interface for monitoring portfolios and performance
- **Management Commands**: CLI tools for automation and maintenance

## 📊 Strategy Overview

The momentum trading strategy is based on academic research showing that stocks with strong past performance tend to continue outperforming in the near term.

### Key Components:

1. **Momentum Score Calculation**
   - Calculate return from 12 months ago to 1 month ago
   - Skip the most recent month to avoid short-term mean reversion
   - Formula: `(Price_1m_ago - Price_12m_ago) / Price_12m_ago`

2. **Stock Ranking & Selection**
   - Rank all stocks by momentum score
   - Divide into quintiles (5 equal groups)
   - Buy: Top quintile (top 20%)
   - Sell: Bottom quintile (bottom 20%)

3. **Portfolio Management**
   - Equal-weight positions in top quintile stocks
   - Regular rebalancing (weekly or monthly)
   - Maintain cash buffer for new opportunities

## 🛠 Installation

### Prerequisites

- Python 3.8+
- Django 4.2+
- Redis (for Celery background tasks)
- PostgreSQL (recommended for production)

### Setup

1. **Clone the repository**
   ```bash
   cd project1
   ```

2. **Create virtual environment**
   ```bash
   python -m venv momentum_trader_env
   source momentum_trader_env/bin/activate  # On Windows: momentum_trader_env\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

5. **Configure database**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

6. **Create superuser**
   ```bash
   python manage.py createsuperuser
   ```

7. **Run development server**
   ```bash
   python manage.py runserver
   ```

## 📚 API Configuration

### Massive API Setup

1. Sign up at [Massive](https://massive.com) and obtain your API key
2. Add your API key to `.env`:
   ```
   MASSIVE_API_KEY=your_massive_api_key_here
   ```

### SnapTrade API Setup

1. Register at [SnapTrade](https://snaptrade.com) for trading capabilities
2. Get your client credentials and add to `.env`:
   ```
   SNAPTRADE_CLIENT_ID=your_client_id_here
   SNAPTRADE_CLIENT_SECRET=your_client_secret_here
   ```

## 🎯 Usage

### Initial Setup

1. **Update stock universe**
   ```bash
   python manage.py backfill_data --update-universe --days 420
   ```

2. **Calculate initial momentum scores**
   ```bash
   python manage.py update_momentum_scores --update-universe
   ```

3. **Create a portfolio** (via Django admin or shell)
   ```python
   from portfolio.models import Portfolio
   portfolio = Portfolio.objects.create(
       name="My Momentum Portfolio",
       initial_cash=100000,
       current_cash=100000
   )
   ```

### Regular Operations

1. **Daily momentum score updates**
   ```bash
   python manage.py update_momentum_scores
   ```

2. **Execute rebalancing**
   ```bash
   python manage.py execute_rebalance --portfolio "My Momentum Portfolio"
   ```

3. **Sync portfolio with broker**
   ```bash
   python manage.py sync_portfolio --portfolio "My Momentum Portfolio" --update-trades
   ```

### Management Commands

#### Update Momentum Scores
```bash
# Update all stocks
python manage.py update_momentum_scores

# Update specific stocks
python manage.py update_momentum_scores --tickers AAPL MSFT GOOGL

# Update for specific date
python manage.py update_momentum_scores --date 2024-01-15

# Update stock universe first
python manage.py update_momentum_scores --update-universe
```

#### Execute Rebalancing
```bash
# Execute rebalancing
python manage.py execute_rebalance --portfolio "Portfolio Name"

# Dry run (no actual trades)
python manage.py execute_rebalance --portfolio "Portfolio Name" --dry-run

# Force rebalance (ignore frequency settings)
python manage.py execute_rebalance --portfolio "Portfolio Name" --force
```

#### Backfill Historical Data
```bash
# Backfill 420 days for all stocks
python manage.py backfill_data

# Backfill specific stocks
python manage.py backfill_data --tickers AAPL MSFT

# Backfill with custom parameters
python manage.py backfill_data --days 600 --batch-size 5
```

#### Sync Portfolio
```bash
# Sync positions only
python manage.py sync_portfolio --portfolio "Portfolio Name"

# Sync positions and update trade statuses
python manage.py sync_portfolio --portfolio "Portfolio Name" --update-trades
```

## 📈 Web Interface

Access the web dashboard at `http://localhost:8000/` to:

- Monitor momentum scores and rankings
- View portfolio performance and positions
- Track trading signals and execution
- Analyze rebalancing events
- Manage portfolios through admin interface

### Key Pages:

- **Dashboard**: Overview of momentum statistics and portfolio summaries
- **Portfolio Details**: Individual portfolio performance, positions, and trades
- **Momentum Scores**: Current stock rankings and momentum calculations
- **Trading Signals**: Recent buy/sell signals and execution status

## 🏗 Architecture

```
momentum_trader/
├── trading/                 # Core trading logic
│   ├── models.py           # Stock, PriceData, MomentumScore, TradingSignal
│   ├── services/           # Business logic services
│   │   ├── massive_client.py        # Massive API integration
│   │   ├── momentum_calculator.py   # Momentum calculation engine
│   │   ├── snaptrade_client.py     # SnapTrade API integration
│   │   └── strategy_engine.py      # Trading strategy execution
│   ├── management/commands/ # CLI management commands
│   └── templates/          # Web interface templates
├── portfolio/              # Portfolio management
│   └── models.py          # Portfolio, Position, Trade, PerformanceMetric
└── momentum_trader/       # Django project settings
```

## 📊 Database Schema

### Core Models:

- **Stock**: Stock information and metadata
- **PriceData**: Historical OHLCV price data
- **MomentumScore**: Calculated momentum scores and rankings
- **TradingSignal**: Buy/sell signals generated by the strategy
- **Portfolio**: Portfolio configuration and current state
- **Position**: Current stock positions and P&L
- **Trade**: Individual trade records and execution status
- **RebalanceEvent**: Rebalancing event tracking

## 🔧 Configuration

Key settings in `settings.py`:

```python
# Trading Strategy Configuration
MOMENTUM_LOOKBACK_MONTHS = 12    # Momentum calculation period
MOMENTUM_SKIP_MONTHS = 1         # Skip recent month for calculation
REBALANCE_FREQUENCY = 'weekly'   # 'weekly' or 'monthly'
TOP_QUINTILE_THRESHOLD = 20      # Top 20% of stocks

# API Configuration
MASSIVE_API_KEY = 'your_key'
SNAPTRADE_CLIENT_ID = 'your_client_id'
SNAPTRADE_CLIENT_SECRET = 'your_secret'
```

## 🚨 Important Notes

### Risk Disclaimers

- **Educational Purpose**: This system is built for educational and tutorial purposes
- **Paper Trading**: Test thoroughly with paper trading before using real money
- **Market Risk**: All trading involves risk of loss
- **No Guarantees**: Past performance does not guarantee future results

### Production Considerations

- Use PostgreSQL for production database
- Set up proper logging and monitoring
- Implement comprehensive error handling
- Add position sizing and risk management rules
- Consider transaction costs in strategy calculations
- Implement proper security measures for API keys

## 🔍 Monitoring & Troubleshooting

### Common Issues

1. **Insufficient Data**: Ensure stocks have at least 280 trading days of data
2. **API Rate Limits**: Implement appropriate delays between API calls
3. **Market Hours**: Consider market hours for real-time operations
4. **Data Quality**: Validate price data for corporate actions and splits

### Logging

The system uses Django's logging framework. Key log messages include:
- Momentum calculation progress and results
- Trading signal generation and execution
- Portfolio synchronization status
- API call successes and failures

## 📝 License

This project is created for educational purposes as part of a freeCodeCamp tutorial.

## 🤝 Contributing

This is a tutorial project, but feedback and suggestions are welcome for educational improvements.

## 📞 Support

For questions about this tutorial project, refer to the freeCodeCamp course materials or community forums.