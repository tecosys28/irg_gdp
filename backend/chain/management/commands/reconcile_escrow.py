"""
Daily escrow reconciliation — matches EscrowVault on-chain events against
the trustee bank's statement for a given date.

Usage:
    # Reconcile today (no bank statement yet — PARTIAL result):
    python manage.py reconcile_escrow

    # Reconcile a specific date with bank total:
    python manage.py reconcile_escrow --date 2026-04-20 --bank-credits-inr 4750000

    # Reconcile last N days (useful after a weekend):
    python manage.py reconcile_escrow --days 3

A DISCREPANCY result means on-chain totals don't match the bank figure.
The ops team must investigate and resolve before new redemptions are accepted.
See docs/DEPLOYMENT.md §7.4 for the fix matrix.

IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
import logging
from datetime import date, datetime, timedelta, timezone as dt_tz

from django.conf import settings
from django.core.management.base import BaseCommand
from web3 import Web3

from chain.models import EscrowReconciliationLog

logger = logging.getLogger(__name__)

ESCROW_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True,  "name": "escrowId",      "type": "bytes32"},
            {"indexed": False, "name": "lotId",         "type": "bytes32"},
            {"indexed": False, "name": "holder",        "type": "address"},
            {"indexed": False, "name": "minter",        "type": "address"},
            {"indexed": False, "name": "amountINR",     "type": "uint256"},
            {"indexed": False, "name": "expiresAt",     "type": "uint256"},
            {"indexed": False, "name": "timestamp",     "type": "uint256"},
        ],
        "name": "EscrowLocked",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True,  "name": "escrowId",         "type": "bytes32"},
            {"indexed": False, "name": "minter",           "type": "address"},
            {"indexed": False, "name": "amountINR",        "type": "uint256"},
            {"indexed": False, "name": "bankConfirmRef",   "type": "bytes32"},
            {"indexed": False, "name": "timestamp",        "type": "uint256"},
        ],
        "name": "EscrowReleasedToMinter",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True,  "name": "escrowId",   "type": "bytes32"},
            {"indexed": False, "name": "holder",     "type": "address"},
            {"indexed": False, "name": "amountINR",  "type": "uint256"},
            {"indexed": False, "name": "reason",     "type": "string"},
            {"indexed": False, "name": "timestamp",  "type": "uint256"},
        ],
        "name": "EscrowRefundedToHolder",
        "type": "event",
    },
]


def _day_bounds_unix(d: date):
    start = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=dt_tz.utc)
    end = start + timedelta(days=1)
    return int(start.timestamp()), int(end.timestamp())


def _logs_for_day(event, from_block, to_block, day_start_ts, day_end_ts):
    all_logs = event.get_logs(fromBlock=from_block, toBlock=to_block)
    return [
        l for l in all_logs
        if day_start_ts <= int(l['args'].get('timestamp', 0)) < day_end_ts
    ]


class Command(BaseCommand):
    help = 'Reconcile EscrowVault on-chain events against the trustee bank statement.'

    def add_arguments(self, parser):
        parser.add_argument('--date', type=str, default='',
                            help='ISO date to reconcile (default: today).')
        parser.add_argument('--days', type=int, default=1,
                            help='Number of days to reconcile ending on --date.')
        parser.add_argument('--bank-credits-inr', type=int, default=0,
                            help='Total INR credited by the trustee bank for the period.')
        parser.add_argument('--scan-blocks', type=int, default=50000,
                            help='Number of recent blocks to scan for events.')

    def handle(self, *args, **opts):
        rpc_url = settings.BLOCKCHAIN_CONFIG.get('RPC_URL')
        contract_addr = settings.CONTRACT_ADDRESSES.get('EscrowVault', '')
        if not contract_addr:
            self.stderr.write('EscrowVault contract address not set in CONTRACT_ADDRESSES; exiting.')
            return

        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not w3.is_connected():
            self.stderr.write(f'Cannot connect to Besu RPC at {rpc_url}')
            return

        contract = w3.eth.contract(address=Web3.to_checksum_address(contract_addr), abi=ESCROW_ABI)

        target_date_str = opts.get('date') or ''
        target_date = (
            date.fromisoformat(target_date_str) if target_date_str
            else date.today()
        )
        days = max(1, int(opts.get('days') or 1))
        bank_credits = int(opts.get('bank_credits_inr') or 0)
        scan_blocks = int(opts.get('scan_blocks') or 50000)

        head = w3.eth.block_number
        from_block = max(0, head - scan_blocks)

        for offset in range(days - 1, -1, -1):
            run_date = target_date - timedelta(days=offset)
            self._reconcile_day(
                w3=w3,
                contract=contract,
                run_date=run_date,
                from_block=from_block,
                to_block=head,
                bank_credits=bank_credits if offset == 0 else 0,
            )

    def _reconcile_day(self, *, w3, contract, run_date, from_block, to_block, bank_credits):
        day_start, day_end = _day_bounds_unix(run_date)

        try:
            locked_logs = _logs_for_day(
                contract.events.EscrowLocked, from_block, to_block, day_start, day_end)
            released_logs = _logs_for_day(
                contract.events.EscrowReleasedToMinter, from_block, to_block, day_start, day_end)
            refunded_logs = _logs_for_day(
                contract.events.EscrowRefundedToHolder, from_block, to_block, day_start, day_end)
        except Exception as exc:  # noqa: BLE001
            logger.exception('RPC error during reconciliation for %s: %s', run_date, exc)
            EscrowReconciliationLog.objects.create(
                run_date=run_date,
                status='ERROR',
                notes=str(exc),
            )
            self.stderr.write(f'Reconciliation FAILED for {run_date}: {exc}')
            return

        total_locked = sum(int(l['args']['amountINR']) for l in locked_logs)
        total_released = sum(int(l['args']['amountINR']) for l in released_logs)
        total_refunded = sum(int(l['args']['amountINR']) for l in refunded_logs)

        # Net settled = released (bank paid out to minters).
        # Discrepancy = bank credits vs on-chain released total.
        discrepancy = 0
        if bank_credits > 0:
            discrepancy = bank_credits - total_released
            status = 'OK' if discrepancy == 0 else 'DISCREPANCY'
        else:
            status = 'PARTIAL'

        notes_parts = [
            f'Locked events: {len(locked_logs)}, Released: {len(released_logs)}, Refunded: {len(refunded_logs)}.',
        ]
        if bank_credits == 0:
            notes_parts.append('No bank statement provided — rerun with --bank-credits-inr to finalise.')
        if discrepancy != 0:
            notes_parts.append(
                f'DISCREPANCY: bank reported {bank_credits} INR, chain shows {total_released} INR released. '
                f'Delta: {discrepancy} INR. Halt new redemptions and investigate.'
            )

        EscrowReconciliationLog.objects.update_or_create(
            run_date=run_date,
            defaults=dict(
                status=status,
                escrow_locked_count=len(locked_logs),
                escrow_released_count=len(released_logs),
                escrow_refunded_count=len(refunded_logs),
                total_locked_inr=total_locked,
                total_released_inr=total_released,
                total_refunded_inr=total_refunded,
                bank_credits_inr=bank_credits,
                discrepancy_inr=discrepancy,
                notes=' '.join(notes_parts),
            ),
        )

        line = (
            f'{run_date}  locked={len(locked_logs)} (₹{total_locked})  '
            f'released={len(released_logs)} (₹{total_released})  '
            f'refunded={len(refunded_logs)} (₹{total_refunded})  '
            f'bank=₹{bank_credits}  status={status}'
        )
        if status == 'DISCREPANCY':
            self.stderr.write(f'DISCREPANCY  {line}')
        else:
            self.stdout.write(line)
