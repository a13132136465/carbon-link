// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {
    AccessControlDefaultAdminRules
} from "@openzeppelin/contracts/access/extensions/AccessControlDefaultAdminRules.sol";
import { ERC1155 } from "@openzeppelin/contracts/token/ERC1155/ERC1155.sol";
import {
    ERC1155Pausable
} from "@openzeppelin/contracts/token/ERC1155/extensions/ERC1155Pausable.sol";
import { CarbonProjectRegistry } from "./CarbonProjectRegistry.sol";

/// @title CarbonCreditLedger
/// @notice ERC-1155 batches representing verified carbon credits. One token unit equals one
///         platform base unit; the off-chain registry defines its display precision.
contract CarbonCreditLedger is ERC1155Pausable, AccessControlDefaultAdminRules {
    bytes32 public constant ISSUER_ROLE = keccak256("ISSUER_ROLE");
    bytes32 public constant VERIFIER_ROLE = keccak256("VERIFIER_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");

    struct CreditBatch {
        uint256 projectTokenId;
        bytes32 verificationHash;
        bytes32 metadataDigest;
        uint64 vintage;
        uint64 issuedAt;
        uint256 totalIssued;
        uint256 totalRetired;
        bool frozen;
    }

    struct RetirementRecord {
        uint256 batchId;
        address account;
        uint256 amount;
        bytes32 beneficiaryHash;
        bytes32 evidenceDigest;
        uint64 retiredAt;
    }

    CarbonProjectRegistry public immutable projectRegistry;
    uint256 private _nextBatchId = 1;
    uint256 private _nextRetirementId = 1;
    mapping(uint256 batchId => CreditBatch batch) private _batches;
    mapping(uint256 batchId => string metadataURI) private _batchURIs;
    mapping(bytes32 verificationHash => uint256 batchId) private _batchByVerificationHash;
    mapping(uint256 retirementId => RetirementRecord record) private _retirements;

    error BatchFrozen(uint256 batchId);
    error BatchNotFound(uint256 batchId);
    error EmptyBeneficiaryHash();
    error EmptyMetadataURI();
    error InactiveProject(uint256 projectTokenId);
    error InvalidAmount();
    error InvalidRecipient();
    error InvalidRegistry();
    error InvalidVerificationHash();
    error InvalidVintage();
    error RetirementNotFound(uint256 retirementId);
    error VerificationAlreadyIssued(bytes32 verificationHash);

    event CreditBatchIssued(
        uint256 indexed batchId,
        uint256 indexed projectTokenId,
        bytes32 indexed verificationHash,
        address recipient,
        uint64 vintage,
        uint256 amount,
        bytes32 metadataDigest,
        string metadataURI
    );
    event BatchFrozenStatusChanged(uint256 indexed batchId, bool frozen);
    event BatchMetadataUpdated(
        uint256 indexed batchId, bytes32 indexed metadataDigest, string metadataURI
    );
    event CreditRetired(
        uint256 indexed retirementId,
        uint256 indexed batchId,
        address indexed account,
        uint256 amount,
        bytes32 beneficiaryHash,
        bytes32 evidenceDigest
    );

    constructor(
        address initialAdmin,
        address initialOperator,
        uint48 adminTransferDelay,
        address registry
    ) ERC1155("") AccessControlDefaultAdminRules(adminTransferDelay, initialAdmin) {
        if (initialAdmin == address(0)) revert InvalidRecipient();
        if (initialOperator == address(0)) revert InvalidRecipient();
        if (registry == address(0)) revert InvalidRegistry();
        projectRegistry = CarbonProjectRegistry(registry);
        _grantRole(ISSUER_ROLE, initialAdmin);
        _grantRole(VERIFIER_ROLE, initialAdmin);
        _grantRole(PAUSER_ROLE, initialAdmin);
        _grantRole(ISSUER_ROLE, initialOperator);
    }

    function issueBatch(
        address recipient,
        uint256 projectTokenId,
        bytes32 verificationHash,
        uint64 vintage,
        uint256 amount,
        bytes32 metadataDigest,
        string calldata metadataURI
    ) external onlyRole(ISSUER_ROLE) whenNotPaused returns (uint256 batchId) {
        if (recipient == address(0)) revert InvalidRecipient();
        if (!projectRegistry.isActive(projectTokenId)) revert InactiveProject(projectTokenId);
        if (verificationHash == bytes32(0)) revert InvalidVerificationHash();
        if (vintage == 0) revert InvalidVintage();
        if (amount == 0) revert InvalidAmount();
        if (bytes(metadataURI).length == 0) revert EmptyMetadataURI();
        if (_batchByVerificationHash[verificationHash] != 0) {
            revert VerificationAlreadyIssued(verificationHash);
        }

        batchId = _nextBatchId++;
        _batches[batchId] = CreditBatch({
            projectTokenId: projectTokenId,
            verificationHash: verificationHash,
            metadataDigest: metadataDigest,
            vintage: vintage,
            issuedAt: uint64(block.timestamp),
            totalIssued: amount,
            totalRetired: 0,
            frozen: false
        });
        _batchURIs[batchId] = metadataURI;
        _batchByVerificationHash[verificationHash] = batchId;
        _mint(recipient, batchId, amount, "");

        emit CreditBatchIssued(
            batchId,
            projectTokenId,
            verificationHash,
            recipient,
            vintage,
            amount,
            metadataDigest,
            metadataURI
        );
    }

    function retire(
        uint256 batchId,
        uint256 amount,
        bytes32 beneficiaryHash,
        bytes32 evidenceDigest
    ) external whenNotPaused returns (uint256 retirementId) {
        _requireUsableBatch(batchId);
        if (amount == 0) revert InvalidAmount();
        if (beneficiaryHash == bytes32(0)) revert EmptyBeneficiaryHash();
        _burn(msg.sender, batchId, amount);
        _batches[batchId].totalRetired += amount;

        retirementId = _nextRetirementId++;
        _retirements[retirementId] = RetirementRecord({
            batchId: batchId,
            account: msg.sender,
            amount: amount,
            beneficiaryHash: beneficiaryHash,
            evidenceDigest: evidenceDigest,
            retiredAt: uint64(block.timestamp)
        });
        emit CreditRetired(
            retirementId, batchId, msg.sender, amount, beneficiaryHash, evidenceDigest
        );
    }

    function setBatchFrozen(uint256 batchId, bool frozen) external onlyRole(VERIFIER_ROLE) {
        _requireBatch(batchId);
        _batches[batchId].frozen = frozen;
        emit BatchFrozenStatusChanged(batchId, frozen);
    }

    function updateBatchMetadata(
        uint256 batchId,
        bytes32 metadataDigest,
        string calldata metadataURI
    ) external onlyRole(VERIFIER_ROLE) {
        _requireBatch(batchId);
        if (bytes(metadataURI).length == 0) revert EmptyMetadataURI();
        _batches[batchId].metadataDigest = metadataDigest;
        _batchURIs[batchId] = metadataURI;
        emit BatchMetadataUpdated(batchId, metadataDigest, metadataURI);
    }

    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
    }

    function uri(uint256 batchId) public view override returns (string memory) {
        _requireBatch(batchId);
        return _batchURIs[batchId];
    }

    function getBatch(uint256 batchId) external view returns (CreditBatch memory) {
        _requireBatch(batchId);
        return _batches[batchId];
    }

    function getRetirement(uint256 retirementId) external view returns (RetirementRecord memory) {
        if (_retirements[retirementId].account == address(0)) {
            revert RetirementNotFound(retirementId);
        }
        return _retirements[retirementId];
    }

    function batchByVerificationHash(bytes32 verificationHash) external view returns (uint256) {
        return _batchByVerificationHash[verificationHash];
    }

    function supportsInterface(bytes4 interfaceId)
        public
        view
        override(ERC1155, AccessControlDefaultAdminRules)
        returns (bool)
    {
        return super.supportsInterface(interfaceId);
    }

    function _update(address from, address to, uint256[] memory ids, uint256[] memory values)
        internal
        override(ERC1155Pausable)
    {
        for (uint256 i = 0; i < ids.length; ++i) {
            if (_batches[ids[i]].frozen) revert BatchFrozen(ids[i]);
        }
        super._update(from, to, ids, values);
    }

    function _requireBatch(uint256 batchId) internal view {
        if (_batches[batchId].totalIssued == 0) revert BatchNotFound(batchId);
    }

    function _requireUsableBatch(uint256 batchId) internal view {
        _requireBatch(batchId);
        if (_batches[batchId].frozen) revert BatchFrozen(batchId);
    }
}
