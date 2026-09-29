import json
import logging
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.request import Request, urlopen

from sqlalchemy import or_, select
from web3 import HTTPProvider, Web3
from web3.exceptions import TransactionNotFound

from app.config import settings
from app.database import SessionLocal
from app.models import ChainOperation

logger = logging.getLogger("carbonlink.chain_worker")
SCALE = Decimal("10000")

PROJECT_ABI = [{
    "type": "function", "name": "registerProject", "stateMutability": "nonpayable",
    "inputs": [{"name":"owner","type":"address"},{"name":"externalProjectId","type":"string"},{"name":"metadataDigest","type":"bytes32"},{"name":"metadataURI","type":"string"}],
    "outputs": [{"name":"tokenId","type":"uint256"}],
}, {
    "type":"function", "name":"tokenByExternalProjectId", "stateMutability":"view",
    "inputs":[{"name":"externalProjectId","type":"string"}], "outputs":[{"name":"","type":"uint256"}],
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
}]

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class ChainWorker:
    def __init__(self) -> None:
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
                self.operator, p["project_id"], self._digest(p), f"carbonlink://project/{p['project_id']}"
            )
        if operation.operation_type == "credit.issue":
            project_token_id = self.projects.functions.tokenByExternalProjectId(p["project_id"]).call()
            if not project_token_id:
                raise RuntimeError("project is not confirmed on chain yet")
            verification_hash = Web3.keccak(text=p["batch_id"])
            return self.credits.functions.issueBatch(
                self.operator, project_token_id, verification_hash, int(p["vintage"]),
                int(Decimal(p["quantity"]) * SCALE), self._digest(p), f"carbonlink://batch/{p['batch_id']}"
            )
        if operation.operation_type == "credit.retire":
            batch_id = self.credits.functions.batchByVerificationHash(Web3.keccak(text=p["batch_id"])).call()
            if not batch_id:
                raise RuntimeError("credit batch is not confirmed on chain yet")
            return self.credits.functions.retire(
                batch_id, int(Decimal(p["quantity"]) * SCALE), Web3.keccak(text=p["beneficiary"]), self._digest(p)
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

    def prepare(self, operation: ChainOperation) -> None:
        nonce = self.w3.eth.get_transaction_count(self.operator, "pending")
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
        operation.nonce = nonce
        operation.raw_transaction = raw
        operation.transaction_hash = tx_hash
        operation.status = "prepared"
        operation.error_message = None

    def broadcast(self, operation: ChainOperation) -> None:
        try:
            tx_hash = self.w3.eth.send_raw_transaction(operation.raw_transaction)
            operation.transaction_hash = Web3.to_hex(tx_hash)
        except ValueError as exc:
            message = str(exc).lower()
            if not any(marker in message for marker in ("already known", "known transaction")):
                raise
        operation.status = "submitted"
        operation.submitted_at = utcnow()
        operation.error_message = None

    def confirm(self, operation: ChainOperation) -> None:
        try:
            receipt = self.w3.eth.get_transaction_receipt(operation.transaction_hash)
        except TransactionNotFound:
            submitted_at = operation.submitted_at
            if submitted_at and submitted_at.tzinfo is None:
                submitted_at = submitted_at.replace(tzinfo=timezone.utc)
            if submitted_at and utcnow() - submitted_at > timedelta(seconds=60):
                operation.status = "prepared"
                operation.next_attempt_at = utcnow()
            return
        if receipt.status != 1:
            operation.status = "failed"
            operation.error_message = "transaction reverted"
            operation.block_number = receipt.blockNumber
            return
        confirmations = self.w3.eth.block_number - receipt.blockNumber + 1
        if confirmations >= settings.blockchain_confirmations:
            operation.status = "confirmed"
            operation.block_number = receipt.blockNumber
            operation.confirmed_at = utcnow()

    def run_once(self) -> bool:
        with SessionLocal() as db:
            submitted = db.scalar(select(ChainOperation).where(ChainOperation.status == "submitted").order_by(ChainOperation.submitted_at).limit(1))
            if submitted:
                self.confirm(submitted)
                db.commit()
                return True
            operation = db.scalar(select(ChainOperation).where(
                ChainOperation.status.in_(("pending", "prepared")),
                or_(ChainOperation.next_attempt_at.is_(None), ChainOperation.next_attempt_at <= utcnow()),
            ).order_by(ChainOperation.created_at).with_for_update(skip_locked=True).limit(1))
            if not operation:
                return False
            try:
                operation.attempts += 1
                if operation.status == "pending":
                    self.prepare(operation)
                    db.commit()
                self.broadcast(operation)
                db.commit()
            except Exception as exc:
                attempts = operation.attempts
                operation_id = operation.id
                db.rollback()
                operation = db.get(ChainOperation, operation_id)
                operation.attempts = attempts
                operation.error_message = str(exc)[:2000]
                if operation.attempts >= settings.blockchain_worker_max_attempts:
                    operation.status = "failed"
                else:
                    operation.next_attempt_at = utcnow() + timedelta(seconds=min(300, 2 ** min(operation.attempts, 8)))
                db.commit()
                logger.exception("chain operation %s failed", operation.id)
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
        worked = worker.run_once()
        time.sleep(0.5 if worked else settings.blockchain_worker_poll_seconds)

if __name__ == "__main__":
    main()
