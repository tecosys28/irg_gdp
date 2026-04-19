// SPDX-License-Identifier: UNLICENSED
// IPR Owner: Rohit Tidke | (c) 2026 Intech Research Group
pragma solidity ^0.8.20;

/**
 * @title WalletRecoveryEvents
 * @notice On-chain handoff between the IRG wallet-access system and the
 *         existing IRG Ombudsman system. This contract is deliberately
 *         minimal — it holds no business logic, no Ombudsman-selection
 *         rules, no order validation beyond signature check. It exists
 *         solely as a pub/sub integration point:
 *
 *         - The Django/Node backend (wallet_access) emits
 *           WalletRecoveryRequested when a trustee-path recovery case
 *           is filed.
 *
 *         - The Ombudsman system (managed separately) emits
 *           OmbudsmanOrderIssued when an Order is rendered on that case.
 *
 *         - The Django/Node backend watches OmbudsmanOrderIssued, fetches
 *           the Order from IPFS by orderHash, and mechanically executes.
 *
 *         All Ombudsman appointment, eligibility, functioning, and
 *         oversight lives in the already-existing Ombudsman module. This
 *         contract intentionally does NOT encode any of that.
 */
contract WalletRecoveryEvents {
    // ─── Path taxonomy matches the RecoveryCase.path field on the backend ───
    enum RecoveryPath { SELF, SOCIAL, TRUSTEE }

    // ─── Order disposition — what the Ombudsman decided ───
    enum OrderDisposition {
        APPROVE,           // full approval as requested
        APPROVE_MODIFIED,  // approved with modifications (e.g. partial assets)
        REJECT,            // claim rejected
        REMAND,            // back to trustees for more investigation
        ESCALATE_COURT     // matter exceeds Ombudsman jurisdiction
    }

    // Caller authorised to file recovery requests — typically the
    // wallet_access submission middleware's system signer.
    mapping(address => bool) public recoveryFilers;

    // Caller authorised to issue Ombudsman Orders — the Ombudsman
    // office's signing key as managed in the existing system.
    mapping(address => bool) public ombudsmanSigners;

    address public admin;

    event RecoveryFilerSet(address indexed who, bool enabled);
    event OmbudsmanSignerSet(address indexed who, bool enabled);
    event AdminTransferred(address indexed from, address indexed to);

    // Fired by wallet_access when a TRUSTEE-path case is filed.
    event WalletRecoveryRequested(
        bytes32 indexed caseId,
        address indexed originalWallet,
        address indexed claimantWallet,
        RecoveryPath path,
        bytes32 evidenceBundleHash,
        uint256 filedAt
    );

    // Fired by wallet_access when a SOCIAL case is cancelled by the
    // original owner during cooling-off. Ombudsman does not consume this
    // directly but may choose to watch it for pattern analysis.
    event WalletRecoveryCancelled(
        bytes32 indexed caseId,
        address indexed originalWallet,
        string reason
    );

    // Fired by the Ombudsman system when an Order is issued.
    // orderHash references the IPFS-pinned Order document.
    event OmbudsmanOrderIssued(
        bytes32 indexed caseId,
        bytes32 indexed orderHash,
        OrderDisposition disposition,
        address indexed targetWallet,
        bytes32 actionPayload,
        uint256 issuedAt
    );

    // Fired by wallet_access once the Order has been mechanically executed.
    // Closes the loop for auditors.
    event RecoveryExecuted(
        bytes32 indexed caseId,
        bytes32 indexed orderHash,
        bytes32 executionTxContext,
        uint256 executedAt
    );

    modifier onlyAdmin() {
        require(msg.sender == admin, "not_admin");
        _;
    }

    constructor(address _admin) {
        require(_admin != address(0), "zero_admin");
        admin = _admin;
    }

    // ─────────────────────────────────────────────────────────────────────
    // ADMIN
    // ─────────────────────────────────────────────────────────────────────
    function transferAdmin(address next) external onlyAdmin {
        require(next != address(0), "zero_admin");
        emit AdminTransferred(admin, next);
        admin = next;
    }

    function setRecoveryFiler(address who, bool enabled) external onlyAdmin {
        recoveryFilers[who] = enabled;
        emit RecoveryFilerSet(who, enabled);
    }

    function setOmbudsmanSigner(address who, bool enabled) external onlyAdmin {
        ombudsmanSigners[who] = enabled;
        emit OmbudsmanSignerSet(who, enabled);
    }

    // ─────────────────────────────────────────────────────────────────────
    // WALLET_ACCESS -> OMBUDSMAN
    // ─────────────────────────────────────────────────────────────────────
    function fileRecoveryRequest(
        bytes32 caseId,
        address originalWallet,
        address claimantWallet,
        RecoveryPath path,
        bytes32 evidenceBundleHash
    ) external {
        require(recoveryFilers[msg.sender], "not_filer");
        require(originalWallet != address(0), "zero_original");
        require(path == RecoveryPath.TRUSTEE, "only_trustee_path_on_chain");

        emit WalletRecoveryRequested(
            caseId,
            originalWallet,
            claimantWallet,
            path,
            evidenceBundleHash,
            block.timestamp
        );
    }

    function cancelRecoveryRequest(
        bytes32 caseId,
        address originalWallet,
        string calldata reason
    ) external {
        require(recoveryFilers[msg.sender], "not_filer");
        emit WalletRecoveryCancelled(caseId, originalWallet, reason);
    }

    // ─────────────────────────────────────────────────────────────────────
    // OMBUDSMAN -> WALLET_ACCESS
    // ─────────────────────────────────────────────────────────────────────
    function issueOmbudsmanOrder(
        bytes32 caseId,
        bytes32 orderHash,
        OrderDisposition disposition,
        address targetWallet,
        bytes32 actionPayload
    ) external {
        require(ombudsmanSigners[msg.sender], "not_ombudsman");
        emit OmbudsmanOrderIssued(
            caseId,
            orderHash,
            disposition,
            targetWallet,
            actionPayload,
            block.timestamp
        );
    }

    // ─────────────────────────────────────────────────────────────────────
    // WALLET_ACCESS confirms execution (closes the loop)
    // ─────────────────────────────────────────────────────────────────────
    function confirmRecoveryExecuted(
        bytes32 caseId,
        bytes32 orderHash,
        bytes32 executionTxContext
    ) external {
        require(recoveryFilers[msg.sender], "not_filer");
        emit RecoveryExecuted(caseId, orderHash, executionTxContext, block.timestamp);
    }
}
