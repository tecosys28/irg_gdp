"""
Monthly TSF (Token Support Fund) cycle — calls TSFEngine.runTSFCycle() on
IRG Chain 888101 to credit Stream 2 GIC allocations to licensees.

Usage (run on the 1st of each month or via cron):
    python manage.py run_monthly_tsf

The system signer key must be loaded in BLOCKCHAIN_CONFIG / SYSTEM_SIGNER_KEY.
The call is idempotent — TSFEngine.isCycleRan(period) will revert if the
cycle for the current period has already run, so re-running is safe.

Post-run: check the TSFCycleRun event in the tx receipt and reconcile
Stream 2 credits per the weekly ops review.

IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
import logging
import uuid
from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand

from chain.client import SystemTx, system_submit

logger = logging.getLogger(__name__)

TSF_ENGINE_ABI_FRAGMENT = [{
    "inputs": [],
    "name": "runTSFCycle",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function",
}]


def _encode_run_tsf_cycle() -> str | None:
    try:
        from web3 import Web3
        selector = Web3.keccak(text='runTSFCycle()')[:4].hex()
        return '0x' + selector
    except Exception:  # noqa: BLE001
        return None


class Command(BaseCommand):
    help = 'Run the monthly TSF cycle on IRG Chain 888101 (credits GIC Stream 2 to licensees).'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Log what would be submitted without sending to chain.')

    def handle(self, *args, **opts):
        contract_addr = settings.CONTRACT_ADDRESSES.get('TSFEngine', '')
        if not contract_addr:
            self.stderr.write('TSFEngine contract address not set in CONTRACT_ADDRESSES; exiting.')
            return

        calldata = _encode_run_tsf_cycle()
        period = date.today().strftime('%Y-%m')
        client_tx_id = f'tsf-cycle-{period}-{uuid.uuid4().hex[:8]}'

        tx = SystemTx(
            client_tx_id=client_tx_id,
            module='irg_gic',
            action='run_tsf_cycle',
            to_address=contract_addr,
            data=calldata or '0x',
            meta={'period': period},
        )

        if opts.get('dry_run'):
            self.stdout.write(f'[DRY RUN] Would submit TSF cycle for {period}: {tx}')
            return

        result = system_submit(tx)
        if result.success:
            self.stdout.write(f'TSF cycle submitted for {period}: tx={result.tx_hash}')
            logger.info('TSF cycle %s submitted: %s', period, result.tx_hash)
        else:
            self.stderr.write(f'TSF cycle submission FAILED for {period}: {result.error}')
            logger.error('TSF cycle %s failed: %s', period, result.error)
            raise SystemExit(1)
