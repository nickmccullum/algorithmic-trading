from django.core.management.base import BaseCommand
from market_data.models import Index, ETF


class Command(BaseCommand):
    help = 'Set up default indices and ETFs for the trading system'

    def handle(self, *args, **options):
        indices_data = [
            {
                'name': 'S&P 500',
                'massive_ticker': 'I:SPX',
                'description': 'Tracks the 500 largest U.S. companies',
                'etf_ticker': 'SPY',
                'etf_name': 'SPDR S&P 500 ETF Trust'
            },
            {
                'name': 'NASDAQ-100',
                'massive_ticker': 'I:NDX',
                'description': 'Tracks the 100 largest non-financial NASDAQ companies',
                'etf_ticker': 'QQQ',
                'etf_name': 'Invesco QQQ Trust'
            },
            {
                'name': 'Dow Jones Industrial',
                'massive_ticker': 'I:DJI',
                'description': 'Tracks 30 large-cap U.S. blue-chip companies',
                'etf_ticker': 'DIA',
                'etf_name': 'SPDR Dow Jones Industrial Average ETF'
            },
            {
                'name': 'Russell 2000',
                'massive_ticker': 'I:RUT',
                'description': 'Tracks 2,000 small-cap U.S. companies',
                'etf_ticker': 'IWM',
                'etf_name': 'iShares Russell 2000 ETF'
            },
        ]

        created_count = 0

        for index_data in indices_data:
            # Create or get the index
            index, index_created = Index.objects.get_or_create(
                massive_ticker=index_data['massive_ticker'],
                defaults={
                    'name': index_data['name'],
                    'description': index_data['description']
                }
            )

            if index_created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created index: {index.name}')
                )
                created_count += 1

            # Create or get the ETF
            etf, etf_created = ETF.objects.get_or_create(
                ticker=index_data['etf_ticker'],
                defaults={
                    'index': index,
                    'name': index_data['etf_name']
                }
            )

            if etf_created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created ETF: {etf.ticker} for {index.name}')
                )
                created_count += 1

        if created_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'Successfully created {created_count} new records')
            )
        else:
            self.stdout.write(
                self.style.WARNING('All indices and ETFs already exist')
            )