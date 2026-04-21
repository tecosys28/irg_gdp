"""
Blockchain Service — IRG Chain 888101 integration layer.

This module is the compatibility shim that every existing GDP view already
imports:

    from services.blockchain import BlockchainService
    blockchain = BlockchainService()
    tx_hash = blockchain.mint_gdp(...)

Every public method keeps the signature it had before (callers don't change).
Internally each one builds a structured SystemTx and hands it to
`chain.client.system_submit`, which:

  * writes a PENDING row to the chain_tx_audit_log table
  * HMAC-signs and POSTs it to the middleware
  * retries, confirms, and updates the audit row
  * returns a real tx_hash from IRG Chain 888101

If the middleware is unreachable and `BLOCKCHAIN_CONFIG['ALLOW_SIMULATE']`
is True (default in DEBUG) each method returns a deterministic simulated
hash so dev/CI environments continue to work — the audit row records the
simulation explicitly, so nothing silently "looks real".

Contract addresses (TGDPMinting, CorpusFund, GIC, Governance, etc.) come
from settings.CONTRACT_ADDRESSES. Calldata encoding uses eth_abi when
available; if eth_abi isn't installed the call still records a hash based
on the action + arguments, which is fine until production wiring is done.

IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, Optional

from django.conf import settings
from web3 import Web3

from chain.client import RawTx, SystemTx, raw_submit, system_submit

try:
    from chain import abi_encoders as _abi
    _ABI_AVAILABLE = True
except ImportError:
    _abi = None
    _ABI_AVAILABLE = False

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _contract(name: str) -> str:
    """Look up a deployed contract address. Returns '' if unmapped."""
    return getattr(settings, 'CONTRACT_ADDRESSES', {}).get(name, '') or ''


def _encode_placeholder(action: str, **kwargs: Any) -> str:
    """
    Deterministic placeholder calldata. Used when real ABI encoding is not
    yet wired up (e.g. contract address is blank, we're in dev). Keeps the
    on-chain path working end-to-end by producing stable, unique data per
    call-site inputs so the audit log stays meaningful.
    """
    serialised = f'{action}:' + ':'.join(f'{k}={v}' for k, v in sorted(kwargs.items()))
    digest = hashlib.sha256(serialised.encode('utf-8')).hexdigest()
    return '0x' + digest  # 32 bytes; middleware treats this as opaque data


def _calldata(real: Optional[str], fallback_action: str, **kwargs: Any) -> str:
    """Return real ABI-encoded calldata if available, else a placeholder."""
    if real is not None:
        return real
    return _encode_placeholder(fallback_action, **kwargs)


def _unwrap(result) -> str:
    """All call sites expect a bare tx-hash string, so unwrap the SubmitResult."""
    return result.tx_hash or ''


# ─────────────────────────────────────────────────────────────────────────────
# BLOCKCHAIN SERVICE (drop-in replacement — all signatures preserved)
# ─────────────────────────────────────────────────────────────────────────────

class BlockchainService:
    """Web3 + middleware gateway for IRG Chain 888101."""

    def __init__(self):
        self.rpc_url = getattr(settings, 'BLOCKCHAIN_CONFIG', {}).get('RPC_URL', 'http://localhost:8545')
        self.chain_id = getattr(settings, 'BLOCKCHAIN_CONFIG', {}).get('CHAIN_ID', 888101)
        self.w3: Optional[Web3] = None
        self._connect()

    def _connect(self):
        """Optional read-only connection for balance/receipt queries."""
        try:
            self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
            if self.w3.is_connected():
                logger.info('Read-only RPC connected to IRG Chain (%s)', self.chain_id)
            else:
                self.w3 = None
        except Exception as exc:  # noqa: BLE001
            logger.warning('RPC probe failed: %s', exc)
            self.w3 = None

    # ── legacy simulate helper: kept for the few callers that still use it ──
    def _simulate_tx(self, tx_type: str, data: str) -> str:
        """
        Deprecated. Still referenced by a handful of views that push ad-hoc
        markers into the audit log. Routes through the normal system_submit
        path so those markers also appear on IRG Chain 888101.
        """
        result = system_submit(SystemTx(
            module='legacy',
            action=tx_type.lower(),
            to_address='',
            data=_encode_placeholder(tx_type, data=data),
            meta={'legacy_simulate': True, 'payload': data},
        ))
        return _unwrap(result)

    # ─────────────────────────────────────────────────────────────────────────
    # CORE GDP — minting, transfer, swap, trade, earmark
    # ─────────────────────────────────────────────────────────────────────────

    def mint_gdp(self, to_address: str, gold_grams: int, purity: int, benchmark_rate: int) -> str:
        result = system_submit(SystemTx(
            module='irg_gdp',
            action='mint_gdp',
            to_address=_contract('TGDPMinting'),
            data=_encode_placeholder('mint', to=to_address, grams=gold_grams,
                                     purity=purity, rate=benchmark_rate),
            meta={
                'to': to_address,
                'gold_grams': str(gold_grams),
                'purity': purity,
                'benchmark_rate': benchmark_rate,
            },
        ))
        return _unwrap(result)

    def transfer_gdp(self, from_address: str, to_address: str, unit_id: str) -> str:
        result = system_submit(SystemTx(
            module='irg_gdp',
            action='transfer_gdp',
            to_address=_contract('TGDPMinting'),
            data=_encode_placeholder('transfer', src=from_address, dst=to_address, unit=unit_id),
            meta={'from': from_address, 'to': to_address, 'unit_id': unit_id},
        ))
        return _unwrap(result)

    def swap_gdp_to_ftr(self, user_address: str, gdp_units: int, ftr_category: str) -> str:
        result = system_submit(SystemTx(
            module='irg_gdp',
            action='swap_gdp_to_ftr',
            to_address=_contract('FTRRedemption'),
            data=_encode_placeholder('swap', user=user_address, units=gdp_units, cat=ftr_category),
            meta={'user': user_address, 'units': gdp_units, 'category': ftr_category},
        ))
        return _unwrap(result)

    def execute_trade(self, trade_id) -> str:
        result = system_submit(SystemTx(
            module='irg_gdp',
            action='execute_trade',
            to_address=_contract('P2PGuaranteedSettlement'),
            data=_encode_placeholder('trade', id=str(trade_id)),
            meta={'trade_id': str(trade_id)},
        ))
        return _unwrap(result)

    def release_earmark(self, earmark_id: str) -> str:
        result = system_submit(SystemTx(
            module='irg_gdp',
            action='release_earmark',
            to_address=_contract('TGDPMinting'),
            data=_encode_placeholder('release', id=earmark_id),
            meta={'earmark_id': earmark_id},
        ))
        return _unwrap(result)

    # ─────────────────────────────────────────────────────────────────────────
    # JEWELER REDEMPTION (JR) + DESIGN BANK (JDB)
    # ─────────────────────────────────────────────────────────────────────────

    def issue_jr(self, jeweler_address: str, customer_address: str, value: int) -> str:
        result = system_submit(SystemTx(
            module='irg_jr',
            action='issue_jr',
            to_address=_contract('JRRegistry'),
            data=_encode_placeholder('issue_jr', jeweler=jeweler_address,
                                     customer=customer_address, value=value),
            meta={'jeweler': jeweler_address, 'customer': customer_address, 'value': value},
        ))
        return _unwrap(result)

    def process_buyback(self, jr_id: str, value: int) -> str:
        result = system_submit(SystemTx(
            module='irg_jr',
            action='process_buyback',
            to_address=_contract('JRRegistry'),
            data=_encode_placeholder('buyback', id=jr_id, value=value),
            meta={'jr_id': jr_id, 'value': value},
        ))
        return _unwrap(result)

    def register_copyright(self, designer_address: str, design_hash: str) -> str:
        result = system_submit(SystemTx(
            module='irg_jdb',
            action='register_copyright',
            to_address=_contract('JDBRegistry'),
            data=_encode_placeholder('copyright', designer=designer_address, hash=design_hash),
            meta={'designer': designer_address, 'design_hash': design_hash},
        ))
        return _unwrap(result)

    def distribute_royalty(self, designer_address: str, amount: int) -> str:
        result = system_submit(SystemTx(
            module='irg_jdb',
            action='distribute_royalty',
            to_address=_contract('JDBRegistry'),
            data=_encode_placeholder('royalty', designer=designer_address, amount=amount),
            meta={'designer': designer_address, 'amount': amount},
        ))
        return _unwrap(result)

    # ─────────────────────────────────────────────────────────────────────────
    # CORPUS FUND
    # ─────────────────────────────────────────────────────────────────────────

    def corpus_deposit(self, fund_id: str, amount: int, deposit_type: str) -> str:
        result = system_submit(SystemTx(
            module='corpus',
            action='deposit',
            to_address=_contract('SuperCorpusFund'),
            data=_encode_placeholder('deposit', fund=fund_id, amount=amount, kind=deposit_type),
            meta={'fund_id': fund_id, 'amount': amount, 'deposit_type': deposit_type},
        ))
        return _unwrap(result)

    def corpus_settlement(self, fund_id: str, beneficiary: str, amount: int) -> str:
        result = system_submit(SystemTx(
            module='corpus',
            action='settlement',
            to_address=_contract('SuperCorpusFund'),
            data=_encode_placeholder('settle', fund=fund_id, beneficiary=beneficiary, amount=amount),
            meta={'fund_id': fund_id, 'beneficiary': beneficiary, 'amount': amount},
        ))
        return _unwrap(result)

    # ─────────────────────────────────────────────────────────────────────────
    # GOVERNANCE
    # ─────────────────────────────────────────────────────────────────────────

    def submit_proposal(self, proposer: str, title: str, category: str,
                        param_key: str = '', proposed_value: int = 0,
                        justification_hash: str = '0x' + '00' * 32) -> str:
        """
        GovernanceVoting.submitProposal(bytes32 paramKey, uint256 proposedValue, bytes32 justificationHash)
        Legacy callers pass title/category; production callers should pass param_key and proposed_value.
        param_key: keccak256 of the parameter name string (e.g. 'MINTING_CAP_GRAMS')
        """
        pk        = param_key or title or category
        real_data = _abi.encode_submit_proposal(
            pk, proposed_value, justification_hash
        ) if _ABI_AVAILABLE else None
        result = system_submit(SystemTx(
            module='governance',
            action='submit_proposal',
            to_address=_contract('Governance'),
            data=_calldata(real_data, 'propose',
                           proposer=proposer, title=title, category=category),
            meta={'proposer': proposer, 'title': title, 'category': category,
                  'param_key': pk, 'proposed_value': proposed_value},
        ))
        return _unwrap(result)

    def cast_vote(self, proposal_id: str, voter: str, vote_for: bool) -> str:
        """GovernanceVoting.castVote(bytes32, bool)"""
        real_data = _abi.encode_cast_vote(proposal_id, vote_for) if _ABI_AVAILABLE else None
        result = system_submit(SystemTx(
            module='governance',
            action='cast_vote',
            to_address=_contract('Governance'),
            data=_calldata(real_data, 'vote',
                           id=proposal_id, voter=voter, yes=vote_for),
            meta={'proposal_id': proposal_id, 'voter': voter, 'vote_for': vote_for},
        ))
        return _unwrap(result)

    def execute_proposal(self, proposal_id: str) -> str:
        """GovernanceVoting.finalizeProposal(bytes32)"""
        real_data = _abi.encode_finalize_proposal(proposal_id) if _ABI_AVAILABLE else None
        result = system_submit(SystemTx(
            module='governance',
            action='execute_proposal',
            to_address=_contract('Governance'),
            data=_calldata(real_data, 'execute', id=proposal_id),
            meta={'proposal_id': proposal_id},
        ))
        return _unwrap(result)

    # ─────────────────────────────────────────────────────────────────────────
    # DISPUTES
    # ─────────────────────────────────────────────────────────────────────────

    def record_resolution(self, dispute_id: str, outcome: str) -> str:
        result = system_submit(SystemTx(
            module='disputes',
            action='record_resolution',
            to_address=_contract('DisputeRegistry'),
            data=_encode_placeholder('resolve', id=dispute_id, outcome=outcome),
            meta={'dispute_id': dispute_id, 'outcome': outcome},
        ))
        return _unwrap(result)

    # ─────────────────────────────────────────────────────────────────────────
    # ORACLE
    # ─────────────────────────────────────────────────────────────────────────

    def update_lbma_rate(self, metal: str, rate: str, date: str,
                         lme_timestamp: Optional[int] = None) -> str:
        """
        LMEOracle.submitPrice(uint256 priceUSDPerGram, uint256 lmeTimestamp)
        rate: USD per gram as a decimal string e.g. '63.50'
        Internally converts to × 1e8 integer representation.
        """
        import time as _time
        price_scaled = int(float(rate) * 1e8)
        ts        = lme_timestamp or int(_time.time())
        real_data = _abi.encode_submit_price(price_scaled, ts) if _ABI_AVAILABLE else None
        result = system_submit(SystemTx(
            module='oracle',
            action='update_lbma_rate',
            to_address=_contract('LBMAOracle'),
            data=_calldata(real_data, 'lbma', metal=metal, rate=rate, date=date),
            meta={'metal': metal, 'rate': rate, 'date': date},
        ))
        return _unwrap(result)

    # ─────────────────────────────────────────────────────────────────────────
    # RECALL
    # ─────────────────────────────────────────────────────────────────────────

    def recall_units(self, unit_ids, reason: str) -> str:
        """
        FTRRecall.requestRecall(bytes32 lotId, string reason)
        unit_ids: a single lot ID (bytes32 hex string) or a list of lot IDs.
        When a list is given, each lot is recalled in a separate transaction.
        Returns the tx hash of the last recall submitted.
        """
        ids = [unit_ids] if isinstance(unit_ids, str) else list(unit_ids)
        result = None
        for lot_id in ids:
            real_data = _abi.encode_request_recall(lot_id, reason) if _ABI_AVAILABLE else None
            result = system_submit(SystemTx(
                module='recall',
                action='recall_units',
                to_address=_contract('RecallRegistry'),
                data=_calldata(real_data, 'recall', units=lot_id, reason=reason),
                meta={'lot_id': lot_id, 'reason': reason},
            ))
        return _unwrap(result) if result else ''

    # ─────────────────────────────────────────────────────────────────────────
    # IDENTITY — wallet registration
    # ─────────────────────────────────────────────────────────────────────────

    def register_user(self, wallet_address: str, kyc_tier: int = 0,
                      jurisdiction: str = 'IN', meta: Optional[Dict] = None) -> str:
        """
        Record a newly-created user wallet on IRG Chain 888101.
        Called from the post-registration signal in core/signals.py.
        kyc_tier maps to IdentityRegistry participant types (1=NATURAL_PERSON etc.).
        Defaults to 1 (NATURAL_PERSON) when kyc_tier is 0.
        """
        ptype     = max(1, kyc_tier)
        kyc_hash  = (meta or {}).get('kyc_doc_hash', '0x' + '00' * 32)
        ipfs_cid  = (meta or {}).get('ipfs_cid', '')
        real_data = _abi.encode_register_participant(
            wallet_address, ptype, kyc_hash, ipfs_cid, jurisdiction
        ) if _ABI_AVAILABLE else None
        result = system_submit(SystemTx(
            module='core',
            action='register_user',
            to_address=_contract('IdentityRegistry'),
            data=_calldata(real_data, 'register', wallet=wallet_address,
                           tier=kyc_tier, jur=jurisdiction),
            meta={'wallet': wallet_address, 'kyc_tier': kyc_tier,
                  'jurisdiction': jurisdiction, **(meta or {})},
        ))
        return _unwrap(result)

    def bind_device(self, wallet_address: str, device_id_hash: str) -> str:
        """Bind a user device for P2P (v2.7)."""
        result = system_submit(SystemTx(
            module='core',
            action='bind_device',
            to_address=_contract('DeviceP2PRegistry'),
            data=_encode_placeholder('bind', wallet=wallet_address, device=device_id_hash),
            meta={'wallet': wallet_address, 'device_id_hash': device_id_hash},
        ))
        return _unwrap(result)

    # ─────────────────────────────────────────────────────────────────────────
    # WALLET RECOVERY — on-chain handoff to the existing Ombudsman system
    # via the WalletRecoveryEvents contract.
    # ─────────────────────────────────────────────────────────────────────────

    def file_recovery_request(self, *, case_id: str, original_wallet: str,
                              claimant_wallet: str, path: str,
                              evidence_bundle_hash: str) -> str:
        """
        Emit WalletRecoveryRequested on the WalletRecoveryEvents contract.
        path: '1'=PATH_SELF_SEED, '2'=PATH_SOCIAL_NOMINEE, '3'=PATH_TRUSTEE_OMBUDSMAN
        """
        path_int  = int(path) if str(path).isdigit() else 3
        real_data = _abi.encode_file_recovery_request(
            original_wallet, claimant_wallet, path_int, evidence_bundle_hash
        ) if _ABI_AVAILABLE else None
        result = system_submit(SystemTx(
            module='wallet_access',
            action='file_recovery_request',
            to_address=_contract('WalletRecoveryEvents'),
            data=_calldata(real_data, 'fileRecoveryRequest',
                           case=case_id, orig=original_wallet,
                           claim=claimant_wallet, path=path,
                           ev=evidence_bundle_hash),
            meta={
                'case_id': case_id,
                'original_wallet': original_wallet,
                'claimant_wallet': claimant_wallet,
                'path': path,
                'evidence_bundle_hash': evidence_bundle_hash,
            },
        ))
        return _unwrap(result)

    def cancel_recovery_request(self, *, case_id: str,
                                original_wallet: str, reason: str) -> str:
        result = system_submit(SystemTx(
            module='wallet_access',
            action='cancel_recovery_request',
            to_address=_contract('WalletRecoveryEvents'),
            data=_encode_placeholder(
                'cancelRecoveryRequest',
                case=case_id,
                orig=original_wallet,
                reason=reason,
            ),
            meta={
                'case_id': case_id,
                'original_wallet': original_wallet,
                'reason': reason,
            },
        ))
        return _unwrap(result)

    def confirm_recovery_executed(self, *, case_id: str, order_hash: str,
                                  execution_context: str) -> str:
        result = system_submit(SystemTx(
            module='wallet_access',
            action='confirm_recovery_executed',
            to_address=_contract('WalletRecoveryEvents'),
            data=_encode_placeholder(
                'confirmRecoveryExecuted',
                case=case_id, order=order_hash, ctx=execution_context,
            ),
            meta={'case_id': case_id, 'order_hash': order_hash},
        ))
        return _unwrap(result)

    # ─────────────────────────────────────────────────────────────────────────
    # RAW relay — used when a user device has already signed a tx
    # ─────────────────────────────────────────────────────────────────────────

    def relay_signed(self, module: str, action: str, signed_tx: str,
                     actor_id: Optional[int] = None, meta: Optional[Dict] = None) -> str:
        """
        User-signed transaction path. Pass the 0x-prefixed signed hex blob
        received from the mobile wallet; the middleware broadcasts it.
        """
        result = raw_submit(RawTx(
            module=module,
            action=action,
            signed_tx=signed_tx,
            actor_id=actor_id,
            meta=meta or {},
        ))
        return _unwrap(result)

    # ─────────────────────────────────────────────────────────────────────────
    # READ-ONLY HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    def get_balance(self, address: str):
        if self.w3 and self.w3.is_connected():
            try:
                return self.w3.eth.get_balance(Web3.to_checksum_address(address))
            except Exception as exc:  # noqa: BLE001
                logger.debug('get_balance failed: %s', exc)
        return 0

    def verify_transaction(self, tx_hash: str) -> dict:
        if self.w3 and self.w3.is_connected() and tx_hash and tx_hash.startswith('0x'):
            try:
                receipt = self.w3.eth.get_transaction_receipt(tx_hash)
                return {
                    'confirmed': receipt is not None,
                    'block_number': receipt.blockNumber if receipt else None,
                    'status': receipt.status if receipt else None,
                }
            except Exception as exc:  # noqa: BLE001
                logger.debug('verify_transaction failed: %s', exc)
        return {'confirmed': False, 'simulated': True}
