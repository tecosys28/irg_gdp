# IRG_GDP API Documentation

**Version:** 2.0  
**Base URL:** `https://api.irggdp.com/api/v1/`

---

## Authentication

All API requests require authentication via Token.

```bash
# Get token
POST /api/token/
Content-Type: application/json
{"username": "user@email.com", "password": "yourpassword"}

# Response
{"token": "abc123..."}

# Use in requests
Authorization: Token abc123...
```

---

## Core Module (`/auth/`)

### Register User
```
POST /auth/register/
{
  "email": "user@example.com",
  "mobile": "+919876543210",
  "first_name": "John",
  "last_name": "Doe",
  "password": "SecurePass123!",
  "confirm_password": "SecurePass123!",
  "city": "Mumbai",
  "roles": ["HOUSEHOLD", "INVESTOR"]
}
```

### Verify OTP
```
POST /auth/verify-otp/
{"email": "user@example.com", "otp": "123456"}
```

### Login
```
POST /auth/login/
{"email": "user@example.com", "password": "SecurePass123!"}
```

### Get Dashboard
```
GET /auth/users/dashboard/
Authorization: Token xxx
```

---

## IRG_GDP Module (`/gdp/`)

### List GDP Units
```
GET /gdp/units/
GET /gdp/units/portfolio/
```

### Minting (with 5-point checklist)
```
# Step 1: Create minting request
POST /gdp/minting/
{
  "gold_grams": "10.5",
  "purity": "22K",
  "invoice_hash": "0x..."
}

# Step 2: Verify checklist
POST /gdp/minting/{id}/verify_checklist/
{
  "invoice_verified": true,
  "jeweler_certified": true,
  "nw_certified": true,
  "within_cap": true,
  "undertaking_signed": true,
  "certifying_jeweler_id": "uuid"
}

# Step 3: Execute mint
POST /gdp/minting/{id}/execute_mint/
```

### Swap to FTR
```
POST /gdp/swap/initiate/
{
  "gdp_unit_ids": ["uuid1", "uuid2"],
  "ftr_category": "Healthcare"
}

POST /gdp/swap/{id}/confirm/
```

### Trading
```
GET /gdp/trade/orderbook/

POST /gdp/trade/place_order/
{
  "trade_type": "BUY",
  "units": 100,
  "price_per_unit": "650.00"
}
```

### Transfer/Gift
```
POST /gdp/transfer/initiate/
{
  "gdp_unit_id": "uuid",
  "to_email": "recipient@example.com",
  "transfer_type": "GIFT",
  "message": "Happy Birthday!"
}
```

### Earmarking
```
GET /gdp/earmarking/
POST /gdp/earmarking/{id}/release/
```

---

## irg_jr Module (`/jr/`)

### Issue JR (Jeweler only)
```
POST /jr/issuance/issue/
{
  "customer_email": "customer@example.com",
  "jewelry_type": "NEW",
  "description": "22K Gold Necklace",
  "gold_weight": "15.5",
  "purity": "22K",
  "making_charges": "5000.00",
  "stone_value": "0",
  "invoice_number": "INV-2026-001"
}
```

### Request Buyback
```
POST /jr/buyback/request_buyback/
{"jr_unit_id": "uuid"}
```

---

## irg_jdb Module (`/jdb/`)

### Browse Designs
```
GET /jdb/designs/browse/
GET /jdb/designs/browse/?category=NECKLACE
```

### Upload Design (Designer only)
```
POST /jdb/designs/
{
  "title": "Modern Kundan Set",
  "description": "Contemporary kundan bridal set",
  "category": "NECKLACE",
  "estimated_gold_weight": "25.0",
  "estimated_making_charges": "15000.00"
}
```

### Register Copyright
```
POST /jdb/designs/{id}/register_copyright/
```

### Place Design Order
```
POST /jdb/orders/place/
{
  "design_id": "uuid",
  "quantity": 1,
  "customization_notes": "Lighter weight version"
}
```

---

## Oracle Module (`/oracle/`)

### Get Latest Rates
```
GET /oracle/lbma/latest/
GET /oracle/lbma/gold/
GET /oracle/lbma/history/?metal=XAU&days=30
```

### Update Rate (Admin)
```
POST /oracle/lbma/update_rate/
{
  "metal": "XAU",
  "date": "2026-04-16",
  "am_fix_usd": "2350.00",
  "pm_fix_usd": "2355.00",
  "inr_per_gram": "6750.00"
}
```

### Get Benchmarks
```
GET /oracle/benchmark/by_category/
```

---

## Corpus Module (`/corpus/`)

### Get Fund Summary
```
GET /corpus/funds/{id}/summary/
```

### Confirm Deposit
```
POST /corpus/deposits/{id}/confirm/
```

### Process Settlement (Admin)
```
POST /corpus/settlements/process_settlement/
{
  "fund_id": "uuid",
  "beneficiary_id": "uuid",
  "amount": "50000.00",
  "settlement_type": "BUYBACK",
  "reference_id": "BUY-001"
}
```

---

## Governance Module (`/governance/`)

### Create Proposal
```
POST /governance/proposals/
{
  "title": "Increase Earmarking to 12%",
  "description": "Proposal to increase earmarking percentage",
  "category": "PARAMETER",
  "voting_starts": "2026-04-17T00:00:00Z",
  "voting_ends": "2026-04-24T00:00:00Z"
}
```

### Submit for Voting
```
POST /governance/proposals/{id}/submit/
```

### Cast Vote
```
POST /governance/votes/cast/
{
  "proposal_id": "uuid",
  "vote_for": true
}
```

### Get Active Proposals
```
GET /governance/proposals/active/
```

---

## Disputes Module (`/disputes/`)

### File Dispute
```
POST /disputes/cases/file/
{
  "against_email": "jeweler@example.com",
  "category": "BUYBACK",
  "subject": "Delayed buyback processing",
  "description": "Full description...",
  "amount_in_dispute": "100000.00"
}
```

### Start Review (Ombudsman)
```
POST /disputes/cases/{id}/start_review/
```

### Resolve Dispute (Ombudsman)
```
POST /disputes/cases/{id}/resolve/
{
  "outcome": "FAVOR_FILER",
  "ruling": "Full ruling text...",
  "compensation_amount": "50000.00"
}
```

---

## Recall Module (`/recall/`)

### Initiate Recall (Admin)
```
POST /recall/orders/initiate/
{
  "reason": "FRAUD",
  "description": "Suspected fraudulent minting",
  "target_unit_ids": ["uuid1", "uuid2"]
}
```

### Approve Recall
```
POST /recall/orders/{id}/approve/
```

### Execute Recall
```
POST /recall/orders/{id}/execute/
```

### Node Management
```
GET /recall/nodes/active/
POST /recall/nodes/{id}/heartbeat/
```

### DAC Voting
```
POST /recall/dac/{id}/vote/
{
  "approve": true,
  "comment": "Approved after review"
}
```

---

## Response Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 500 | Server Error |

---

## Rate Limits

- Standard: 100 requests/minute
- Minting: 10 requests/minute
- Trading: 50 requests/minute

---

© 2026 Intech Research Group. All Rights Reserved.
