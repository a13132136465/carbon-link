import json
import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.request import Request, urlopen

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session
from web3 import HTTPProvider, Web3
from web3.exceptions import TransactionNotFound, Web3RPCError

from app.config import settings
from app.database import engine
from app.models import ChainOperation, CreditBatch, Project

logger = logging.getLogger("carbonlink.chain_worker")
SCALE = Decimal("10000")

PROJECT_ABI = [{
    "type": "function", "name": "registerProject", "stateMutability": "nonpayable",
    "inputs": [{"name":"owner","type":"address"},{"name":"externalProjectId","type":"string"},{"name":"metadataDigest","type":"bytes32"},{"name":"metadataURI","type":"string"}],
    "outputs": [{"name":"tokenId","type":"uint256"}],
}, {
    "type":"function", "name":"tokenByExternalProjectId", "stateMutability":"view",
    "inputs":[{"name":"externalProjectId","type":"string"}], "outputs":[{"name":"","type":"uint256"}],
}, {
    "type":"function", "name":"ownerOf", "stateMutability":"view",
    "inputs":[{"name":"tokenId","type":"uint256"}], "outputs":[{"name":"","type":"address"}],
}, {
    "type":"function", "name":"safeTransferFrom", "stateMutability":"nonpayable",
    "inputs":[{"name":"from","type":"address"},{"name":"to","type":"address"},{"name":"tokenId","type":"uint256"}], "outputs":[],
}]

