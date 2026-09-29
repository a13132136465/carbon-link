// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import { Script } from "forge-std/Script.sol";
import { CarbonProjectRegistry } from "../src/CarbonProjectRegistry.sol";
import { CarbonCreditLedger } from "../src/CarbonCreditLedger.sol";
import { CarbonMarketplace } from "../src/CarbonMarketplace.sol";

contract DeployCarbonLink is Script {
    function run() external returns (CarbonProjectRegistry registry, CarbonCreditLedger credits, CarbonMarketplace marketplace) {
        uint256 deployerKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        address admin = vm.envAddress("CONTRACT_ADMIN_ADDRESS");
        address operator = vm.envAddress("BLOCKCHAIN_OPERATOR_ADDRESS");
        uint48 delay = uint48(vm.envOr("ADMIN_TRANSFER_DELAY_SECONDS", uint256(172800)));

        vm.startBroadcast(deployerKey);
        registry = new CarbonProjectRegistry(admin, operator, delay);
        credits = new CarbonCreditLedger(admin, operator, delay, address(registry));
        marketplace = new CarbonMarketplace(admin, delay, address(credits));
        vm.stopBroadcast();
    }
}
