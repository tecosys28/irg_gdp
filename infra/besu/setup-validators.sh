#!/usr/bin/env bash
# Generate IBFT2 validator keys and produce the genesis extraData for IRG Chain 888101.
#
# Requires: Hyperledger Besu on PATH (docker run hyperledger/besu works too),
#           jq, python3
#
# Usage:
#   chmod +x setup-validators.sh
#   ./setup-validators.sh 4      # generate keys for N validators (default 4)
#
# Output:
#   keys/validator{1..N}/key         — private key (KEEP SECRET, load via HSM in prod)
#   keys/validator{1..N}/key.pub     — public key
#   keys/validator{1..N}/address     — Ethereum address
#   genesis-extra-data.txt           — paste into genesis.json "extraData" field
#   validator-enodes.txt             — enode URLs for bootnode config

set -euo pipefail

N=${1:-4}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEYS_DIR="${SCRIPT_DIR}/keys"

echo "Generating keys for ${N} validators..."
mkdir -p "${KEYS_DIR}"

ADDRESSES=()

for i in $(seq 1 "$N"); do
  NODE_DIR="${KEYS_DIR}/validator${i}"
  mkdir -p "${NODE_DIR}"

  if command -v besu &>/dev/null; then
    besu --data-path="${NODE_DIR}" operator generate-blockchain-config \
      --config-file=/dev/null --to="${NODE_DIR}" --private-key-file-name=key 2>/dev/null || true
    # Besu writes to NODE_DIR/keys/<address>/key — flatten it.
    INNER=$(find "${NODE_DIR}/keys" -name "key" 2>/dev/null | head -1)
    if [[ -n "${INNER}" ]]; then
      cp "${INNER}" "${NODE_DIR}/key"
    fi
  else
    echo "  besu not found — generating key with Python (eth-keys)..."
    python3 - <<PYEOF
import secrets, hashlib
priv = secrets.token_bytes(32)
with open("${NODE_DIR}/key", "w") as f:
    f.write(priv.hex())
try:
    from eth_keys import keys as ethkeys
    pk = ethkeys.PrivateKey(priv)
    pub = pk.public_key.to_hex()[2:]  # strip 0x04
    addr = pk.public_key.to_checksum_address()
    with open("${NODE_DIR}/key.pub", "w") as f:
        f.write(pub)
    with open("${NODE_DIR}/address", "w") as f:
        f.write(addr)
    print(f"  validator${i}: {addr}")
except ImportError:
    print("  eth-keys not installed — install it: pip install eth-keys eth-account")
    print("  key written to ${NODE_DIR}/key (hex) — derive address manually.")
PYEOF
    continue
  fi

  # Read address from generated file.
  ADDR_FILE=$(find "${NODE_DIR}" -name "address" 2>/dev/null | head -1)
  if [[ -n "${ADDR_FILE}" ]]; then
    ADDR=$(cat "${ADDR_FILE}")
    ADDRESSES+=("${ADDR}")
    echo "  validator${i}: ${ADDR}"
  fi
done

echo ""

# Generate IBFT2 extraData.
# Format: RLP-encoded [ vanity(32 bytes), [validators...], 0, [], [] ]
# The easiest way is to use besu's ibft2 encoder or the Python rlp library.
echo "Generating IBFT2 extraData..."
python3 - "${ADDRESSES[@]}" <<'PYEOF'
import sys, rlp  # pip install rlp

def to_addr_bytes(addr):
    return bytes.fromhex(addr.replace("0x","").lower())

validators = [to_addr_bytes(a) for a in sys.argv[1:]]
vanity = b'\x00' * 32

# IBFT2 extra data: vanity || RLP([validators, vote, round, seals])
extra_rlp = rlp.encode([validators, b'', b'\x00', []])
extra_data = "0x" + vanity.hex() + extra_rlp.hex()

with open("genesis-extra-data.txt", "w") as f:
    f.write(extra_data + "\n")

print(f"extraData written to genesis-extra-data.txt")
print(f"Paste into genesis.json \"extraData\" field:")
print(f"  {extra_data[:80]}...")
PYEOF

echo ""
echo "Next steps:"
echo "  1. Replace 'REPLACE_WITH_IBFT2_EXTRA_DATA' in genesis.json with content of genesis-extra-data.txt"
echo "  2. Replace 'REPLACE_WITH_DEPLOYER_ADDRESS' in genesis.json with your deployer's Ethereum address"
echo "  3. Replace validator address placeholders in genesis.json alloc section"
echo "  4. Set VALIDATOR{1..N}_PUBKEY env vars from keys/validator{N}/key.pub for docker-compose.besu.yml"
echo "  5. Run: docker compose -f docker-compose.besu.yml up -d"
echo "  6. Verify: curl -s http://localhost:8545 -X POST -H 'Content-Type: application/json'"
echo "            --data '{\"jsonrpc\":\"2.0\",\"method\":\"eth_blockNumber\",\"params\":[],\"id\":1}'"