CREDIT_ABI = [{
    "type":"function", "name":"issueBatch", "stateMutability":"nonpayable",
    "inputs":[{"name":"recipient","type":"address"},{"name":"projectTokenId","type":"uint256"},{"name":"verificationHash","type":"bytes32"},{"name":"vintage","type":"uint64"},{"name":"amount","type":"uint256"},{"name":"metadataDigest","type":"bytes32"},{"name":"metadataURI","type":"string"}],
    "outputs":[{"name":"batchId","type":"uint256"}],
}, {
    "type":"function", "name":"retire", "stateMutability":"nonpayable",
    "inputs":[{"name":"batchId","type":"uint256"},{"name":"amount","type":"uint256"},{"name":"beneficiaryHash","type":"bytes32"},{"name":"evidenceDigest","type":"bytes32"}],
    "outputs":[{"name":"retirementId","type":"uint256"}],
}, {
    "type":"function", "name":"batchByVerificationHash", "stateMutability":"view",
    "inputs":[{"name":"verificationHash","type":"bytes32"}], "outputs":[{"name":"","type":"uint256"}],
}, {
    "type":"function", "name":"balanceOf", "stateMutability":"view",
    "inputs":[{"name":"account","type":"address"},{"name":"id","type":"uint256"}], "outputs":[{"name":"","type":"uint256"}],
}, {
    "type":"function", "name":"safeTransferFrom", "stateMutability":"nonpayable",
    "inputs":[{"name":"from","type":"address"},{"name":"to","type":"address"},{"name":"id","type":"uint256"},{"name":"amount","type":"uint256"},{"name":"data","type":"bytes"}], "outputs":[],
}]

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class ChainWorker:
    def __init__(self) -> None:
        if engine.dialect.name != "postgresql":
            raise RuntimeError("The signing worker requires PostgreSQL account locks")
        if not settings.blockchain_rpc_url:
            raise RuntimeError("BLOCKCHAIN_RPC_URL is required")
        self.w3 = Web3(HTTPProvider(settings.blockchain_rpc_url, request_kwargs={"timeout": settings.blockchain_request_timeout_seconds}))
        self.operator = Web3.to_checksum_address(settings.blockchain_operator_address)
        self.projects = self.w3.eth.contract(address=Web3.to_checksum_address(settings.carbon_project_contract_address), abi=PROJECT_ABI)
        self.credits = self.w3.eth.contract(address=Web3.to_checksum_address(settings.carbon_credit_contract_address), abi=CREDIT_ABI)

    def _digest(self, value: object) -> bytes:
        return Web3.keccak(text=json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))

    def _function(self, operation: ChainOperation):
        p = operation.payload
        if operation.operation_type == "project.register":
            return self.projects.functions.registerProject(
                Web3.to_checksum_address(p["owner_wallet"]), p["project_id"], self._digest(p), f"carbonlink://project/{p['project_id']}"
            )
        if operation.operation_type == "credit.issue":
            project_token_id = self.projects.functions.tokenByExternalProjectId(p["project_id"]).call()
            if not project_token_id:
                raise RuntimeError("project is not confirmed on chain yet")
            verification_hash = Web3.keccak(text=p["batch_id"])
            return self.credits.functions.issueBatch(
                Web3.to_checksum_address(p["recipient"]), project_token_id, verification_hash, int(p["vintage"]),
                int(Decimal(p["quantity"]) * SCALE), self._digest(p), f"carbonlink://batch/{p['batch_id']}"
            )
        if operation.operation_type == "project.transfer":
            return self.projects.functions.safeTransferFrom(
                self.operator, Web3.to_checksum_address(p["recipient"]), int(p["token_id"])
            )
        if operation.operation_type == "credit.transfer":
            return self.credits.functions.safeTransferFrom(
                self.operator, Web3.to_checksum_address(p["recipient"]), int(p["token_id"]),
                int(Decimal(p["quantity"]) * SCALE), b""
            )
        raise RuntimeError(f"unsupported chain operation: {operation.operation_type}")

    def _external_sign(self, transaction: dict) -> str:
        serializable = {key: (hex(value) if isinstance(value, int) and key in {"data"} else value) for key, value in transaction.items()}
        request = Request(settings.blockchain_signer_url, data=json.dumps({"transaction": serializable}).encode(), headers={"Content-Type":"application/json"}, method="POST")
        with urlopen(request, timeout=settings.blockchain_request_timeout_seconds) as response:
            result = json.loads(response.read())
        raw = result.get("raw_transaction")
        if not raw:
            raise RuntimeError("external signer did not return raw_transaction")
        return raw

    def prepare(self, operation: ChainOperation, db: Session) -> None:
        # Caller holds the account advisory lock across prepare/commit/broadcast.
        reserved = db.scalar(select(func.max(ChainOperation.nonce)).where(
            ChainOperation.chain_id == settings.blockchain_chain_id,
            or_(ChainOperation.signer_address == self.operator, ChainOperation.signer_address.is_(None)),
            ChainOperation.raw_transaction.is_not(None),
        ))
        nonce = max(self.w3.eth.get_transaction_count(self.operator, "pending"), (reserved + 1) if reserved is not None else 0)
        transaction = self._function(operation).build_transaction({
            "from": self.operator,
            "nonce": nonce,
            "chainId": settings.blockchain_chain_id,
            "gasPrice": self.w3.eth.gas_price,
        })
        if settings.blockchain_signer_url:
            raw = self._external_sign(transaction)
            tx_hash = Web3.to_hex(Web3.keccak(hexstr=raw))
        else:
            signed = self.w3.eth.account.sign_transaction(transaction, settings.blockchain_operator_private_key)
            raw = Web3.to_hex(signed.raw_transaction)
            tx_hash = Web3.to_hex(signed.hash)
        operation.signer_address = self.operator
        operation.nonce = nonce
        operation.raw_transaction = raw
        operation.transaction_hash = tx_hash
        operation.status = "prepared"
        operation.error_message = None

    def broadcast(self, operation: ChainOperation) -> None:
        try:
            tx_hash = self.w3.eth.send_raw_transaction(operation.raw_transaction)
            operation.transaction_hash = Web3.to_hex(tx_hash)
        except (ValueError, Web3RPCError) as exc:
            message = str(exc).lower()
            if not any(marker in message for marker in ("already known", "known transaction")):
                raise
        operation.status = "submitted"
        operation.submitted_at = operation.submitted_at or utcnow()
        operation.error_message = None

    def confirm(self, db, operation: ChainOperation) -> None:
        try:
            receipt = self.w3.eth.get_transaction_receipt(operation.transaction_hash)
        except TransactionNotFound:
            submitted_at = operation.submitted_at
            if submitted_at and submitted_at.tzinfo is None:
                submitted_at = submitted_at.replace(tzinfo=timezone.utc)
            if submitted_at and utcnow() - submitted_at > timedelta(seconds=60):
                # Re-send exactly the persisted transaction; never sign a replacement here.
                self.broadcast(operation)
                if utcnow() - submitted_at > timedelta(seconds=settings.blockchain_transaction_timeout_seconds):
                    operation.error_message = "Confirmation timeout; inspect the transaction and signer nonce before recovery"
            return
        if receipt.status != 1:
            operation.status = "failed"
            operation.error_message = "transaction reverted"
            operation.block_number = receipt.blockNumber
            return
        confirmations = self.w3.eth.block_number - receipt.blockNumber + 1
        if confirmations < settings.blockchain_confirmations:
            started = operation.submitted_at
            if started and started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            if started and utcnow() - started > timedelta(seconds=settings.blockchain_transaction_timeout_seconds):
                operation.error_message = "Confirmation timeout; waiting for finality"
        if confirmations >= settings.blockchain_confirmations:
            operation.error_message = None
            operation.status = "confirmed"
            operation.block_number = receipt.blockNumber
            operation.confirmed_at = utcnow()
            if operation.operation_type == "project.register":
                project = self.w3.eth.contract(address=Web3.to_checksum_address(operation.contract_address), abi=PROJECT_ABI)
                token_id = project.functions.tokenByExternalProjectId(operation.payload["project_id"]).call()
                record = db.get(Project, operation.resource_id)
                if record: record.chain_token_id = token_id
            elif operation.operation_type == "credit.issue":
                batch_id = self.credits.functions.batchByVerificationHash(Web3.keccak(text=operation.payload["batch_id"])).call()
                record = db.get(CreditBatch, operation.resource_id)
                if record: record.chain_batch_id = batch_id

    def run_once(self) -> bool:
        # Session-level PostgreSQL lock survives the durable prepare commit.
        # A row lock alone cannot coordinate two different outbox operations.
        if engine.dialect.name != "postgresql":
            raise RuntimeError("The signing worker requires PostgreSQL account locks")
        identity = f"{settings.blockchain_chain_id}:{self.operator.lower()}".encode()
        lock_id = int.from_bytes(hashlib.sha256(identity).digest()[:8], "big", signed=True)
        with engine.connect() as connection:
            acquired = connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": lock_id})
            connection.commit()
            if not acquired:
                return False
            try:
                with Session(bind=connection, expire_on_commit=False) as db:
                    return self._run_locked(db)
            finally:
                connection.rollback()
                connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_id})
                connection.commit()

    def _failure(self, db, operation_id: str, error: Exception) -> None:
        db.rollback()
        operation = db.get(ChainOperation, operation_id)
        operation.attempts += 1
        operation.error_message = str(error)[:2000]
        operation.next_attempt_at = utcnow() + timedelta(seconds=min(300, 2 ** min(operation.attempts, 8)))
        if operation.status != "submitted" and operation.attempts >= settings.blockchain_worker_max_attempts:
            # Signed transactions may still land. Retain their nonce and require
            # reconciliation instead of treating a broadcast timeout as failure.
            operation.status = "needs_attention" if operation.raw_transaction else "failed"
        db.commit()
        logger.warning("Chain operation %s deferred (%s)", operation_id, type(error).__name__)

    def _run_locked(self, db: Session) -> bool:
        scope = (ChainOperation.chain_id == settings.blockchain_chain_id,
                 or_(ChainOperation.signer_address == self.operator, ChainOperation.signer_address.is_(None)))
        due = or_(ChainOperation.next_attempt_at.is_(None), ChainOperation.next_attempt_at <= utcnow())
        submitted = db.scalar(select(ChainOperation).where(*scope, ChainOperation.status.in_(("submitted", "needs_attention")), due)
                              .order_by(ChainOperation.next_attempt_at.asc().nullsfirst(), ChainOperation.created_at).limit(1))
        worked = submitted is not None
        if submitted:
            operation_id = submitted.id
            try:
                self.confirm(db, submitted)
                if submitted.status in ("submitted", "needs_attention"):
                    submitted.next_attempt_at = utcnow() + timedelta(seconds=settings.blockchain_worker_poll_seconds)
                db.commit()
            except Exception as exc:
                self._failure(db, operation_id, exc)
        # Check confirmations and new work in the same tick; a slow receipt does
        # not starve unrelated tasks. Unbroadcast signed work must be resolved first.
        blocked = db.scalar(select(ChainOperation).where(*scope,
            ChainOperation.raw_transaction.is_not(None),
            ChainOperation.status.in_(("prepared", "needs_attention"))).order_by(ChainOperation.nonce).limit(1))
        if blocked:
            next_at = blocked.next_attempt_at
            if next_at and next_at.tzinfo is None:
                next_at = next_at.replace(tzinfo=timezone.utc)
            if blocked.status == "needs_attention" or (next_at and next_at > utcnow()):
                return worked
            operation = blocked
        else:
            operation = db.scalar(select(ChainOperation).where(*scope, ChainOperation.status == "pending", due)
                                  .order_by(ChainOperation.created_at).limit(1))
        if not operation:
            return worked
        operation_id = operation.id
        try:
            if operation.status == "pending":
                self.prepare(operation, db)
                db.commit()
            operation.attempts += 1
            self.broadcast(operation)
            db.commit()
        except Exception as exc:
            self._failure(db, operation_id, exc)
        return True


def main() -> None:
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if not settings.blockchain_enabled:
        logger.info("blockchain worker is disabled")
        while True:
            time.sleep(3600)
    worker = ChainWorker()
    logger.info("chain worker started for %s (%s)", settings.blockchain_name, settings.blockchain_chain_id)
    while True:
        try:
            worked = worker.run_once()
        except Exception:
            logger.exception("Worker infrastructure failure; retrying")
            worked = False
        time.sleep(0.5 if worked else settings.blockchain_worker_poll_seconds)

if __name__ == "__main__":
    main()
