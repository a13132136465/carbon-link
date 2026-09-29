// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import { Test } from "forge-std/Test.sol";
import { CarbonProjectRegistry } from "../src/CarbonProjectRegistry.sol";
import { CarbonCreditLedger } from "../src/CarbonCreditLedger.sol";
import { CarbonMarketplace } from "../src/CarbonMarketplace.sol";

contract CarbonLinkTest is Test {
    CarbonProjectRegistry internal registry;
    CarbonCreditLedger internal credits;
    CarbonMarketplace internal marketplace;
    address internal admin = makeAddr("admin");
    address internal issuer = makeAddr("issuer");
    address internal verifier = makeAddr("verifier");
    address internal owner = makeAddr("owner");
    address internal buyer = makeAddr("buyer");
    uint256 internal projectId;

    function setUp() public {
        vm.startPrank(admin);
        registry = new CarbonProjectRegistry(admin, issuer, 2 days);
        credits = new CarbonCreditLedger(admin, issuer, 2 days, address(registry));
        marketplace = new CarbonMarketplace(admin, 2 days, address(credits));
        registry.grantRole(registry.REGISTRAR_ROLE(), issuer);
        registry.grantRole(registry.VERIFIER_ROLE(), verifier);
        credits.grantRole(credits.ISSUER_ROLE(), issuer);
        credits.grantRole(credits.VERIFIER_ROLE(), verifier);
        vm.stopPrank();

        vm.prank(issuer);
        projectId = registry.registerProject(
            owner, "PRJ-2026-001", keccak256("project metadata"), "ipfs://project/metadata.json"
        );
    }

    function testUsersSignAtomicMarketplaceTrade() public {
        uint256 batchId = _issue(10 * 10_000);
        vm.prank(owner);
        credits.setApprovalForAll(address(marketplace), true);
        vm.prank(owner);
        uint256 listingId = marketplace.createListing(batchId, 2 * 10_000, 1 ether);
        assertEq(marketplace.activeListingCount(), 1);
        assertEq(marketplace.activeListingIdAt(0), listingId);
        assertEq(credits.balanceOf(owner, batchId), 8 * 10_000);
        assertEq(marketplace.lockedBalance(owner, batchId), 2 * 10_000);

        vm.deal(buyer, 2 ether);
        vm.prank(buyer);
        marketplace.buy{value: 1 ether}(listingId, 1 * 10_000);
        assertEq(credits.balanceOf(buyer, batchId), 1 * 10_000);
        assertEq(marketplace.lockedBalance(owner, batchId), 1 * 10_000);

        vm.prank(owner);
        marketplace.cancel(listingId);
        assertEq(credits.balanceOf(owner, batchId), 9 * 10_000);
        assertEq(marketplace.lockedBalance(owner, batchId), 0);
        assertEq(marketplace.activeListingCount(), 0);
    }

    function testRegisterProjectAndLookup() public view {
        assertEq(projectId, 1);
        assertEq(registry.ownerOf(projectId), owner);
        assertEq(registry.tokenByExternalProjectId("PRJ-2026-001"), projectId);
        assertTrue(registry.isActive(projectId));
        CarbonProjectRegistry.ProjectRecord memory record = registry.getProject(projectId);
        assertEq(record.externalIdHash, keccak256("PRJ-2026-001"));
        assertEq(uint256(record.status), uint256(CarbonProjectRegistry.ProjectStatus.Active));
    }

    function testCannotRegisterDuplicateProject() public {
        vm.prank(issuer);
        vm.expectRevert(
            abi.encodeWithSelector(
                CarbonProjectRegistry.ProjectAlreadyRegistered.selector, keccak256("PRJ-2026-001")
            )
        );
        registry.registerProject(owner, "PRJ-2026-001", bytes32(uint256(1)), "ipfs://other");
    }

    function testRevocationIsFinalAndPreventsIssuance() public {
        vm.prank(verifier);
        registry.setProjectStatus(projectId, CarbonProjectRegistry.ProjectStatus.Revoked);
        assertFalse(registry.isActive(projectId));

        vm.prank(verifier);
        vm.expectRevert(
            abi.encodeWithSelector(CarbonProjectRegistry.RevokedProjectIsFinal.selector, projectId)
        );
        registry.setProjectStatus(projectId, CarbonProjectRegistry.ProjectStatus.Active);

        vm.prank(issuer);
        vm.expectRevert(
            abi.encodeWithSelector(CarbonCreditLedger.InactiveProject.selector, projectId)
        );
        credits.issueBatch(
            owner,
            projectId,
            keccak256("verification"),
            2026,
            100,
            keccak256("batch"),
            "ipfs://batch"
        );
    }

    function testIssueTransferAndRetire() public {
        uint256 batchId = _issue(1_000);
        assertEq(credits.balanceOf(owner, batchId), 1_000);
        assertEq(credits.uri(batchId), "ipfs://batch/metadata.json");

        vm.prank(owner);
        credits.safeTransferFrom(owner, buyer, batchId, 250, "");
        assertEq(credits.balanceOf(buyer, batchId), 250);

        bytes32 beneficiaryHash = keccak256("Example Manufacturing Ltd");
        bytes32 evidenceDigest = keccak256("2026 emissions evidence");
        vm.prank(buyer);
        uint256 retirementId = credits.retire(batchId, 100, beneficiaryHash, evidenceDigest);

        assertEq(credits.balanceOf(buyer, batchId), 150);
        CarbonCreditLedger.CreditBatch memory batch = credits.getBatch(batchId);
        assertEq(batch.totalIssued, 1_000);
        assertEq(batch.totalRetired, 100);
        CarbonCreditLedger.RetirementRecord memory record = credits.getRetirement(retirementId);
        assertEq(record.account, buyer);
        assertEq(record.beneficiaryHash, beneficiaryHash);
        assertEq(record.evidenceDigest, evidenceDigest);
    }

    function testCannotIssueSameVerificationTwice() public {
        _issue(100);
        bytes32 verificationHash = keccak256("AUD-2026-001");
        vm.prank(issuer);
        vm.expectRevert(
            abi.encodeWithSelector(
                CarbonCreditLedger.VerificationAlreadyIssued.selector, verificationHash
            )
        );
        credits.issueBatch(
            owner,
            projectId,
            verificationHash,
            2026,
            100,
            keccak256("batch"),
            "ipfs://batch/metadata.json"
        );
    }

    function testFrozenBatchCannotTransferOrRetire() public {
        uint256 batchId = _issue(100);
        vm.prank(verifier);
        credits.setBatchFrozen(batchId, true);

        vm.prank(owner);
        vm.expectRevert(abi.encodeWithSelector(CarbonCreditLedger.BatchFrozen.selector, batchId));
        credits.safeTransferFrom(owner, buyer, batchId, 1, "");

        vm.prank(owner);
        vm.expectRevert(abi.encodeWithSelector(CarbonCreditLedger.BatchFrozen.selector, batchId));
        credits.retire(batchId, 1, keccak256("beneficiary"), keccak256("evidence"));
    }

    function testPauseStopsRegistryAndCreditMovement() public {
        uint256 batchId = _issue(100);
        vm.prank(admin);
        registry.pause();
        vm.prank(owner);
        vm.expectRevert();
        registry.transferFrom(owner, buyer, projectId);

        vm.prank(admin);
        credits.pause();
        vm.prank(owner);
        vm.expectRevert();
        credits.safeTransferFrom(owner, buyer, batchId, 1, "");
    }

    function testOnlyAuthorizedRolesCanMutate() public {
        vm.prank(buyer);
        vm.expectRevert();
        registry.registerProject(buyer, "ATTACK", bytes32(uint256(1)), "ipfs://attack");

        vm.prank(buyer);
        vm.expectRevert();
        credits.issueBatch(
            buyer, projectId, keccak256("attack"), 2026, 1, bytes32(uint256(1)), "ipfs://attack"
        );
    }

    function testFuzzRetirementNeverExceedsIssued(uint96 issued, uint96 retired) public {
        issued = uint96(bound(issued, 1, type(uint96).max));
        retired = uint96(bound(retired, 1, issued));
        uint256 batchId = _issue(issued);
        vm.prank(owner);
        credits.retire(batchId, retired, keccak256("beneficiary"), keccak256("evidence"));
        CarbonCreditLedger.CreditBatch memory batch = credits.getBatch(batchId);
        assertLe(batch.totalRetired, batch.totalIssued);
        assertEq(credits.balanceOf(owner, batchId), uint256(issued) - uint256(retired));
    }

    function _issue(uint256 amount) internal returns (uint256) {
        vm.prank(issuer);
        return credits.issueBatch(
            owner,
            projectId,
            keccak256("AUD-2026-001"),
            2026,
            amount,
            keccak256("batch metadata"),
            "ipfs://batch/metadata.json"
        );
    }
}
