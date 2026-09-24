// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {
    AccessControlDefaultAdminRules
} from "@openzeppelin/contracts/access/extensions/AccessControlDefaultAdminRules.sol";
import { ERC721 } from "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import { ERC721Pausable } from "@openzeppelin/contracts/token/ERC721/extensions/ERC721Pausable.sol";
import {
    ERC721URIStorage
} from "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";

/// @title CarbonProjectRegistry
/// @notice Registry of verified carbon projects. One external project identifier maps to one NFT.
/// @dev The default administrator uses OpenZeppelin's delayed two-step transfer mechanism.
contract CarbonProjectRegistry is ERC721URIStorage, ERC721Pausable, AccessControlDefaultAdminRules {
    bytes32 public constant REGISTRAR_ROLE = keccak256("REGISTRAR_ROLE");
    bytes32 public constant VERIFIER_ROLE = keccak256("VERIFIER_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");

    enum ProjectStatus {
        Active,
        Suspended,
        Revoked
    }

    struct ProjectRecord {
        bytes32 externalIdHash;
        bytes32 metadataDigest;
        uint64 registeredAt;
        ProjectStatus status;
    }

    uint256 private _nextTokenId = 1;
    mapping(uint256 tokenId => ProjectRecord record) private _projects;
    mapping(bytes32 externalIdHash => uint256 tokenId) private _tokenByExternalIdHash;

    error EmptyExternalProjectId();
    error EmptyMetadataURI();
    error InvalidRecipient();
    error ProjectAlreadyRegistered(bytes32 externalIdHash);
    error ProjectNotFound(uint256 tokenId);
    error RevokedProjectIsFinal(uint256 tokenId);

    event ProjectRegistered(
        uint256 indexed tokenId,
        bytes32 indexed externalIdHash,
        address indexed owner,
        bytes32 metadataDigest,
        string metadataURI
    );
    event ProjectStatusChanged(
        uint256 indexed tokenId, ProjectStatus previousStatus, ProjectStatus newStatus
    );
    event ProjectMetadataUpdated(
        uint256 indexed tokenId, bytes32 indexed metadataDigest, string metadataURI
    );

    constructor(address initialAdmin, address initialOperator, uint48 adminTransferDelay)
        ERC721("CarbonLink Verified Project", "CLVP")
        AccessControlDefaultAdminRules(adminTransferDelay, initialAdmin)
    {
        if (initialAdmin == address(0)) revert InvalidRecipient();
        if (initialOperator == address(0)) revert InvalidRecipient();
        _grantRole(REGISTRAR_ROLE, initialAdmin);
        _grantRole(VERIFIER_ROLE, initialAdmin);
        _grantRole(PAUSER_ROLE, initialAdmin);
        _grantRole(REGISTRAR_ROLE, initialOperator);
    }

    function registerProject(
        address owner,
        string calldata externalProjectId,
        bytes32 metadataDigest,
        string calldata metadataURI
    ) external onlyRole(REGISTRAR_ROLE) whenNotPaused returns (uint256 tokenId) {
        if (owner == address(0)) revert InvalidRecipient();
        if (bytes(externalProjectId).length == 0) revert EmptyExternalProjectId();
        if (bytes(metadataURI).length == 0) revert EmptyMetadataURI();

        bytes32 externalIdHash = keccak256(bytes(externalProjectId));
        if (_tokenByExternalIdHash[externalIdHash] != 0) {
            revert ProjectAlreadyRegistered(externalIdHash);
        }

        tokenId = _nextTokenId++;
        _projects[tokenId] = ProjectRecord({
            externalIdHash: externalIdHash,
            metadataDigest: metadataDigest,
            registeredAt: uint64(block.timestamp),
            status: ProjectStatus.Active
        });
        _tokenByExternalIdHash[externalIdHash] = tokenId;
        _safeMint(owner, tokenId);
        _setTokenURI(tokenId, metadataURI);

        emit ProjectRegistered(tokenId, externalIdHash, owner, metadataDigest, metadataURI);
    }

    function updateMetadata(uint256 tokenId, bytes32 digest, string calldata metadataURI)
        external
        onlyRole(REGISTRAR_ROLE)
    {
        _requireProject(tokenId);
        if (bytes(metadataURI).length == 0) revert EmptyMetadataURI();
        _projects[tokenId].metadataDigest = digest;
        _setTokenURI(tokenId, metadataURI);
        emit ProjectMetadataUpdated(tokenId, digest, metadataURI);
    }

    function setProjectStatus(uint256 tokenId, ProjectStatus newStatus)
        external
        onlyRole(VERIFIER_ROLE)
    {
        _requireProject(tokenId);
        ProjectStatus previous = _projects[tokenId].status;
        if (previous == ProjectStatus.Revoked) revert RevokedProjectIsFinal(tokenId);
        _projects[tokenId].status = newStatus;
        emit ProjectStatusChanged(tokenId, previous, newStatus);
    }

    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
    }

    function getProject(uint256 tokenId) external view returns (ProjectRecord memory) {
        _requireProject(tokenId);
        return _projects[tokenId];
    }

    function tokenByExternalProjectId(string calldata externalProjectId)
        external
        view
        returns (uint256)
    {
        return _tokenByExternalIdHash[keccak256(bytes(externalProjectId))];
    }

    function isActive(uint256 tokenId) external view returns (bool) {
        return _ownerOf(tokenId) != address(0) && _projects[tokenId].status == ProjectStatus.Active;
    }

    function supportsInterface(bytes4 interfaceId)
        public
        view
        override(ERC721, ERC721URIStorage, AccessControlDefaultAdminRules)
        returns (bool)
    {
        return super.supportsInterface(interfaceId);
    }

    function tokenURI(uint256 tokenId)
        public
        view
        override(ERC721, ERC721URIStorage)
        returns (string memory)
    {
        return super.tokenURI(tokenId);
    }

    function _update(address to, uint256 tokenId, address auth)
        internal
        override(ERC721, ERC721Pausable)
        returns (address)
    {
        return super._update(to, tokenId, auth);
    }

    function _requireProject(uint256 tokenId) internal view {
        if (_ownerOf(tokenId) == address(0)) revert ProjectNotFound(tokenId);
    }
}
