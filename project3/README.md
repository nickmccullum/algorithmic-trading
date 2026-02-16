# Covered Call Trading CLI

A Python CLI tool for automated covered call option analysis and trading. This tool helps you identify the best call options to sell against your stock holdings for additional income.

## Features

- **Option Analysis**: Finds optimal call options based on delta (15-30), days to expiration (30-45), and other criteria
- **Risk Assessment**: Calculates annual returns, breakeven points, and probability of profit
- **Position Management**: Tracks existing covered call positions and suggests when to close or roll
- **Trade Execution**: Integrates with SnapTrade for actual order placement
- **Comprehensive Scoring**: Ranks opportunities based on multiple factors including delta, returns, and liquidity

## Strategy Overview

### Covered Call Mechanics
- **Hold Stock**: Own 100 shares per option contract
- **Sell Calls**: Sell call options 15-30 delta (70-85% probability OTM)
- **Target DTE**: 30-45 days to expiration for optimal theta decay
- **Management**: Close at 50% profit or roll at 21 DTE

### Risk/Reward Targets

| Delta | Probability OTM | Premium Level | Assignment Risk |
|-------|----------------|---------------|-----------------|
| 0.20Δ | ~80% | Moderate | Low |
| 0.25Δ | ~75% | Higher | Moderate |
| 0.30Δ | ~70% | High | Elevated |

## Installation

1. **Clone and Setup**:
   ```bash
   cd project3
   pip install -r requirements.txt
   ```

