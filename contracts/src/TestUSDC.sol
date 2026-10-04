// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import { ERC20 } from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import { Ownable } from "@openzeppelin/contracts/access/Ownable.sol";

/// @title CarbonLink Test USDC
/// @notice Six-decimal test token for local chains and public testnets only.
/// @dev The owner may mint freely. Never use this token as a production settlement asset.
contract TestUSDC is ERC20, Ownable {
    error InvalidRecipient();

    constructor(address initialOwner, uint256 initialSupply)
        ERC20("CarbonLink Test USD Coin", "tUSDC")
        Ownable(initialOwner)
    {
        if (initialOwner == address(0)) revert InvalidRecipient();
        _mint(initialOwner, initialSupply);
    }

    function decimals() public pure override returns (uint8) {
        return 6;
    }

    function mint(address recipient, uint256 amount) external onlyOwner {
        if (recipient == address(0)) revert InvalidRecipient();
        _mint(recipient, amount);
    }
}
