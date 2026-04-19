// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title CorpusFund - Corpus Fund Management
 * @notice IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
 */

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";

contract CorpusFund is AccessControl, ReentrancyGuard {
    
    bytes32 public constant TRUSTEE_ROLE = keccak256("TRUSTEE_ROLE");
    
    struct Fund {
        uint256 id;
        address jeweler;
        uint256 totalBalance;
        uint256 physicalGoldValue;
        uint256 otherInvestments;
        bool active;
    }
    
    struct Deposit {
        uint256 fundId;
        address depositor;
        uint256 amount;
        string depositType;
        uint256 timestamp;
    }
    
    struct Settlement {
        uint256 fundId;
        address beneficiary;
        uint256 amount;
        string settlementType;
        uint256 timestamp;
    }
    
    mapping(uint256 => Fund) public funds;
    mapping(uint256 => Deposit[]) public fundDeposits;
    mapping(uint256 => Settlement[]) public fundSettlements;
    
    uint256 public nextFundId;
    uint256 public physicalGoldPercent = 5;
    uint256 public otherInvestmentsPercent = 95;
    
    event FundCreated(uint256 indexed fundId, address indexed jeweler);
    event DepositMade(uint256 indexed fundId, address indexed depositor, uint256 amount, string depositType);
    event SettlementProcessed(uint256 indexed fundId, address indexed beneficiary, uint256 amount, string settlementType);
    event BonusDistributed(uint256 indexed fundId, address indexed beneficiary, uint256 amount);
    
    constructor() {
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(TRUSTEE_ROLE, msg.sender);
    }
    
    function createFund(address jeweler) external onlyRole(TRUSTEE_ROLE) returns (uint256) {
        uint256 fundId = nextFundId++;
        funds[fundId] = Fund({
            id: fundId,
            jeweler: jeweler,
            totalBalance: 0,
            physicalGoldValue: 0,
            otherInvestments: 0,
            active: true
        });
        emit FundCreated(fundId, jeweler);
        return fundId;
    }
    
    function deposit(
        uint256 fundId,
        uint256 amount,
        string calldata depositType
    ) external nonReentrant {
        Fund storage fund = funds[fundId];
        require(fund.active, "Fund not active");
        
        fund.totalBalance += amount;
        fund.physicalGoldValue += (amount * physicalGoldPercent) / 100;
        fund.otherInvestments += (amount * otherInvestmentsPercent) / 100;
        
        fundDeposits[fundId].push(Deposit({
            fundId: fundId,
            depositor: msg.sender,
            amount: amount,
            depositType: depositType,
            timestamp: block.timestamp
        }));
        
        emit DepositMade(fundId, msg.sender, amount, depositType);
    }
    
    function processSettlement(
        uint256 fundId,
        address beneficiary,
        uint256 amount,
        string calldata settlementType
    ) external onlyRole(TRUSTEE_ROLE) nonReentrant {
        Fund storage fund = funds[fundId];
        require(fund.active, "Fund not active");
        require(fund.totalBalance >= amount, "Insufficient balance");
        
        fund.totalBalance -= amount;
        
        fundSettlements[fundId].push(Settlement({
            fundId: fundId,
            beneficiary: beneficiary,
            amount: amount,
            settlementType: settlementType,
            timestamp: block.timestamp
        }));
        
        emit SettlementProcessed(fundId, beneficiary, amount, settlementType);
    }
    
    function distributeBonus(
        uint256 fundId,
        address[] calldata beneficiaries,
        uint256[] calldata amounts
    ) external onlyRole(TRUSTEE_ROLE) {
        require(beneficiaries.length == amounts.length, "Length mismatch");
        
        for (uint256 i = 0; i < beneficiaries.length; i++) {
            emit BonusDistributed(fundId, beneficiaries[i], amounts[i]);
        }
    }
    
    function getFund(uint256 fundId) external view returns (Fund memory) {
        return funds[fundId];
    }
}
