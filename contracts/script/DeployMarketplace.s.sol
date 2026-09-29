// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script} from "forge-std/Script.sol";
import {CarbonMarketplace} from "../src/CarbonMarketplace.sol";

/// @notice Rolling-upgrade helper for installations that already have registry and credit contracts.
contract DeployMarketplace is Script {
    function run() external returns (CarbonMarketplace marketplace) {
        uint256 deployerKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        address admin = vm.envAddress("CONTRACT_ADMIN_ADDRESS");
        address credits = vm.envAddress("CARBON_CREDIT_CONTRACT_ADDRESS");
        uint48 delay = uint48(vm.envOr("ADMIN_TRANSFER_DELAY_SECONDS", uint256(172800)));
        vm.startBroadcast(deployerKey);
        marketplace = new CarbonMarketplace(admin, delay, credits);
        vm.stopBroadcast();
    }
}
