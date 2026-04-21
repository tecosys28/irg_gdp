"""
Listen for OmbudsmanOrderIssued events on the WalletRecoveryEvents contract
and mechanically execute them via wallet_access.services.execute_ombudsman_order.

Usage:
    python manage.py watch_ombudsman_orders

Intended to run as a long-lived sidecar process (systemd / Kubernetes
Deployment). Safe to restart — it resumes from the last block it saw,
persisted in the ChainWatcherCursor singleton row (watcher name:
"ombudsman_orders").

IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
import logging
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from web3 import Web3

from chain.models import ChainWatcherCursor
from wallet_access import services as wallet_services

logger = logging.getLogger(__name__)

WATCHER_NAME = 'ombudsman_orders'

# ABI matches WalletRecoveryEvents.sol exactly.
# OmbudsmanOrderIssued(bytes32 indexed caseId, bytes32 indexed orderHash,
#                      uint8 orderType, uint8 action, uint256 timestamp)
EVENT_ABI = [{
    "anonymous": False,
    "inputs": [
        {"indexed": True,  "name": "caseId",    "type": "bytes32"},
        {"indexed": True,  "name": "orderHash", "type": "bytes32"},
        {"indexed": False, "name": "orderType", "type": "uint8"},
        {"indexed": False, "name": "action",    "type": "uint8"},
        {"indexed": False, "name": "timestamp", "type": "uint256"},
    ],
    "name": "OmbudsmanOrderIssued",
    "type": "event",
}]

# orderType uint8 mapping (must match OmbudsmanRegistry.sol enum OrderType).
ORDER_TYPE_MAP = {
    0: 'APPROVE',
    1: 'APPROVE_MODIFIED',
    2: 'REJECT',
    3: 'REMAND',
    4: 'ESCALATE_COURT',
}


class Command(BaseCommand):
    help = 'Watch WalletRecoveryEvents for OmbudsmanOrderIssued events and execute them.'

    def add_arguments(self, parser):
        parser.add_argument('--poll-seconds', type=float, default=10.0)
        parser.add_argument('--confirmations', type=int, default=2)
        parser.add_argument('--from-block', type=int, default=0,
                            help='Override stored cursor and start from this block (0 = use stored).')

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
        event = contract.events.OmbudsmanOrderIssued

        confirmations = int(opts['confirmations'])
        poll = float(opts['poll_seconds'])

        # Resume from stored cursor, or from explicit --from-block, or from chain head.
        forced_start = int(opts.get('from_block') or 0)
        if forced_start > 0:
            last_block = forced_start
        else:
            last_block = ChainWatcherCursor.resume_from(WATCHER_NAME, w3.eth.block_number)

        self.stdout.write(f'Watching OmbudsmanOrderIssued from block {last_block}')

        while True:
            try:
                head = w3.eth.block_number
                to_block = head - confirmations
                if to_block <= last_block:
                    time.sleep(poll)
                    continue

                logs = event.get_logs(fromBlock=last_block + 1, toBlock=to_block)
                for log in logs:
                    self._process(log)

                last_block = to_block
                ChainWatcherCursor.advance(WATCHER_NAME, last_block)
            except KeyboardInterrupt:
                self.stdout.write('stopping')
                return
            except Exception as exc:  # noqa: BLE001
                logger.exception('Ombudsman watcher error: %s', exc)
                time.sleep(poll)

    def _process(self, log):
        args = log['args']
        try:
            case_id_bytes = args['caseId']
            order_hash_bytes = args['orderHash']
            order_type_int = int(args['orderType'])
            disposition = ORDER_TYPE_MAP.get(order_type_int, str(order_type_int))

            # caseId is a bytes32 left-padded encoding of the Django RecoveryCase.id (int).
            # Strip trailing zero bytes and decode as UTF-8 integer string.
            raw = bytes(case_id_bytes).rstrip(b'\x00')
            try:
                case_id = int(raw.decode('utf-8'))
            except (UnicodeDecodeError, ValueError):
                logger.warning('Unable to decode caseId from on-chain bytes: %r', case_id_bytes)
                return

            order_hash_hex = '0x' + bytes(order_hash_bytes).hex()
            tx_hash_hex = (log['transactionHash'].hex()
                           if hasattr(log['transactionHash'], 'hex')
                           else str(log['transactionHash']))

            case = wallet_services.execute_ombudsman_order(
                case_id=case_id,
                order_hash=order_hash_hex,
                order_tx_hash=tx_hash_hex,
                disposition=disposition,
                target_wallet='',  # resolved from the DB case; not emitted in this event
            )
            self.stdout.write(f'Processed Ombudsman Order for case {case_id}: {case.status}')
        except Exception as exc:  # noqa: BLE001
            logger.exception('Failed to process Ombudsman event: %s', exc)
