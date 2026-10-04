// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import { Test } from "forge-std/Test.sol";
import { TestUSDC } from "../src/TestUSDC.sol";

contract TestUSDCTest is Test {
    address internal owner = makeAddr("owner");
    address internal user = makeAddr("user");
    TestUSDC internal token;

    function setUp() public {
        token = new TestUSDC(owner, 1_000_000e6);
    }

    function testUsesSixDecimalsAndMintsInitialSupply() public view {
        assertEq(token.name(), "CarbonLink Test USD Coin");
        assertEq(token.symbol(), "tUSDC");
        assertEq(token.decimals(), 6);
        assertEq(token.balanceOf(owner), 1_000_000e6);
    }

    function testOwnerCanMintAndUsersCanTransfer() public {
        vm.prank(owner);
        token.mint(user, 100e6);
        assertEq(token.balanceOf(user), 100e6);

        vm.prank(user);
        token.transfer(owner, 25e6);
        assertEq(token.balanceOf(user), 75e6);
    }

    function testNonOwnerCannotMint() public {
        vm.prank(user);
        vm.expectRevert();
        token.mint(user, 1e6);
    }
}
