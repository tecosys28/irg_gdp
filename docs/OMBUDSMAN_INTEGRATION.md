# Ombudsman integration guide

This document describes the contract between the **Ombudsman office's
existing case-management system** and the two IRG platforms (IRG_GDP
and IRG_FTR). The IRG team built the wallet-access machinery; you
already operate the Ombudsman process. This document is how they
connect.

## What IRG does

IRG files cases. Specifically:

1. A user fires a **trustee-path recovery** (death, incapacity,
   contested case) or a **legal-person ownership transfer** (corporate
   acquisition, partnership change, trustee succession) through their
   own IRG wallet UI.
2. IRG's backend persists the case locally, pauses transactions on
   the affected wallet, and emits a `WalletRecoveryRequested` event
   on IRG Chain 888101.
3. IRG waits.

## What the Ombudsman office does

Whatever you already do. Investigate, hold hearings, call for
documents, issue written orders. IRG has no opinion about your
internal process.

When you have a decision, you emit an `OmbudsmanOrderIssued` event
on-chain with a disposition code. IRG listens for that event and
mechanically applies it to the corresponding wallet — moving the
wallet into `RECOVERED` state, updating the case row, rotating the
seed phrase on the new operator's activation, notifying affected
users.

## The contract at a glance

Everything runs through a single solidity contract:
`contracts/WalletRecoveryEvents.sol`. It is deployed once on
IRG Chain 888101 and its address is recorded in the
`CONTRACT_ADDRESSES.WalletRecoveryEvents` config of both backends.

The contract does **no substantive logic** — it is a pub/sub board.
IRG writes events to announce case filings; the Ombudsman office
writes events to announce decisions. All the actual work happens
off-chain.

## Events IRG emits (Ombudsman listens)

### `WalletRecoveryRequested`

Emitted when a user files a trustee-path recovery case OR a
legal-person ownership transfer.

```solidity
event WalletRecoveryRequested(
    bytes32 indexed caseId,
    address indexed originalWallet,
    address indexed claimantWallet,
    uint8 path,              // 0=SELF, 1=SOCIAL, 2=TRUSTEE
    bytes32 evidenceBundleHash,
    uint256 filedAt
);
```

**Decoding `caseId`:** it is a `bytes32` encoding of the Django/Prisma
primary key of the case row, right-padded with zero bytes. For an
ownership transfer, the decoded UTF-8 string is prefixed with
`ownership:` (e.g. `ownership:clxyz123abc...`). For a recovery, no
prefix.

**`evidenceBundleHash`:** IPFS CID of the document bundle (death
certificate, board resolution, etc.) the user uploaded. The Ombudsman
office fetches this bundle off-chain to review the case.

### `WalletRecoveryCancelled`

Emitted when the original wallet holder cancels a recovery during the
cooling-off / notice period. If the Ombudsman has not yet issued an
order, the case is closed; if they have, the cancellation is ignored
(an issued order is final unless reversed within the 90-day
reversibility window).

```solidity
event WalletRecoveryCancelled(
    bytes32 indexed caseId,
    address indexed originalWallet,
    string reason
);
```

### `RecoveryExecuted`

IRG emits this *after* mechanically executing an `OmbudsmanOrderIssued`
with an APPROVE disposition. It is a confirmation for the Ombudsman's
audit trail that the order has been carried out.

```solidity
event RecoveryExecuted(
    bytes32 indexed caseId,
    bytes32 indexed orderHash,
    string executionContext
);
```

## Events the Ombudsman emits (IRG listens)

### `OmbudsmanOrderIssued`

**This is the only event the Ombudsman has to emit.** IRG's event
listener (`wallet_access/management/commands/watch_ombudsman_orders.py`
on the Django side, `backend/src/scripts/watch-ombudsman.ts` on the FTR
side) watches for it and applies it to the case.

```solidity
event OmbudsmanOrderIssued(
    bytes32 indexed caseId,        // must match the caseId IRG filed
    bytes32 indexed orderHash,     // hash of the written order document
    uint8 disposition,             // see table below
    address indexed targetWallet,  // new owner wallet (or 0x0 for reject)
    bytes32 actionPayload,         // reserved, use 0x0 for now
    uint256 issuedAt
);
```

