from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

from trading.services.momentum_calculator import get_momentum_calculator
from trading.services.strategy_engine import get_strategy_engine
from portfolio.models import Portfolio
from trading.models import Stock

logger = logging.getLogger(__name__)


@shared_task
def calculate_momentum_scores_task(stock_ids=None, calculation_date=None):
    """
    Background task to calculate momentum scores for stocks
    """
    try:
        momentum_calculator = get_momentum_calculator()
        
        if calculation_date:
            from datetime import datetime
            calculation_date = datetime.strptime(calculation_date, '%Y-%m-%d').date()
        else:
            calculation_date = timezone.now().date()
        
        if stock_ids:
            stocks = Stock.objects.filter(id__in=stock_ids, is_active=True)
        else:
            stocks = Stock.objects.filter(is_active=True)
        
        momentum_scores = momentum_calculator.calculate_momentum_scores_bulk(
            stock_list=list(stocks),
            calculation_date=calculation_date
        )
        
        # Rank stocks and calculate quintiles
        momentum_calculator.rank_stocks_by_momentum(calculation_date)
        
        logger.info(f"Calculated momentum scores for {len(momentum_scores)} stocks")
        return {
            'success': True,
            'scores_calculated': len(momentum_scores),
            'calculation_date': calculation_date.isoformat()
        }
        
    except ValueError as e:
        logger.error(f"Error in calculate_momentum_scores_task: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def execute_rebalance_task(portfolio_id, calculation_date=None):
    """
    Background task to execute portfolio rebalancing
    """
    try:
        portfolio = Portfolio.objects.get(id=portfolio_id)
        
        if calculation_date:
            from datetime import datetime
            calculation_date = datetime.strptime(calculation_date, '%Y-%m-%d').date()
        else:
            calculation_date = timezone.now().date()
        
        strategy_engine = get_strategy_engine(portfolio)
        rebalance_event = strategy_engine.execute_rebalance(calculation_date)
        
        logger.info(f"Executed rebalance for portfolio {portfolio.name}")
        return {
            'success': True,
            'rebalance_event_id': rebalance_event.id,
            'status': rebalance_event.execution_status,
            'buy_signals': rebalance_event.buy_signals_generated,
            'sell_signals': rebalance_event.sell_signals_generated
        }
        
    except ValueError as e:
        logger.error(f"Error in execute_rebalance_task: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def sync_portfolio_task(portfolio_id):
    """
    Background task to sync portfolio positions with broker
    """
    try:
        portfolio = Portfolio.objects.get(id=portfolio_id)
        
        from trading.services.snaptrade_client import get_trading_executor
        trading_executor = get_trading_executor()
        
        positions = trading_executor.sync_portfolio_positions(portfolio)
        
        logger.info(f"Synced {len(positions)} positions for portfolio {portfolio.name}")
        return {
            'success': True,
            'positions_synced': len(positions),
            'portfolio_value': float(portfolio.total_value)
        }
        
    except ValueError as e:
        logger.error(f"Error in sync_portfolio_task: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def backfill_price_data_task(stock_ids, days_back=420):
    """
    Background task to backfill historical price data
    """

    momentum_calculator = get_momentum_calculator()
    stocks = Stock.objects.filter(id__in=stock_ids, is_active=True)
    
    total_new_records = 0
    for stock in stocks:
        new_records = momentum_calculator.backfill_price_data(stock, days_back)
        total_new_records += new_records
    
    logger.info(f"Backfilled {total_new_records} records for {len(stocks)} stocks")
    return {
        'success': True,
        'stocks_processed': len(stocks),
        'new_records': total_new_records
    }
        


@shared_task
def daily_momentum_update():
    """
    Daily scheduled task to update momentum scores for all active stocks
    """
    # Calculate momentum scores
    result = calculate_momentum_scores_task.apply()
    
    if result.get('success'):
        logger.info("Daily momentum update completed successfully")
        return {
            'success': True,
            'scores_calculated': result.get('scores_calculated', 0)
        }
    else:
        logger.error(f"Daily momentum update failed: {result.get('error')}")
        return result

@shared_task
def scheduled_rebalance():
    """
    Scheduled task to check and execute rebalancing for all active portfolios
    """
    try:
        portfolios = Portfolio.objects.filter(is_active=True)
        results = []
        
        for portfolio in portfolios:
            try:
                strategy_engine = get_strategy_engine(portfolio)
                
                if strategy_engine.should_rebalance():
                    result = execute_rebalance_task.apply(args=[portfolio.id])
                    results.append({
                        'portfolio': portfolio.name,
                        'rebalanced': True,
                        'result': result
                    })
                else:
                    results.append({
                        'portfolio': portfolio.name,
                        'rebalanced': False,
                        'reason': 'Not scheduled for rebalance'
                    })
                    
            except ValueError as e:
                logger.error(f"Error rebalancing portfolio {portfolio.name}: {str(e)}")
                results.append({
                    'portfolio': portfolio.name,
                    'rebalanced': False,
                    'error': str(e)
                })
        
        return {
            'success': True,
            'portfolios_processed': len(portfolios),
            'results': results
        }
        
    except ValueError as e:
        logger.error(f"Error in scheduled_rebalance: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }