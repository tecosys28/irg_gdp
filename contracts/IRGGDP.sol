// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title IRGGDP - Main GDP Contract
 * @dev Blockchain-registered rights with full transaction support
 * @notice IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
 */

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/security/Pausable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";

contract IRGGDP is AccessControl, Pausable, ReentrancyGuard {
    
    bytes32 public constant MINTER_ROLE = keccak256("MINTER_ROLE");
    bytes32 public constant ORACLE_ROLE = keccak256("ORACLE_ROLE");
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");
    bytes32 public constant RECALL_ROLE = keccak256("RECALL_ROLE");
    
    // Structs
    struct GDPUnit {
        uint256 id;
        address owner;
        uint256 pureGoldGrams;
        uint256 benchmarkAtMint;
        uint256 saleableUnits;
        uint256 reserveUnits;
        uint256 mintedAt;
        Status status;
    }
    
    enum Status { Active, Earmarked, Swapped, Transferred, Redeemed, Burned, Recalled }
    
    struct MintingRequest {
        address requester;
        uint256 goldGrams;
        uint8 purity;
        bytes32 invoiceHash;
        bool[5] checklist; // invoice, jeweler, nw, cap, undertaking
        RequestStatus status;
    }
    
    enum RequestStatus { Pending, Approved, Rejected, Minted }
    
    struct EarmarkRecord {
        uint256 unitId;
        uint256 amount;
        uint256 releaseDate;
        bool released;
    }
    
    // State
    mapping(uint256 => GDPUnit) public gdpUnits;
    mapping(address => uint256[]) public userUnits;
    mapping(uint256 => MintingRequest) public mintingRequests;
    mapping(uint256 => EarmarkRecord) public earmarks;
    
    uint256 public totalSupply;
    uint256 public nextUnitId;
    uint256 public nextRequestId;
    uint256 public nextEarmarkId;
    
    // Config (can be updated via governance)
    uint256 public saleablePerGram = 9;
    uint256 public reservePerGram = 1;
    uint256 public maxMintingCap = 500 * 1e18;
    uint256 public earmarkingPercent = 11;
    uint256 public corpusContributionPercent = 20;
    
    // Events
    event UnitMinted(uint256 indexed unitId, address indexed owner, uint256 goldGrams, uint256 timestamp);
    event UnitTransferred(uint256 indexed unitId, address indexed from, address indexed to, string transferType);
    event UnitSwapped(uint256 indexed unitId, address indexed owner, string ftrCategory, uint256 ftrUnits);
    event UnitEarmarked(uint256 indexed unitId, uint256 indexed earmarkId, uint256 amount, uint256 releaseDate);
    event EarmarkReleased(uint256 indexed earmarkId, address indexed beneficiary, uint256 amount);
    event UnitRecalled(uint256 indexed unitId, address indexed previousOwner, string reason);
    event BenchmarkUpdated(uint256 newBenchmark, uint256 timestamp);
    event MintingRequested(uint256 indexed requestId, address indexed requester, uint256 goldGrams);
    event ChecklistVerified(uint256 indexed requestId, uint8 checkpointIndex, bool passed);
    
    constructor() {
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(ADMIN_ROLE, msg.sender);
        _grantRole(MINTER_ROLE, msg.sender);
        _grantRole(RECALL_ROLE, msg.sender);
    }
    
    // ═══════════════════════════════════════════════════════════════════
    // MINTING WITH 5-POINT CHECKLIST
    // ═══════════════════════════════════════════════════════════════════
    
    function requestMinting(
        uint256 goldGrams,
        uint8 purity,
        bytes32 invoiceHash
    ) external whenNotPaused returns (uint256) {
        require(goldGrams > 0 && goldGrams <= maxMintingCap, "Invalid gold amount");
        require(purity == 24 || purity == 22 || purity == 18 || purity == 14, "Invalid purity");
        
        uint256 requestId = nextRequestId++;
        mintingRequests[requestId] = MintingRequest({
            requester: msg.sender,
            goldGrams: goldGrams,
            purity: purity,
            invoiceHash: invoiceHash,
            checklist: [false, false, false, false, false],
            status: RequestStatus.Pending
        });
        
        emit MintingRequested(requestId, msg.sender, goldGrams);
        return requestId;
    }
    
    function verifyCheckpoint(
        uint256 requestId,
        uint8 checkpoint
    ) external onlyRole(MINTER_ROLE) {
        require(checkpoint < 5, "Invalid checkpoint");
        MintingRequest storage req = mintingRequests[requestId];
        require(req.status == RequestStatus.Pending, "Not pending");
        
        req.checklist[checkpoint] = true;
        emit ChecklistVerified(requestId, checkpoint, true);
        
        // Check if all verified
        if (req.checklist[0] && req.checklist[1] && req.checklist[2] && 
            req.checklist[3] && req.checklist[4]) {
            req.status = RequestStatus.Approved;
        }
    }
    
    function executeMint(
        uint256 requestId,
        uint256 benchmarkRate
    ) external onlyRole(MINTER_ROLE) whenNotPaused nonReentrant returns (uint256) {
        MintingRequest storage req = mintingRequests[requestId];
        require(req.status == RequestStatus.Approved, "Not approved");
        
        uint256 purityFactor = getPurityFactor(req.purity);
        uint256 pureGold = (req.goldGrams * purityFactor) / 10000;
        
        uint256 saleableUnits = (pureGold * saleablePerGram) / 1e18;
        uint256 reserveUnits = (pureGold * reservePerGram) / 1e18;
        
        uint256 unitId = nextUnitId++;
        
        gdpUnits[unitId] = GDPUnit({
            id: unitId,
            owner: req.requester,
            pureGoldGrams: pureGold,
            benchmarkAtMint: benchmarkRate,
            saleableUnits: saleableUnits,
            reserveUnits: reserveUnits,
            mintedAt: block.timestamp,
            status: Status.Active
        });
        
        userUnits[req.requester].push(unitId);
        totalSupply += saleableUnits + reserveUnits;
        req.status = RequestStatus.Minted;
        
        emit UnitMinted(unitId, req.requester, req.goldGrams, block.timestamp);
        return unitId;
    }
    
    // ═══════════════════════════════════════════════════════════════════
    // TRANSFERS (GIFT/SPONSOR/INHERITANCE)
    // ═══════════════════════════════════════════════════════════════════
    
    function transfer(
        uint256 unitId,
        address to,
        string calldata transferType
    ) external whenNotPaused nonReentrant {
        GDPUnit storage unit = gdpUnits[unitId];
        require(unit.owner == msg.sender, "Not owner");
        require(unit.status == Status.Active, "Unit not active");
        require(to != address(0), "Invalid recipient");
        
        unit.owner = to;
        userUnits[to].push(unitId);
        
        emit UnitTransferred(unitId, msg.sender, to, transferType);
    }
    
    // ═══════════════════════════════════════════════════════════════════
    // SWAP TO FTR
    // ═══════════════════════════════════════════════════════════════════
    
    function swap(
        uint256 unitId,
        string calldata ftrCategory,
        uint256 ftrUnits
    ) external whenNotPaused nonReentrant {
        GDPUnit storage unit = gdpUnits[unitId];
        require(unit.owner == msg.sender, "Not owner");
        require(unit.status == Status.Active, "Unit not active");
        
        unit.status = Status.Swapped;
        
        emit UnitSwapped(unitId, msg.sender, ftrCategory, ftrUnits);
    }
    
    // ═══════════════════════════════════════════════════════════════════
    // EARMARKING
    // ═══════════════════════════════════════════════════════════════════
    
    function earmark(
        uint256 unitId,
        uint256 amount,
        uint256 releaseDate
    ) external whenNotPaused nonReentrant returns (uint256) {
        GDPUnit storage unit = gdpUnits[unitId];
        require(unit.owner == msg.sender, "Not owner");
        require(unit.status == Status.Active, "Unit not active");
        require(releaseDate > block.timestamp, "Invalid release date");
        
        uint256 earmarkId = nextEarmarkId++;
        earmarks[earmarkId] = EarmarkRecord({
            unitId: unitId,
            amount: amount,
            releaseDate: releaseDate,
            released: false
        });
        
        unit.status = Status.Earmarked;
        
        emit UnitEarmarked(unitId, earmarkId, amount, releaseDate);
        return earmarkId;
    }
    
    function releaseEarmark(uint256 earmarkId) external nonReentrant {
        EarmarkRecord storage record = earmarks[earmarkId];
        require(!record.released, "Already released");
        require(block.timestamp >= record.releaseDate, "Not yet releasable");
        
        GDPUnit storage unit = gdpUnits[record.unitId];
        require(unit.owner == msg.sender, "Not owner");
        
        record.released = true;
        unit.status = Status.Active;
        
        emit EarmarkReleased(earmarkId, msg.sender, record.amount);
    }
    
    // ═══════════════════════════════════════════════════════════════════
    // RECALL (EMERGENCY)
    // ═══════════════════════════════════════════════════════════════════
    
    function recall(
        uint256[] calldata unitIds,
        string calldata reason
    ) external onlyRole(RECALL_ROLE) {
        for (uint256 i = 0; i < unitIds.length; i++) {
            GDPUnit storage unit = gdpUnits[unitIds[i]];
            if (unit.status != Status.Recalled && unit.status != Status.Burned) {
                address previousOwner = unit.owner;
                unit.status = Status.Recalled;
                unit.owner = address(0);
                totalSupply -= (unit.saleableUnits + unit.reserveUnits);
                
                emit UnitRecalled(unitIds[i], previousOwner, reason);
            }
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════
    // HELPERS
    // ═══════════════════════════════════════════════════════════════════
    
    function getPurityFactor(uint8 purity) public pure returns (uint256) {
        if (purity == 24) return 10000;
        if (purity == 22) return 9167;
        if (purity == 18) return 7500;
        if (purity == 14) return 5833;
        revert("Invalid purity");
    }
    
    function getUserUnits(address user) external view returns (uint256[] memory) {
        return userUnits[user];
    }
    
    function getUnit(uint256 unitId) external view returns (GDPUnit memory) {
        return gdpUnits[unitId];
    }
    
    // ═══════════════════════════════════════════════════════════════════
    // GOVERNANCE PARAMETER UPDATES
    // ═══════════════════════════════════════════════════════════════════
    
    function updateParameters(
        uint256 _saleablePerGram,
        uint256 _reservePerGram,
        uint256 _maxMintingCap,
        uint256 _earmarkingPercent,
        uint256 _corpusContributionPercent
    ) external onlyRole(ADMIN_ROLE) {
        saleablePerGram = _saleablePerGram;
        reservePerGram = _reservePerGram;
        maxMintingCap = _maxMintingCap;
        earmarkingPercent = _earmarkingPercent;
        corpusContributionPercent = _corpusContributionPercent;
    }
    
    function pause() external onlyRole(ADMIN_ROLE) {
        _pause();
    }
    
    function unpause() external onlyRole(ADMIN_ROLE) {
        _unpause();
    }
}