**Disposition codes:**

| Code | Meaning | Effect on IRG case |
|------|---------|---------------------|
| 0 | `APPROVE` | Case → EXECUTED; wallet → RECOVERED; new operator activation invited |
| 1 | `APPROVE_MODIFIED` | Same as APPROVE; IRG records the modified terms from the order hash for audit |
| 2 | `REJECT` | Case → REJECTED; wallet returns to ACTIVATED (or CREATED if it had never been activated) |
| 3 | `REMAND` | Case stays in AWAITING_OMBUDSMAN; the order is recorded for audit (e.g. remand for more evidence) |
| 4 | `ESCALATE_COURT` | Same as REMAND; signals that the Ombudsman has referred the matter to a civil court |

**Emitter authorisation.** Only addresses on the
`ombudsmanSigners` list of `WalletRecoveryEvents.sol` can emit this
event. The list is managed by the contract admin
(`setOmbudsmanSigner(address, bool)`). On pilot launch this admin is
held by an IRG governance multisig; it is expected to be handed over
to an Ombudsman-office-controlled multisig once the office is
established. The handover is on-chain via `transferAdmin`.

### `WalletOwnershipTransferRequested` (upcoming)

For now, legal-person ownership transfers reuse `WalletRecoveryRequested`
with the `ownership:` caseId prefix. A dedicated event may be
introduced in a later release if the Ombudsman office prefers to treat
the two case types as first-class separate streams. If that happens,
this guide will be updated before any change to the contract.

## Gas, cost, and latency

- `OmbudsmanOrderIssued` costs ~50–70k gas on a QBFT Besu chain with
  3s block time. At current pricing this is negligible.
- Confirmation latency (from event emission to IRG acting on it) is
  configured to 2 blocks (6 seconds) on both GDP and FTR listeners.
- In practice the end-to-end latency from "Ombudsman clicks approve"
  to "IRG sends notification to family" is well under one minute.

## Case IDs — bytes32 encoding rules

Because Ethereum events use `bytes32` for string-like indexed
arguments, IRG encodes its database case IDs as follows:

1. Take the case ID as a UTF-8 string:
   - Django: stringified integer (e.g. `"1428"`)
   - Prisma: CUID (e.g. `"clxyz123abc0000"`)
2. For ownership transfers only, prefix with `ownership:` (so the
   UTF-8 string becomes e.g. `"ownership:clxyz123abc0000"`).
3. Pad on the right with zero bytes to 32 bytes.
4. Emit as `bytes32`.

The Ombudsman system must emit `OmbudsmanOrderIssued` with the **exact
same bytes32** value it received in `WalletRecoveryRequested`. Do not
reinterpret, trim, or rehash.

## Operational expectations

1. **Idempotency.** IRG's listener deduplicates by `orderHash`. If you
   accidentally emit the same order twice it will be processed once.
2. **Ordering.** IRG processes orders in block order. If you issue two
   orders for the same `caseId`, the later one wins.
3. **No mid-case state changes.** The Ombudsman does not need to emit
   intermediate "still reviewing" events. IRG's case row stays in
   `AWAITING_OMBUDSMAN` until a final disposition arrives, however
   long that takes. If you want to extend the 30-day public notice
   period, simply do not issue an order; IRG will not timeout the case
   unilaterally.
4. **Reversibility.** IRG enforces a 90-day reversibility window after
   an APPROVE disposition during which a subsequent REJECT with the
   same `caseId` will unwind the recovery. After 90 days, approvals
   are final.

## Test vectors

A recovery case with the Django primary key `42`:

- `caseId` bytes32:
  `0x3432000000000000000000000000000000000000000000000000000000000000`
  (UTF-8 of `"42"` padded right)
- After an APPROVE order, the corresponding `RecoveryExecuted` event
  from IRG will carry the same `caseId`.

A Prisma ownership-transfer case with CUID `clxyz123abc0000`:

- `caseId` bytes32: UTF-8 of `"ownership:clxyz123abc0000"` padded right.

## Questions, integration support

Contact the IRG chain-ops team. The listener scripts on both backends
log every event they see (with block number and transaction hash) — if
you want to confirm an event arrived, check those logs first.
