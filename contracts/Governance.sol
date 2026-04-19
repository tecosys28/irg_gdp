// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title Governance - DAO Governance
 * @notice IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
 */

import "@openzeppelin/contracts/access/AccessControl.sol";

contract Governance is AccessControl {
    
    struct Proposal {
        uint256 id;
        address proposer;
        string title;
        string category;
        uint256 votesFor;
        uint256 votesAgainst;
        uint256 votingEnds;
        ProposalStatus status;
    }
    
    enum ProposalStatus { Active, Passed, Rejected, Executed }
    
    mapping(uint256 => Proposal) public proposals;
    mapping(uint256 => mapping(address => bool)) public hasVoted;
    mapping(string => uint256) public parameters;
    
    uint256 public nextProposalId;
    uint256 public quorumRequired = 100;
    uint256 public votingPeriod = 7 days;
    
    event ProposalCreated(uint256 indexed proposalId, address indexed proposer, string title);
    event VoteCast(uint256 indexed proposalId, address indexed voter, bool voteFor, uint256 votingPower);
    event ProposalExecuted(uint256 indexed proposalId);
    event ParameterUpdated(string name, uint256 value);
    
    constructor() {
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        
        // Initialize default parameters
        parameters["SALEABLE_PER_GRAM"] = 9;
        parameters["RESERVE_PER_GRAM"] = 1;
        parameters["CORPUS_CONTRIBUTION_PERCENT"] = 20;
        parameters["EARMARKING_PERCENT"] = 11;
        parameters["MINTER_SHARE_PERCENT"] = 6;
    }
    
    function createProposal(
        string calldata title,
        string calldata category
    ) external returns (uint256) {
        uint256 proposalId = nextProposalId++;
        
        proposals[proposalId] = Proposal({
            id: proposalId,
            proposer: msg.sender,
            title: title,
            category: category,
            votesFor: 0,
            votesAgainst: 0,
            votingEnds: block.timestamp + votingPeriod,
            status: ProposalStatus.Active
        });
        
        emit ProposalCreated(proposalId, msg.sender, title);
        return proposalId;
    }
    
    function vote(
        uint256 proposalId,
        bool voteFor,
        uint256 votingPower
    ) external {
        Proposal storage proposal = proposals[proposalId];
        require(proposal.status == ProposalStatus.Active, "Not active");
        require(block.timestamp < proposal.votingEnds, "Voting ended");
        require(!hasVoted[proposalId][msg.sender], "Already voted");
        
        hasVoted[proposalId][msg.sender] = true;
        
        if (voteFor) {
            proposal.votesFor += votingPower;
        } else {
            proposal.votesAgainst += votingPower;
        }
        
        emit VoteCast(proposalId, msg.sender, voteFor, votingPower);
        
        // Check if passed
        if (proposal.votesFor >= quorumRequired) {
            proposal.status = ProposalStatus.Passed;
        }
    }
    
    function executeProposal(uint256 proposalId) external {
        Proposal storage proposal = proposals[proposalId];
        require(proposal.status == ProposalStatus.Passed, "Not passed");
        
        proposal.status = ProposalStatus.Executed;
        
        emit ProposalExecuted(proposalId);
    }
    
    function updateParameter(string calldata name, uint256 value) external onlyRole(DEFAULT_ADMIN_ROLE) {
        parameters[name] = value;
        emit ParameterUpdated(name, value);
    }
    
    function getParameter(string calldata name) external view returns (uint256) {
        return parameters[name];
    }
}
