"""
Watch WalletRecoveryEvents for WalletRecoveryRequested and RecoveryExecuted
events and surface them in the backend so the Ombudsman portal sees them.

Usage:
    python manage.py watch_chain_events

WalletRecoveryRequested  — fired when a backend files a trustee-path
    recovery case on-chain (services.initiate_trustee_recovery). This
    watcher confirms the event landed and marks the local RecoveryCase
    with the on-chain tx hash for the Ombudsman queue.

RecoveryExecuted — fired by WalletRecoveryEvents after the multisig
    calls executeRecovery. This watcher records the execution tx hash
    against the local case so the audit trail is complete.

Persists block cursor in ChainWatcherCursor (name: "chain_events").
Safe to restart.

IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
import logging
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from web3 import Web3

from chain.models import ChainWatcherCursor
from wallet_access.models import RecoveryCase, WalletActivation

logger = logging.getLogger(__name__)

WATCHER_NAME = 'chain_events'

# ABI subset — only the two events we care about.
# WalletRecoveryRequested(bytes32 indexed caseId, address indexed filer,
#     address oldWallet, address newWallet, uint8 path,
#     bytes32 evidenceHash, uint256 timestamp)
# RecoveryExecuted(bytes32 indexed caseId, address indexed oldWallet,
#     address indexed newWallet, uint256 timestamp)
EVENT_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True,  "name": "caseId",       "type": "bytes32"},
            {"indexed": True,  "name": "filer",        "type": "address"},
            {"indexed": False, "name": "oldWallet",    "type": "address"},
            {"indexed": False, "name": "newWallet",    "type": "address"},
            {"indexed": False, "name": "path",         "type": "uint8"},
            {"indexed": False, "name": "evidenceHash", "type": "bytes32"},
            {"indexed": False, "name": "timestamp",    "type": "uint256"},
        ],
        "name": "WalletRecoveryRequested",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True,  "name": "caseId",    "type": "bytes32"},
            {"indexed": True,  "name": "oldWallet", "type": "address"},
            {"indexed": True,  "name": "newWallet", "type": "address"},
            {"indexed": False, "name": "timestamp", "type": "uint256"},
        ],
        "name": "RecoveryExecuted",
        "type": "event",
    },
]

PATH_MAP = {0: 'PATH_SELF_SEED', 1: 'PATH_SOCIAL_NOMINEE', 2: 'PATH_TRUSTEE_OMBUDSMAN'}


class Command(BaseCommand):
    help = 'Watch WalletRecoveryEvents for WalletRecoveryRequested and RecoveryExecuted events.'

    def add_arguments(self, parser):
        parser.add_argument('--poll-seconds', type=float, default=10.0)
        parser.add_argument('--confirmations', type=int, default=2)
        parser.add_argument('--from-block', type=int, default=0)

    def handle(self, *args, **opts):
        rpc_url = settings.BLOCKCHAIN_CONFIG.get('RPC_URL')
        contract_addr = settings.CONTRACT_ADDRESSES.get('WalletRecoveryEvents', '')
        if not contract_addr:
            self.stderr.write('WalletRecoveryEvents contract address not set; exiting.')
            return

        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not w3.is_connected():
            self.stderr.write(f'Cannot connect to {rpc_url}')
            return

        contract = w3.eth.contract(address=Web3.to_checksum_address(contract_addr), abi=EVENT_ABI)
        ev_requested = contract.events.WalletRecoveryRequested
        ev_executed = contract.events.RecoveryExecuted

        confirmations = int(opts['confirmations'])
        poll = float(opts['poll_seconds'])

        forced_start = int(opts.get('from_block') or 0)
        if forced_start > 0:
            last_block = forced_start
        else:
            last_block = ChainWatcherCursor.resume_from(WATCHER_NAME, w3.eth.block_number)

        self.stdout.write(f'Watching WalletRecoveryRequested + RecoveryExecuted from block {last_block}')

        while True:
            try:
                head = w3.eth.block_number
                to_block = head - confirmations
                if to_block <= last_block:
                    time.sleep(poll)
                    continue

                from_b, to_b = last_block + 1, to_block

                for log in ev_requested.get_logs(fromBlock=from_b, toBlock=to_b):
                    self._handle_requested(log)

                for log in ev_executed.get_logs(fromBlock=from_b, toBlock=to_b):
                    self._handle_executed(log)

                last_block = to_block
                ChainWatcherCursor.advance(WATCHER_NAME, last_block)

            except KeyboardInterrupt:
                self.stdout.write('stopping')
                return
            except Exception as exc:  # noqa: BLE001
                logger.exception('chain_events watcher error: %s', exc)
                time.sleep(poll)

    # ── WalletRecoveryRequested ──────────────────────────────────────────────

    def _handle_requested(self, log):
        args = log['args']
        case_id_bytes = args['caseId']
        raw = bytes(case_id_bytes).rstrip(b'\x00')
        tx_hash = (log['transactionHash'].hex()
                   if hasattr(log['transactionHash'], 'hex')
                   else str(log['transactionHash']))
        try:
            case_id = int(raw.decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            logger.warning('WalletRecoveryRequested: cannot decode caseId %r', case_id_bytes)
            return

        updated = RecoveryCase.objects.filter(
            id=case_id,
            recovery_requested_tx_hash='',
        ).update(
            recovery_requested_tx_hash=tx_hash,
        )
        if updated:
            self.stdout.write(f'WalletRecoveryRequested confirmed for case {case_id} tx {tx_hash}')
        else:
            logger.debug('WalletRecoveryRequested: case %s already has tx hash or not found', case_id)

    # ── RecoveryExecuted ─────────────────────────────────────────────────────

    def _handle_executed(self, log):
        args = log['args']
        case_id_bytes = args['caseId']
        raw = bytes(case_id_bytes).rstrip(b'\x00')
        tx_hash = (log['transactionHash'].hex()
                   if hasattr(log['transactionHash'], 'hex')
                   else str(log['transactionHash']))
        try:
            case_id = int(raw.decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            logger.warning('RecoveryExecuted: cannot decode caseId %r', case_id_bytes)
            return

        case = RecoveryCase.objects.filter(id=case_id).first()
        if not case:
            logger.warning('RecoveryExecuted: no local case %s', case_id)
            return

        # Record the on-chain execution tx if we don't have one yet.
        if not case.execution_tx_hash:
            case.execution_tx_hash = tx_hash
            case.status = 'EXECUTED'
            now = timezone.now()
            from datetime import timedelta
            case.reversibility_ends_at = now + timedelta(days=90)
            case.save(update_fields=['execution_tx_hash', 'status',
                                     'reversibility_ends_at', 'updated_at'])
            self.stdout.write(f'RecoveryExecuted confirmed for case {case_id} tx {tx_hash}')

        # Mirror wallet state.
        old_wallet = args.get('oldWallet', '').lower()
        wa = WalletActivation.objects.filter(
            wallet_address__iexact=old_wallet,
        ).first()
        if wa and wa.state != 'RECOVERED':
            wa.state = 'RECOVERED'
            wa.save(update_fields=['state', 'last_state_change'])
