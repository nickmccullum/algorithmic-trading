#!/usr/bin/env python3

import click
import os
from dotenv import load_dotenv
from tabulate import tabulate
from colorama import init, Fore, Style

from covered_call_analyzer import CoveredCallAnalyzer
from snaptrade_client import SnapTradeClient
from position_manager import PositionManager

# Initialize colorama for colored output
init(autoreset=True)

# Load environment variables
load_dotenv()

@click.group()
def cli():
    """Covered Call Trading CLI Tool"""
    pass

@cli.command()
@click.argument('ticker')
@click.option('--shares', default=100, help='Number of shares owned (default: 100)')
@click.option('--limit', default=10, help='Max number of opportunities to show (default: 10)')
def analyze(ticker, shares, limit):
    """Analyze covered call opportunities for a given stock ticker"""
    
    try:
        click.echo(f"\n{Fore.CYAN}Analyzing covered call opportunities for {ticker.upper()}{Style.RESET_ALL}")
        click.echo(f"Shares owned: {shares}")
        click.echo("=" * 60)
        
        analyzer = CoveredCallAnalyzer()
        opportunities = analyzer.analyze_covered_calls(ticker.upper(), shares)
        
        if not opportunities:
            click.echo(f"{Fore.YELLOW}No suitable covered call opportunities found for {ticker.upper()}{Style.RESET_ALL}")
            return
        
        # Display top opportunities
        display_opportunities(opportunities[:limit])
        
        # Show the best recommendation
        best = opportunities[0]
        click.echo(f"\n{Fore.GREEN}📈 BEST RECOMMENDATION:{Style.RESET_ALL}")
        click.echo(f"Contract: {best.contract.ticker}")
        click.echo(f"Strike: ${best.contract.strike:.2f}")
        click.echo(f"Expiration: {best.contract.expiration_date}")
        click.echo(f"Premium: ${best.quote.mid:.2f}")
        click.echo(f"Annual Return: {best.annual_return:.1%}")
        click.echo(f"Score: {best.score:.2f}/1.00")
        
    except Exception as e:
        click.echo(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")

@cli.command()
@click.argument('ticker')
@click.option('--shares', default=100, help='Number of shares owned (default: 100)')
@click.option('--execute', is_flag=True, help='Actually place the trade (requires SnapTrade setup)')
def trade(ticker, shares, execute):
    """Find and optionally execute the best covered call trade"""
    
    try:
        analyzer = CoveredCallAnalyzer()
        best_opportunity = analyzer.get_best_covered_call(ticker.upper(), shares)
        
        if not best_opportunity:
            click.echo(f"{Fore.YELLOW}No suitable covered call found for {ticker.upper()}{Style.RESET_ALL}")
            return
        
        click.echo(f"\n{Fore.CYAN}Best Covered Call Opportunity:{Style.RESET_ALL}")
        display_single_opportunity(best_opportunity)
        
        if execute:
            if click.confirm(f"\nProceed with selling {best_opportunity.contract.ticker}?"):
                try:
                    snaptrade = SnapTradeClient()
                    accounts = snaptrade.get_accounts()
                    
                    if not accounts:
                        click.echo(f"{Fore.RED}No trading accounts found{Style.RESET_ALL}")
                        return
                    
                    # Use first account for now
                    account_id = accounts[0]['id']
                    
                    result = snaptrade.sell_covered_call(
                        account_id=account_id,
                        option_symbol=best_opportunity.contract.ticker,
                        contracts=shares // 100
                    )
                    
                    if result.get('success'):
                        click.echo(f"{Fore.GREEN}✅ Trade executed successfully!{Style.RESET_ALL}")
                    else:
                        click.echo(f"{Fore.RED}❌ Trade failed: {result.get('message', 'Unknown error')}{Style.RESET_ALL}")
                        
                except Exception as e:
                    click.echo(f"{Fore.RED}Error executing trade: {e}{Style.RESET_ALL}")
        else:
            click.echo(f"\n{Fore.YELLOW}Use --execute flag to place the actual trade{Style.RESET_ALL}")
            
    except Exception as e:
        click.echo(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")

@cli.command()
@click.option('--account-id', help='Specific account ID to check')
def positions(account_id):
    """View current covered call positions"""
    
    try:
        manager = PositionManager()
        snaptrade = SnapTradeClient()
        
        if not account_id:
            accounts = snaptrade.get_accounts()
            if not accounts:
                click.echo(f"{Fore.RED}No trading accounts found{Style.RESET_ALL}")
                return
            account_id = accounts[0]['id']
        
        positions = manager.get_covered_call_positions(account_id)
        
        if not positions:
            click.echo(f"{Fore.YELLOW}No covered call positions found{Style.RESET_ALL}")
            return
        
        click.echo(f"\n{Fore.CYAN}Current Covered Call Positions:{Style.RESET_ALL}")
        click.echo("=" * 80)
        
        for position in positions:
            action_needed, reason = manager.check_management_rules(position)
            
            status_color = Fore.RED if action_needed else Fore.GREEN
            click.echo(f"\n{Fore.CYAN}{position.underlying_symbol} - {position.option_symbol}{Style.RESET_ALL}")
            click.echo(f"Stock Qty: {position.stock_quantity} | Calls Sold: {position.option_quantity}")
            click.echo(f"Strike: ${position.strike_price:.2f} | Expiration: {position.expiration_date}")
            click.echo(f"DTE: {position.days_to_expiration} | P&L: ${position.unrealized_pnl:.2f}")
            click.echo(f"{status_color}Status: {reason}{Style.RESET_ALL}")
            
            if action_needed and "ROLL" in reason:
                click.echo(f"\n{Fore.YELLOW}Suggested roll options:{Style.RESET_ALL}")
                roll_options = manager.suggest_roll_options(position)
                for i, option in enumerate(roll_options[:3], 1):
                    click.echo(f"  {i}. {option.contract.ticker} - ${option.quote.mid:.2f} premium")
        
    except Exception as e:
        click.echo(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")

@cli.command()
def setup():
    """Setup API credentials"""
    
    click.echo(f"{Fore.CYAN}Covered Call CLI Setup{Style.RESET_ALL}")
    click.echo("=" * 30)
    
    env_file = ".env"
    env_example = ".env.example"
    
    if os.path.exists(env_file):
        if not click.confirm("Environment file exists. Overwrite?"):
            return
    
    # Copy example file
    if os.path.exists(env_example):
        with open(env_example, 'r') as f:
            content = f.read()
        
        click.echo(f"\nPlease provide the following API credentials:")
        click.echo(f"{Fore.YELLOW}Get Polygon API key at: https://polygon.io{Style.RESET_ALL}")
        click.echo(f"{Fore.YELLOW}Get SnapTrade credentials at: https://snaptrade.com{Style.RESET_ALL}\n")
        
        polygon_key = click.prompt("Polygon API Key", type=str)
        snap_consumer = click.prompt("SnapTrade Consumer Key", type=str)
        snap_client_id = click.prompt("SnapTrade Client ID", type=str)
        snap_user_id = click.prompt("SnapTrade User ID", type=str)
        snap_user_secret = click.prompt("SnapTrade User Secret", type=str, hide_input=True)
        
        env_content = f"""POLYGON_API_KEY={polygon_key}
SNAPTRADE_CONSUMER_KEY={snap_consumer}
SNAPTRADE_CLIENT_ID={snap_client_id}
SNAPTRADE_USER_ID={snap_user_id}
SNAPTRADE_USER_SECRET={snap_user_secret}"""
        
        with open(env_file, 'w') as f:
            f.write(env_content)
        
        click.echo(f"\n{Fore.GREEN}✅ Configuration saved to {env_file}{Style.RESET_ALL}")
        click.echo(f"{Fore.YELLOW}You can now use the CLI commands!{Style.RESET_ALL}")
    else:
        click.echo(f"{Fore.RED}Error: .env.example file not found{Style.RESET_ALL}")

def display_opportunities(opportunities):
    """Display opportunities in a formatted table"""
    
    headers = ["Contract", "Strike", "Exp", "Premium", "Delta", "DTE", "Annual Return", "Score"]
    rows = []
    
    for opp in opportunities:
        rows.append([
            opp.contract.ticker,
            f"${opp.contract.strike:.2f}",
            opp.contract.expiration_date,
            f"${opp.quote.mid:.2f}",
            f"{opp.quote.delta:.3f}" if opp.quote.delta else "N/A",
            opp.dte,
            f"{opp.annual_return:.1%}",
            f"{opp.score:.3f}"
        ])
    
    click.echo(tabulate(rows, headers=headers, tablefmt="grid"))

def display_single_opportunity(opportunity):
    """Display single opportunity details"""
    
    click.echo(f"Contract: {opportunity.contract.ticker}")
    click.echo(f"Strike: ${opportunity.contract.strike:.2f}")
    click.echo(f"Expiration: {opportunity.contract.expiration_date}")
    click.echo(f"Days to Expiration: {opportunity.dte}")
    click.echo(f"Premium (Mid): ${opportunity.quote.mid:.2f}")
    click.echo(f"Delta: {opportunity.quote.delta:.3f}" if opportunity.quote.delta else "Delta: N/A")
    click.echo(f"Annual Return: {opportunity.annual_return:.1%}")
    click.echo(f"Return if Assigned: {opportunity.return_if_assigned:.1%}")
    click.echo(f"Breakeven: ${opportunity.breakeven:.2f}")
    click.echo(f"Max Profit: ${opportunity.max_profit:.2f}")
    click.echo(f"Probability of Profit: {opportunity.probability_profit:.1%}")
    click.echo(f"Score: {opportunity.score:.3f}/1.00")

if __name__ == '__main__':
    cli()