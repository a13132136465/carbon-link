// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {
    AccessControlDefaultAdminRules
} from "@openzeppelin/contracts/access/extensions/AccessControlDefaultAdminRules.sol";
import { ERC1155Holder } from "@openzeppelin/contracts/token/ERC1155/utils/ERC1155Holder.sol";
import { IERC1155 } from "@openzeppelin/contracts/token/ERC1155/IERC1155.sol";
import { IERC20 } from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import { SafeERC20 } from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import { Pausable } from "@openzeppelin/contracts/utils/Pausable.sol";
import { ReentrancyGuard } from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @notice Self-custodial carbon-credit/USDC order book. Makers escrow only the
///         asset committed by an order; every create, fill and cancel is user-signed.
contract CarbonMarketplace is
    ERC1155Holder,
    AccessControlDefaultAdminRules,
    Pausable,
    ReentrancyGuard
{
    using SafeERC20 for IERC20;

    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");
    uint256 public constant CREDIT_SCALE = 10_000;

    enum Side {
        Buy,
        Sell
    }

    struct Order {
        address maker;
        uint256 tokenId;
        uint256 remainingAmount;
        uint256 pricePerCredit;
        uint256 remainingQuote;
        Side side;
        bool active;
        uint64 createdAt;
    }

    struct Trade {
        uint256 orderId;
        address buyer;
        address seller;
        uint256 tokenId;
        uint256 amount;
        uint256 quoteAmount;
        uint256 pricePerCredit;
        Side takerSide;
        uint64 timestamp;
    }

    IERC1155 public immutable credits;
    IERC20 public immutable usdc;
    uint256 public nextOrderId = 1;
    mapping(uint256 orderId => Order order) public orders;
    mapping(address seller => mapping(uint256 tokenId => uint256 amount)) public lockedBalance;
    mapping(address buyer => uint256 amount) public lockedUsdc;
    uint256[] private _activeOrderIds;
    mapping(uint256 orderId => uint256 indexPlusOne) private _activeOrderIndex;
    Trade[] private _trades;

    error InvalidAddress();
    error InvalidAmount();
    error InvalidPrice();
    error OrderNotActive();
    error WrongSide();
    error NotMaker();
    error SelfTrade();

    event OrderCreated(
        uint256 indexed orderId,
        address indexed maker,
        uint256 indexed tokenId,
        Side side,
        uint256 amount,
        uint256 pricePerCredit,
        uint64 createdAt
    );
    event OrderFilled(
        uint256 indexed orderId,
        address indexed taker,
        address indexed maker,
        uint256 tokenId,
        Side takerSide,
        uint256 amount,
        uint256 quoteAmount,
        uint256 pricePerCredit,
        uint64 timestamp
    );
    event OrderCancelled(
        uint256 indexed orderId, address indexed maker, Side side, uint256 returnedAmount
    );

    constructor(
        address initialAdmin,
        uint48 adminTransferDelay,
        address creditContract,
        address usdcContract
    ) AccessControlDefaultAdminRules(adminTransferDelay, initialAdmin) {
        if (creditContract == address(0) || usdcContract == address(0)) {
            revert InvalidAddress();
        }
        credits = IERC1155(creditContract);
        usdc = IERC20(usdcContract);
        _grantRole(PAUSER_ROLE, initialAdmin);
    }

    function createSellOrder(uint256 tokenId, uint256 amount, uint256 pricePerCredit)
        external
        whenNotPaused
        nonReentrant
        returns (uint256 orderId)
    {
        _validate(amount, pricePerCredit);
        orderId = _create(msg.sender, tokenId, amount, pricePerCredit, Side.Sell, 0);
        lockedBalance[msg.sender][tokenId] += amount;
        credits.safeTransferFrom(msg.sender, address(this), tokenId, amount, "");
    }

    /// @notice Creates a market-wide bid. tokenId zero denotes any issued carbon-credit batch.
    function createBuyOrder(uint256 amount, uint256 pricePerCredit)
        external
        whenNotPaused
        nonReentrant
        returns (uint256 orderId)
    {
        _validate(amount, pricePerCredit);
        uint256 quote = quoteFor(amount, pricePerCredit);
        if (quote == 0) revert InvalidPrice();
        orderId = _create(msg.sender, 0, amount, pricePerCredit, Side.Buy, quote);
        lockedUsdc[msg.sender] += quote;
        usdc.safeTransferFrom(msg.sender, address(this), quote);
    }

    /// @notice Buyer takes an existing sell order. Buyer must approve USDC first.
    function fillSellOrder(uint256 orderId, uint256 amount) external whenNotPaused nonReentrant {
        Order storage order = orders[orderId];
        if (!order.active) revert OrderNotActive();
        if (order.side != Side.Sell) revert WrongSide();
        if (order.maker == msg.sender) revert SelfTrade();
        _validateFill(order, amount);
        uint256 quote = quoteFor(amount, order.pricePerCredit);
        if (quote == 0) revert InvalidAmount();
        order.remainingAmount -= amount;
        lockedBalance[order.maker][order.tokenId] -= amount;
        if (order.remainingAmount == 0) _deactivate(orderId, order);
        usdc.safeTransferFrom(msg.sender, order.maker, quote);
        credits.safeTransferFrom(address(this), msg.sender, order.tokenId, amount, "");
        _recordTrade(
            orderId, msg.sender, order.maker, order.tokenId, order, Side.Buy, amount, quote
        );
    }

    /// @notice Seller takes a market-wide bid and chooses the batch delivered to the buyer.
    function fillBuyOrder(uint256 orderId, uint256 tokenId, uint256 amount)
        external
        whenNotPaused
        nonReentrant
    {
        Order storage order = orders[orderId];
        if (!order.active) revert OrderNotActive();
        if (order.side != Side.Buy) revert WrongSide();
        if (order.maker == msg.sender) revert SelfTrade();
        _validateFill(order, amount);
        uint256 quote = amount == order.remainingAmount
            ? order.remainingQuote
            : quoteFor(amount, order.pricePerCredit);
        if (quote == 0 || quote > order.remainingQuote) revert InvalidAmount();
        order.remainingAmount -= amount;
        order.remainingQuote -= quote;
        lockedUsdc[order.maker] -= quote;
        if (order.remainingAmount == 0) _deactivate(orderId, order);
        credits.safeTransferFrom(msg.sender, order.maker, tokenId, amount, "");
        usdc.safeTransfer(msg.sender, quote);
        _recordTrade(orderId, order.maker, msg.sender, tokenId, order, Side.Sell, amount, quote);
    }

    function cancel(uint256 orderId) external nonReentrant {
        Order storage order = orders[orderId];
        if (!order.active) revert OrderNotActive();
        if (order.maker != msg.sender) revert NotMaker();
        uint256 returned;
        if (order.side == Side.Sell) {
            returned = order.remainingAmount;
            lockedBalance[msg.sender][order.tokenId] -= returned;
            credits.safeTransferFrom(address(this), msg.sender, order.tokenId, returned, "");
        } else {
            returned = order.remainingQuote;
            lockedUsdc[msg.sender] -= returned;
            usdc.safeTransfer(msg.sender, returned);
        }
        order.remainingAmount = 0;
        order.remainingQuote = 0;
        _deactivate(orderId, order);
        emit OrderCancelled(orderId, msg.sender, order.side, returned);
    }

    function quoteFor(uint256 amount, uint256 pricePerCredit) public pure returns (uint256) {
        return amount * pricePerCredit / CREDIT_SCALE;
    }

    function activeOrderCount() external view returns (uint256) {
        return _activeOrderIds.length;
    }

    function activeOrderIdAt(uint256 index) external view returns (uint256) {
        return _activeOrderIds[index];
    }

    function tradeCount() external view returns (uint256) {
        return _trades.length;
    }

    function tradeAt(uint256 index) external view returns (Trade memory) {
        return _trades[index];
    }

    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
    }

    function _create(
        address maker,
        uint256 tokenId,
        uint256 amount,
        uint256 price,
        Side side,
        uint256 quote
    ) private returns (uint256 orderId) {
        orderId = nextOrderId++;
        uint64 createdAt = uint64(block.timestamp);
        orders[orderId] = Order(maker, tokenId, amount, price, quote, side, true, createdAt);
        _activeOrderIndex[orderId] = _activeOrderIds.length + 1;
        _activeOrderIds.push(orderId);
        emit OrderCreated(orderId, maker, tokenId, side, amount, price, createdAt);
    }

    function _recordTrade(
        uint256 orderId,
        address buyer,
        address seller,
        uint256 tokenId,
        Order storage order,
        Side takerSide,
        uint256 amount,
        uint256 quote
    ) private {
        uint64 timestamp = uint64(block.timestamp);
        _trades.push(
            Trade(
                orderId,
                buyer,
                seller,
                tokenId,
                amount,
                quote,
                order.pricePerCredit,
                takerSide,
                timestamp
            )
        );
        emit OrderFilled(
            orderId,
            takerSide == Side.Buy ? buyer : seller,
            order.maker,
            tokenId,
            takerSide,
            amount,
            quote,
            order.pricePerCredit,
            timestamp
        );
    }

    function _validate(uint256 amount, uint256 price) private pure {
        if (amount == 0) revert InvalidAmount();
        if (price == 0) revert InvalidPrice();
    }

    function _validateFill(Order storage order, uint256 amount) private view {
        if (amount == 0 || amount > order.remainingAmount) revert InvalidAmount();
    }

    function _deactivate(uint256 orderId, Order storage order) private {
        order.active = false;
        uint256 index = _activeOrderIndex[orderId] - 1;
        uint256 lastId = _activeOrderIds[_activeOrderIds.length - 1];
        if (lastId != orderId) {
            _activeOrderIds[index] = lastId;
            _activeOrderIndex[lastId] = index + 1;
        }
        _activeOrderIds.pop();
        delete _activeOrderIndex[orderId];
    }

    function supportsInterface(bytes4 interfaceId)
        public
        view
        override(ERC1155Holder, AccessControlDefaultAdminRules)
        returns (bool)
    {
        return super.supportsInterface(interfaceId);
    }
}
