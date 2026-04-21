"""
Monthly referral engine flush — calls ReferralEngine.flushReferrals() on
IRG Chain 888101 to credit Stream 3 (referral) GIC allocations to licensees.

Usage (run monthly, after run_monthly_tsf):
    python manage.py run_referral_flush

The call batches all pending referral credits accumulated since the last
flush and emits ReferralBatchCredited events for each licensee.

The system signer must hold the OPERATOR role on ReferralEngine.

IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
import logging
import uuid
from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand

from chain.client import SystemTx, system_submit

logger = logging.getLogger(__name__)


def _encode_flush_referrals() -> str | None:
    try:
        from web3 import Web3
        selector = Web3.keccak(text='flushReferrals()')[:4].hex()
        return '0x' + selector
    except Exception:  # noqa: BLE001
        return None


class Command(BaseCommand):
    help = 'Flush pending referral credits on IRG Chain 888101 (credits GIC Stream 3).'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Log what would be submitted without sending to chain.')

    def handle(self, *args, **opts):
        contract_addr = settings.CONTRACT_ADDRESSES.get('ReferralEngine', '')
        if not contract_addr:
            self.stderr.write('ReferralEngine contract address not set in CONTRACT_ADDRESSES; exiting.')
            return

        calldata = _encode_flush_referrals()
        period = date.today().strftime('%Y-%m')
        client_tx_id = f'referral-flush-{period}-{uuid.uuid4().hex[:8]}'

        tx = SystemTx(
            client_tx_id=client_tx_id,
            module='irg_gic',
            action='flush_referrals',
            to_address=contract_addr,
            data=calldata or '0x',
            meta={'period': period},
        )

        if opts.get('dry_run'):
            self.stdout.write(f'[DRY RUN] Would flush referrals for {period}: {tx}')
            return

        result = system_submit(tx)
        if result.success:
            self.stdout.write(f'Referral flush submitted for {period}: tx={result.tx_hash}')
            logger.info('Referral flush %s submitted: %s', period, result.tx_hash)
        else:
            self.stderr.write(f'Referral flush FAILED for {period}: {result.error}')
            logger.error('Referral flush %s failed: %s', period, result.error)
            raise SystemExit(1)