2. **Configure API Keys**:
   ```bash
   python cli.py setup
   ```
   
   You'll need:
   - **Polygon API Key**: Get from [polygon.io](https://polygon.io) for options data
   - **SnapTrade Credentials**: Get from [snaptrade.com](https://snaptrade.com) for trading

3. **Make CLI Executable** (optional):
   ```bash
   chmod +x cli.py
   ```

## Usage

### Analyze Covered Call Opportunities

```bash
# Analyze AAPL for 100 shares
python cli.py analyze AAPL

# Analyze MSFT for 200 shares, show top 5 opportunities
python cli.py analyze MSFT --shares 200 --limit 5
```

**Example Output**:
```
Analyzing covered call opportunities for AAPL
Shares owned: 100
============================================================
Current stock price for AAPL: $150.25

┌─────────────────┬─────────┬────────────┬─────────┬─────────┬─────┬───────────────┬─────────┐
│ Contract        │ Strike  │ Exp        │ Premium │ Delta   │ DTE │ Annual Return │ Score   │
├─────────────────┼─────────┼────────────┼─────────┼─────────┼─────┼───────────────┼─────────┤
│ AAPL241220C155  │ $155.00 │ 2024-12-20 │ $2.45   │ 0.250   │ 35  │ 25.2%         │ 0.847   │
│ AAPL241220C160  │ $160.00 │ 2024-12-20 │ $1.85   │ 0.180   │ 35  │ 19.1%         │ 0.762   │
└─────────────────┴─────────┴────────────┴─────────┴─────────┴─────┴───────────────┴─────────┘

📈 BEST RECOMMENDATION:
Contract: AAPL241220C155
Strike: $155.00
Expiration: 2024-12-20
Premium: $2.45
Annual Return: 25.2%
Score: 0.85/1.00
```

### Execute Best Trade

```bash
# Find and show best trade (paper trading)
python cli.py trade AAPL

# Actually execute the trade
python cli.py trade AAPL --execute
```

### Monitor Positions

```bash
# View all covered call positions
python cli.py positions

# Check specific account
python cli.py positions --account-id your_account_id
```

**Example Output**:
```
Current Covered Call Positions:
================================================================================

AAPL - AAPL241220C155
Stock Qty: 100 | Calls Sold: 1
Strike: $155.00 | Expiration: 2024-12-20
DTE: 35 | P&L: $123.50
Status: HOLD: No action needed

MSFT - MSFT241215C420
Stock Qty: 100 | Calls Sold: 1
Strike: $420.00 | Expiration: 2024-12-15
DTE: 18 | P&L: $89.25
Status: ROLL: 18 DTE threshold reached

Suggested roll options:
  1. MSFT250117C425 - $3.20 premium
  2. MSFT250117C430 - $2.85 premium
  3. MSFT250124C425 - $3.45 premium
```

## Configuration

### Environment Variables

Create a `.env` file or use `python cli.py setup`:

```bash
POLYGON_API_KEY=your_polygon_api_key
SNAPTRADE_CONSUMER_KEY=your_snaptrade_consumer_key
SNAPTRADE_CLIENT_ID=your_snaptrade_client_id
SNAPTRADE_USER_ID=your_snaptrade_user_id
SNAPTRADE_USER_SECRET=your_snaptrade_user_secret
```

### Strategy Rules (config.py)

```python
COVERED_CALL_RULES = {
    "min_delta": 0.15,        # Minimum delta (15Δ)
    "max_delta": 0.30,        # Maximum delta (30Δ)
    "min_dte": 30,            # Minimum days to expiration
    "max_dte": 45,            # Maximum days to expiration
    "profit_target": 0.50,    # Close at 50% profit
    "roll_dte": 21,          # Roll when 21 DTE reached
}
```

## API Integration

### Polygon.io (Market Data)
- Real-time stock prices
- Options contracts and chains
- Greeks (delta, gamma, theta, vega)
- Implied volatility and volume

### SnapTrade (Brokerage)
- Account positions
- Order placement (single and multi-leg)
- Position management
- Trade execution

## CLI Commands

| Command | Description | Options |
|---------|-------------|---------|
| `analyze` | Find covered call opportunities | `--shares`, `--limit` |
| `trade` | Execute best opportunity | `--execute` |
| `positions` | View current positions | `--account-id` |
| `setup` | Configure API credentials | None |

## Scoring Algorithm

Opportunities are ranked based on:

- **Delta Score (25%)**: Preference for 20-25 delta
- **Return Score (25%)**: Higher annualized returns
- **Probability Score (20%)**: Higher probability of profit
- **DTE Score (15%)**: Optimal 30-45 day window
- **Volume Score (10%)**: Minimum liquidity requirements
- **Open Interest Score (5%)**: Market depth

## Risk Management

### Automatic Rules
- ✅ Close positions at 50% profit
- ✅ Roll positions at 21 DTE
- ✅ Filter by delta range (15-30Δ)
- ✅ Require minimum volume/open interest

### Manual Considerations
- Assignment risk at expiration
- Early assignment on dividend dates
- Volatility expansion risk
- Opportunity cost if stock rallies

## Examples

### Basic Workflow

1. **Analyze**: `python cli.py analyze AAPL --shares 300`
2. **Execute**: `python cli.py trade AAPL --execute` 
3. **Monitor**: `python cli.py positions`
4. **Manage**: Close/roll based on displayed recommendations

### Advanced Usage

```bash
# Batch analysis of multiple stocks
for stock in AAPL MSFT GOOGL TSLA; do
    echo "=== $stock ==="
    python cli.py analyze $stock --limit 3
done

# Monitor all positions daily
python cli.py positions | grep "ROLL\|CLOSE"
```

## Troubleshooting

### Common Issues

1. **API Key Errors**: Verify keys in `.env` file
2. **No Opportunities Found**: Check market hours and option availability
3. **Trade Execution Fails**: Ensure account has sufficient buying power and stock positions
4. **Data Timeouts**: Polygon free tier has rate limits

### Support

- Check API documentation: [Polygon](https://polygon.io/docs) | [SnapTrade](https://docs.snaptrade.com)
- Verify market hours (options trade 9:30 AM - 4:00 PM ET)
- Ensure stock positions exist before selling calls

---

**⚠️ Disclaimer**: This tool is for educational purposes. Options trading involves risk. Always verify trades and understand the risks before execution.