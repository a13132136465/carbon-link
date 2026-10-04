// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import { Script } from "forge-std/Script.sol";
import { TestUSDC } from "../src/TestUSDC.sol";

/// @notice Deploys tUSDC for local development or a public testnet.
contract DeployTestUSDC is Script {
    uint256 private constant UNIT = 1e6;

    function run() external returns (TestUSDC token) {
        uint256 deployerKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        address owner = vm.envAddress("TEST_USDC_OWNER_ADDRESS");
        uint256 initialWholeTokens = vm.envOr("TEST_USDC_INITIAL_SUPPLY", uint256(1_000_000));

        vm.startBroadcast(deployerKey);
        token = new TestUSDC(owner, initialWholeTokens * UNIT);
        vm.stopBroadcast();
    }
}
