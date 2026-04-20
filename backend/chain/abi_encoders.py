"""
IRG Chain 888101 — ABI Encoders

Real calldata encoding for the irg_chain contracts that the BlockchainService
submits via the middleware. Uses web3.py's contract ABI encoding so the bytes
land in the correct Solidity function selectors.

The ABI JSON files live in irg_chain/abis/<ContractName>.json.  Point
IRG_CHAIN_ABI_DIR at that directory in your environment (or symlink/copy it).

If the ABI directory is missing or a contract ABI is not found, each encoder
falls back to a deterministic sha256 placeholder so dev/CI continues to work.
The ALLOW_SIMULATE path in chain.client never calls these encoders at all.

IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
"""
from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from web3 import Web3

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# ABI DIRECTORY
# ─────────────────────────────────────────────────────────────────────────────

_ABI_DIR: Path | None = None

def _resolve_abi_dir() -> Path | None:
    global _ABI_DIR
    if _ABI_DIR is not None:
        return _ABI_DIR
    # Django settings override (if running inside Django).
    try:
        from django.conf import settings as _s
        env = getattr(_s, 'IRG_CHAIN_ABI_DIR', '') or ''
    except Exception:  # noqa: BLE001
        env = ''
    # Env var override (takes precedence if set directly).
    env = os.environ.get('IRG_CHAIN_ABI_DIR', env)
    if env and Path(env).is_dir():
        _ABI_DIR = Path(env)
        return _ABI_DIR
    # Auto-discover: look for irg_chain/abis relative to this file.
    candidates = [
        Path(__file__).parent.parent.parent.parent / 'irg_chain' / 'abis',  # sibling repo
        Path('/opt/irg_chain/abis'),
        Path('/app/abis'),
    ]
    for c in candidates:
        if c.is_dir():
            _ABI_DIR = c
            return _ABI_DIR
    logger.warning(
        'IRG_CHAIN_ABI_DIR not set and irg_chain/abis not found — '
        'ABI encoding will fall back to placeholder. '
        'Set IRG_CHAIN_ABI_DIR=<path-to-irg_chain/abis>.'
    )
    return None


@lru_cache(maxsize=64)
def _load_abi(contract_name: str) -> list | None:
    d = _resolve_abi_dir()
    if d is None:
        return None
    p = d / f'{contract_name}.json'
    if not p.exists():
        logger.warning('ABI not found: %s', p)
        return None
    try:
        return json.loads(p.read_text())
    except Exception as exc:  # noqa: BLE001
        logger.warning('Failed to load ABI %s: %s', contract_name, exc)
        return None


