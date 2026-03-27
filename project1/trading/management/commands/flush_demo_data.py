from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from trading.models import Stock, PriceData, MomentumScore, TradingSignal, RebalanceEvent
from portfolio.models import Portfolio, Position, Trade, PerformanceMetric


class Command(BaseCommand):
    help = 'Flush all demo data from database except Stock tickers (for clean demo setup)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm that you want to delete the data (required for safety)',
        )
        parser.add_argument(
            '--delete-stocks',
            action='store_true',
            help='Also delete Stock records (by default, stocks are kept)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        if not options['confirm'] and not options['dry_run']:
            raise CommandError(
                'This command will delete data! Use --confirm to proceed or --dry-run to preview.'
            )

        # Define models to flush (in dependency order - children first)
        models_to_flush = [
            # Portfolio models (dependent on Stock)
            (PerformanceMetric, "Performance metrics"),
            (Trade, "Trades"),
            (Position, "Portfolio positions"),
            (Portfolio, "Portfolios"),
            
            # Trading models (dependent on Stock)
            (RebalanceEvent, "Rebalance events"),
            (TradingSignal, "Trading signals"),
            (MomentumScore, "Momentum scores"),
            (PriceData, "Price data"),
        ]

        self.stdout.write(
            self.style.WARNING(
                f"{'DRY RUN: ' if options['dry_run'] else ''}Preparing to flush demo data..."
            )
        )
        
        # Count records before deletion
        total_records = 0
        deletion_plan = []
        
        for model, description in models_to_flush:
            count = model.objects.count()
            total_records += count
            if count > 0:
                deletion_plan.append((model, description, count))
                self.stdout.write(f"  • {description}: {count} records")
        
        # Show Stock info
        stock_count = Stock.objects.count()
        if options['delete_stocks']:
            deletion_plan.append((Stock, "Stock tickers", stock_count))
            total_records += stock_count
            self.stdout.write(f"  • Stock tickers: {stock_count} records")
        else:
            self.stdout.write(
                self.style.SUCCESS(f"  • Stock tickers: {stock_count} records (KEEPING)")
            )

        if total_records == 0:
            self.stdout.write(self.style.SUCCESS("No data to delete. Database is already clean."))
            return

        self.stdout.write(f"\nTotal records to delete: {total_records}")

        if options['dry_run']:
            self.stdout.write(
                self.style.SUCCESS("DRY RUN complete. No data was actually deleted.")
            )
            return

        # Confirm one more time
        self.stdout.write(
            self.style.WARNING(
                "\n⚠️  WARNING: This will permanently delete the data listed above!"
            )
        )

        # Perform the deletion
        try:
            with transaction.atomic():
                deleted_total = 0
                
                for model, description, count in deletion_plan:
                    if count > 0:
                        self.stdout.write(f"Deleting {description}...")
                        deleted_count, deleted_details = model.objects.all().delete()
                        deleted_total += deleted_count
                        self.stdout.write(
                            self.style.SUCCESS(f"  ✓ Deleted {deleted_count} {description.lower()}")
                        )

                # Reset Stock fields if keeping stocks but want to clean them up
                if not options['delete_stocks']:
                    updated_stocks = Stock.objects.update(
                        sector='',
                        market_cap=None,
                        updated_at=timezone.now()
                    )
                    if updated_stocks > 0:
                        self.stdout.write(
                            self.style.SUCCESS(f"  ✓ Reset {updated_stocks} stock records (cleared sector/market_cap)")
                        )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"\n🎉 Successfully deleted {deleted_total} records!"
                    )
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        "Database is now ready for a fresh demo."
                    )
                )

        except Exception as e:
            raise CommandError(f"Error during deletion: {str(e)}")

        # Show final stats
        self.stdout.write("\n📊 Final database state:")
        remaining_models = [
            (Stock, "Stock tickers"),
            (PriceData, "Price data records"),
            (MomentumScore, "Momentum scores"),
            (TradingSignal, "Trading signals"),
            (RebalanceEvent, "Rebalance events"),
            (Portfolio, "Portfolios"),
            (Position, "Positions"),
            (Trade, "Trades"),
            (PerformanceMetric, "Performance metrics"),
        ]
        
        for model, description in remaining_models:
            count = model.objects.count()
            style = self.style.SUCCESS if count == 0 or (model == Stock and not options['delete_stocks']) else self.style.WARNING
            self.stdout.write(style(f"  • {description}: {count} records"))

        if not options['delete_stocks']:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✨ Demo setup complete! You have {Stock.objects.count()} stock tickers ready for fresh calculations."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "\n✨ Complete database flush finished. Ready for fresh setup."
                )
            )