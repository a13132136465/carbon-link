"""Queue one-time transfers from the legacy omnibus wallet to verified user wallets.

Run without --execute for a read-only preflight. Open legacy listings must be
cancelled first so every database holding is transferable and unambiguous.
"""
import argparse
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from web3 import HTTPProvider, Web3

from app.chain_worker import CREDIT_ABI, PROJECT_ABI, SCALE
from app.config import settings
from app.database import SessionLocal
from app.models import ChainOperation, CreditBatch, Holding, Listing, ListingStatus, Project, ProjectStatus, User


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="persist transfer operations after a successful preflight")
    args = parser.parse_args()
    if not settings.blockchain_enabled:
        raise SystemExit("BLOCKCHAIN_ENABLED must be true")
    w3 = Web3(HTTPProvider(settings.blockchain_rpc_url, request_kwargs={"timeout": settings.blockchain_request_timeout_seconds}))
    operator = Web3.to_checksum_address(settings.blockchain_operator_address)
    projects_contract = w3.eth.contract(address=Web3.to_checksum_address(settings.carbon_project_contract_address), abi=PROJECT_ABI)
    credits_contract = w3.eth.contract(address=Web3.to_checksum_address(settings.carbon_credit_contract_address), abi=CREDIT_ABI)

    with SessionLocal() as db:
        if db.scalar(select(Listing).where(Listing.status == ListingStatus.OPEN).limit(1)):
            raise SystemExit("Cancel every legacy open listing before migration")
        users = {user.id: user for user in db.scalars(select(User))}
        transfers: list[tuple[str, str, str, dict]] = []
        required_by_batch: dict[int, int] = defaultdict(int)

        for project in db.scalars(select(Project).where(Project.status == ProjectStatus.APPROVED)):
            owner = users[project.owner_id]
            if not owner.wallet_address:
                raise SystemExit(f"User {owner.email} must link a wallet before project {project.id} can migrate")
            token_id = projects_contract.functions.tokenByExternalProjectId(project.id).call()
            if not token_id:
                raise SystemExit(f"Project {project.id} is not confirmed on chain")
            project.chain_token_id = token_id
            current_owner = Web3.to_checksum_address(projects_contract.functions.ownerOf(token_id).call())
            recipient = Web3.to_checksum_address(owner.wallet_address)
            if current_owner == operator and recipient != operator:
                transfers.append(("project.transfer", "project", project.id, {"token_id": token_id, "recipient": recipient}))
            elif current_owner != recipient:
                raise SystemExit(f"Project token {token_id} is owned by unexpected address {current_owner}")

        for holding in db.scalars(select(Holding).where(Holding.quantity > 0)):
            if holding.locked_quantity:
                raise SystemExit(f"Holding {holding.id} is still locked by a legacy listing")
            owner = users[holding.user_id]
            if not owner.wallet_address:
                raise SystemExit(f"User {owner.email} must link a wallet before holding {holding.id} can migrate")
            batch = db.get(CreditBatch, holding.batch_id)
            token_id = credits_contract.functions.batchByVerificationHash(Web3.keccak(text=batch.id)).call()
            if not token_id:
                raise SystemExit(f"Batch {batch.id} is not confirmed on chain")
            batch.chain_batch_id = token_id
            recipient = Web3.to_checksum_address(owner.wallet_address)
            amount = int(Decimal(holding.quantity) * SCALE)
            if recipient != operator:
                required_by_batch[token_id] += amount
                transfers.append(("credit.transfer", "holding", holding.id, {"token_id": token_id, "recipient": recipient, "quantity": str(holding.quantity)}))

        for token_id, required in required_by_batch.items():
            available = credits_contract.functions.balanceOf(operator, token_id).call()
            if available < required:
                raise SystemExit(f"Operator balance for batch {token_id} is {available}, but migration requires {required}")

        print(f"Preflight passed: {len(transfers)} signed transfer(s) will be queued")
        if not args.execute:
            db.rollback()
            print("Dry run only; rerun with --execute to persist the outbox operations")
            return
        for operation_type, resource_type, resource_id, payload in transfers:
            existing = db.scalar(select(ChainOperation).where(ChainOperation.operation_type == operation_type, ChainOperation.resource_id == resource_id))
            if not existing:
                db.add(ChainOperation(operation_type=operation_type, resource_type=resource_type, resource_id=resource_id,
                    chain_id=settings.blockchain_chain_id,
                    contract_address=settings.carbon_project_contract_address if operation_type == "project.transfer" else settings.carbon_credit_contract_address,
                    payload=payload))
        db.commit()
        print("Migration operations queued; monitor the chain worker until all are confirmed")


if __name__ == "__main__":
    main()