def _encode(contract_name: str, fn_name: str, *args: Any) -> str | None:
    """
    Encode a function call. Returns '0x'-prefixed hex calldata, or None
    if the ABI is unavailable. Callers fall back to _encode_placeholder.
    """
    abi = _load_abi(contract_name)
    if abi is None:
        return None
    try:
        w3 = Web3()
        contract = w3.eth.contract(abi=abi)
        fn = getattr(contract.functions, fn_name)
        return fn(*args).build_transaction({'gas': 0})['data']
    except Exception as exc:  # noqa: BLE001
        logger.warning('ABI encode failed %s.%s: %s', contract_name, fn_name, exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# IDENTITY
# ─────────────────────────────────────────────────────────────────────────────

def encode_register_participant(
    wallet_address: str,
    participant_type: int,
    kyc_doc_hash: bytes | str,
    ipfs_cid: str,
    jurisdiction: str,
    additional_ref: bytes | str = b'\x00' * 32,
) -> str | None:
    """
    IdentityRegistry.registerParticipant(address, uint8, bytes32, string, string, bytes32)

    participant_type: 1=NATURAL_PERSON, 2=LEGAL_PERSON, 3=JEWELER, 4=CERTIFIER,
                      5=MINTER, 6=FEEDER, 7=LAW_FIRM, 8=CONSULTANT, 9=APPROVED_AGENCY
    kyc_doc_hash:    keccak256 of KYC bundle as 32-byte value or 0x-prefixed hex string
    """
    doc_hash  = _bytes32(kyc_doc_hash)
    extra_ref = _bytes32(additional_ref)
    return _encode(
        'IdentityRegistry', 'registerParticipant',
        Web3.to_checksum_address(wallet_address),
        participant_type,
        doc_hash,
        ipfs_cid,
        jurisdiction,
        extra_ref,
    )


def encode_verify_participant(wallet_address: str) -> str | None:
    """IdentityRegistry.verifyParticipant(address)"""
    return _encode(
        'IdentityRegistry', 'verifyParticipant',
        Web3.to_checksum_address(wallet_address),
    )


# ─────────────────────────────────────────────────────────────────────────────
# WALLET RECOVERY
# ─────────────────────────────────────────────────────────────────────────────

def encode_file_recovery_request(
    old_wallet: str,
    new_wallet: str,
    path: int,
    evidence_hash: bytes | str,
) -> str | None:
    """
    WalletRecoveryEvents.fileRecoveryRequest(address, address, uint8, bytes32)

    path: 1=PATH_SELF_SEED, 2=PATH_SOCIAL_NOMINEE, 3=PATH_TRUSTEE_OMBUDSMAN
    """
    return _encode(
        'WalletRecoveryEvents', 'fileRecoveryRequest',
        Web3.to_checksum_address(old_wallet),
        Web3.to_checksum_address(new_wallet),
        path,
        _bytes32(evidence_hash),
    )


def encode_execute_recovery(case_id: bytes | str) -> str | None:
    """WalletRecoveryEvents.executeRecovery(bytes32)"""
    return _encode('WalletRecoveryEvents', 'executeRecovery', _bytes32(case_id))


# ─────────────────────────────────────────────────────────────────────────────
# GOVERNANCE VOTING
# ─────────────────────────────────────────────────────────────────────────────

def encode_submit_proposal(
    param_key: bytes | str,
    proposed_value: int,
    justification_hash: bytes | str,
) -> str | None:
    """
    GovernanceVoting.submitProposal(bytes32, uint256, bytes32)

    param_key:           keccak256 of the parameter name, e.g.
                         Web3.keccak(text='MINTING_CAP_GRAMS')
    proposed_value:      new numeric value
    justification_hash:  keccak256 of justification document on IPFS
    """
    return _encode(
        'GovernanceVoting', 'submitProposal',
        _bytes32(param_key),
        proposed_value,
        _bytes32(justification_hash),
    )


def encode_cast_vote(proposal_id: bytes | str, approve: bool) -> str | None:
    """GovernanceVoting.castVote(bytes32, bool)"""
    return _encode(
        'GovernanceVoting', 'castVote',
        _bytes32(proposal_id),
        approve,
    )


def encode_finalize_proposal(proposal_id: bytes | str) -> str | None:
    """GovernanceVoting.finalizeProposal(bytes32)"""
    return _encode('GovernanceVoting', 'finalizeProposal', _bytes32(proposal_id))


# ─────────────────────────────────────────────────────────────────────────────
# LME ORACLE
# ─────────────────────────────────────────────────────────────────────────────

def encode_submit_price(price_usd_per_gram: int, lme_timestamp: int) -> str | None:
    """
    LMEOracle.submitPrice(uint256, uint256)

    price_usd_per_gram: USD per gram × 1e8 (e.g. 6350_00000000 = $63.50)
    lme_timestamp:      UNIX timestamp of the LME source quote
    """
    return _encode('LMEOracle', 'submitPrice', price_usd_per_gram, lme_timestamp)


# ─────────────────────────────────────────────────────────────────────────────
# FTR RECALL
# ─────────────────────────────────────────────────────────────────────────────

def encode_request_recall(lot_id: bytes | str, trigger_reason: str) -> str | None:
    """FTRRecall.requestRecall(bytes32, string)"""
    return _encode('FTRRecall', 'requestRecall', _bytes32(lot_id), trigger_reason)


# ─────────────────────────────────────────────────────────────────────────────
# TGDP MINTING — step-by-step encoders
# ─────────────────────────────────────────────────────────────────────────────

def encode_submit_gold_invoices(
    minter: str,
    invoice_hashes: list[bytes | str],
    ipfs_cid: str,
) -> str | None:
    """
    TGDPMinting.submitGoldInvoices(address, bytes32[], string)
    Step ①: minter submits tax-paid invoice hashes.
    """
    return _encode(
        'TGDPMinting', 'submitGoldInvoices',
        Web3.to_checksum_address(minter),
        [_bytes32(h) for h in invoice_hashes],
        ipfs_cid,
    )


def encode_initiate_minting(
    minter: str,
    jeweler: str,
    gold_grams: int,
) -> str | None:
    """
    TGDPMinting.initiateMinting(address, address, uint256)
    Step ③: platform (owner) initiates a minting request.
    """
    return _encode(
        'TGDPMinting', 'initiateMinting',
        Web3.to_checksum_address(minter),
        Web3.to_checksum_address(jeweler),
        gold_grams,
    )


def encode_sign_undertaking_and_mint(
    minting_id: bytes | str,
    undertaking_hash: bytes | str,
) -> str | None:
    """
    TGDPMinting.signUndertakingAndMint(bytes32, bytes32)
    Final step — minter signs undertaking; tokens are minted.
    """
    return _encode(
        'TGDPMinting', 'signUndertakingAndMint',
        _bytes32(minting_id),
        _bytes32(undertaking_hash),
    )


# ─────────────────────────────────────────────────────────────────────────────
# GIC LEDGER
# ─────────────────────────────────────────────────────────────────────────────

def encode_credit_gic(
    household: str,
    minting_id: bytes | str,
    amount: int,
    stream: int,
) -> str | None:
    """
    GICLedger.creditGIC(address, bytes32, uint256, uint8)
    stream: 0=ROYALTY, 1=BONUS, 2=TSF, 3=REFERRAL
    """
    return _encode(
        'GICLedger', 'creditGIC',
        Web3.to_checksum_address(household),
        _bytes32(minting_id),
        amount,
        stream,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CORPUS FUND
# ─────────────────────────────────────────────────────────────────────────────

def encode_corpus_deposit(
    corpus_fund_address: str,
    amount: int,
    minting_id: bytes | str,
    minter: str,
) -> str | None:
    """
    CorpusFund.deposit(uint256, bytes32, address)
    corpus_fund_address is the specific CorpusFund for this jeweler.
    """
    return _encode(
        'CorpusFund', 'deposit',
        amount,
        _bytes32(minting_id),
        Web3.to_checksum_address(minter),
    )


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PAUSE
# ─────────────────────────────────────────────────────────────────────────────

def encode_pause_scope(scope: int) -> str | None:
    """
    SystemPause.pause(uint8)
    scope: 0=GLOBAL, 1=TGDP, 2=FTR, 3=GIC, 4=TDIR, 5=GOVERNANCE
    """
    return _encode('SystemPause', 'pause', scope)


def encode_confirm_unpause(scope: int) -> str | None:
    """SystemPause.confirmUnpause(uint8)"""
    return _encode('SystemPause', 'confirmUnpause', scope)


# ─────────────────────────────────────────────────────────────────────────────
# IRG MULTISIG (governance operations)
# ─────────────────────────────────────────────────────────────────────────────

def encode_propose_operation(
    target: str,
    calldata: bytes | str,
    description: str,
) -> str | None:
    """IRGMultisig.propose(address, bytes, string)"""
    cd = bytes.fromhex(calldata.removeprefix('0x')) if isinstance(calldata, str) else calldata
    return _encode(
        'IRGMultisig', 'propose',
        Web3.to_checksum_address(target),
        cd,
        description,
    )


def encode_confirm_operation(op_id: bytes | str) -> str | None:
    """IRGMultisig.confirm(bytes32)"""
    return _encode('IRGMultisig', 'confirm', _bytes32(op_id))


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _bytes32(value: bytes | str) -> bytes:
    """Normalise a bytes32 value from hex string or raw bytes."""
    if isinstance(value, bytes):
        return value.ljust(32, b'\x00')[:32]
    if isinstance(value, str):
        hex_str = value.removeprefix('0x')
        if len(hex_str) == 64:
            return bytes.fromhex(hex_str)
        # Treat as UTF-8 text → keccak32 if it's not a hex string
        return Web3.keccak(text=value)
    raise TypeError(f'Expected bytes or str, got {type(value)}')
