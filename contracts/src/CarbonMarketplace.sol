// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AccessControlDefaultAdminRules} from "@openzeppelin/contracts/access/extensions/AccessControlDefaultAdminRules.sol";
import {ERC1155Holder} from "@openzeppelin/contracts/token/ERC1155/utils/ERC1155Holder.sol";
import {IERC1155} from "@openzeppelin/contracts/token/ERC1155/IERC1155.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @notice Non-custodial order book for CarbonLink credits. Sellers escrow only the
///         listed amount; buyers pay sellers atomically with the native network token.
contract CarbonMarketplace is ERC1155Holder, AccessControlDefaultAdminRules, Pausable, ReentrancyGuard {
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");
    uint256 public constant CREDIT_SCALE = 10_000;

    struct Listing {
        address seller;
        uint256 tokenId;
        uint256 remainingAmount;
        uint256 pricePerCreditWei;
        bool active;
    }

    IERC1155 public immutable credits;
    uint256 public nextListingId = 1;
    mapping(uint256 listingId => Listing listing) public listings;
    mapping(address seller => mapping(uint256 tokenId => uint256 amount)) public lockedBalance;
    uint256[] private _activeListingIds;
    mapping(uint256 listingId => uint256 indexPlusOne) private _activeListingIndex;

    error InvalidAmount();
    error InvalidPrice();
    error ListingNotActive();
    error NotSeller();
    error SelfTrade();
    error IncorrectPayment(uint256 expected, uint256 supplied);
    error PaymentFailed();

    event ListingCreated(uint256 indexed listingId, address indexed seller, uint256 indexed tokenId, uint256 amount, uint256 pricePerCreditWei);
    event ListingFilled(uint256 indexed listingId, address indexed buyer, address indexed seller, uint256 tokenId, uint256 amount, uint256 totalPaid);
    event ListingCancelled(uint256 indexed listingId, address indexed seller, uint256 returnedAmount);

    constructor(address initialAdmin, uint48 adminTransferDelay, address creditContract)
        AccessControlDefaultAdminRules(adminTransferDelay, initialAdmin)
    {
        if (creditContract == address(0)) revert InvalidAmount();
        credits = IERC1155(creditContract);
        _grantRole(PAUSER_ROLE, initialAdmin);
    }

    function createListing(uint256 tokenId, uint256 amount, uint256 pricePerCreditWei)
        external whenNotPaused nonReentrant returns (uint256 listingId)
    {
        if (amount == 0) revert InvalidAmount();
        if (pricePerCreditWei == 0) revert InvalidPrice();
        listingId = nextListingId++;
        listings[listingId] = Listing(msg.sender, tokenId, amount, pricePerCreditWei, true);
        _activeListingIndex[listingId] = _activeListingIds.length + 1;
        _activeListingIds.push(listingId);
        lockedBalance[msg.sender][tokenId] += amount;
        credits.safeTransferFrom(msg.sender, address(this), tokenId, amount, "");
        emit ListingCreated(listingId, msg.sender, tokenId, amount, pricePerCreditWei);
    }

    function buy(uint256 listingId, uint256 amount) external payable whenNotPaused nonReentrant {
        Listing storage listing = listings[listingId];
        if (!listing.active) revert ListingNotActive();
        if (msg.sender == listing.seller) revert SelfTrade();
        if (amount == 0 || amount > listing.remainingAmount) revert InvalidAmount();
        uint256 payment = (amount * listing.pricePerCreditWei + CREDIT_SCALE - 1) / CREDIT_SCALE;
        if (msg.value != payment) revert IncorrectPayment(payment, msg.value);
        listing.remainingAmount -= amount;
        lockedBalance[listing.seller][listing.tokenId] -= amount;
        if (listing.remainingAmount == 0) _deactivate(listingId, listing);
        credits.safeTransferFrom(address(this), msg.sender, listing.tokenId, amount, "");
        (bool sent,) = payable(listing.seller).call{value: payment}("");
        if (!sent) revert PaymentFailed();
        emit ListingFilled(listingId, msg.sender, listing.seller, listing.tokenId, amount, payment);
    }

    function cancel(uint256 listingId) external nonReentrant {
        Listing storage listing = listings[listingId];
        if (!listing.active) revert ListingNotActive();
        if (listing.seller != msg.sender) revert NotSeller();
        uint256 amount = listing.remainingAmount;
        listing.remainingAmount = 0;
        _deactivate(listingId, listing);
        lockedBalance[msg.sender][listing.tokenId] -= amount;
        credits.safeTransferFrom(address(this), msg.sender, listing.tokenId, amount, "");
        emit ListingCancelled(listingId, msg.sender, amount);
    }

    function pause() external onlyRole(PAUSER_ROLE) { _pause(); }
    function unpause() external onlyRole(PAUSER_ROLE) { _unpause(); }

    function activeListingCount() external view returns (uint256) { return _activeListingIds.length; }
    function activeListingIdAt(uint256 index) external view returns (uint256) { return _activeListingIds[index]; }

    function _deactivate(uint256 listingId, Listing storage listing) private {
        listing.active = false;
        uint256 index = _activeListingIndex[listingId] - 1;
        uint256 lastId = _activeListingIds[_activeListingIds.length - 1];
        if (lastId != listingId) {
            _activeListingIds[index] = lastId;
            _activeListingIndex[lastId] = index + 1;
        }
        _activeListingIds.pop();
        delete _activeListingIndex[listingId];
    }

    function supportsInterface(bytes4 interfaceId)
        public view override(ERC1155Holder, AccessControlDefaultAdminRules) returns (bool)
    {
        return super.supportsInterface(interfaceId);
    }
}
