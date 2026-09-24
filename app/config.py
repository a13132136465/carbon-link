from functools import lru_cache
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    environment: str = "development"
    database_url: str = "sqlite:///./carbon_link.db"
    jwt_secret: str = "local-development-secret-change-this"
    access_token_minutes: int = 30
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None
    log_level: str = "INFO"
    blockchain_enabled: bool = False
    blockchain_rpc_url: str | None = None
    blockchain_chain_id: int = 43113
    blockchain_name: str = "avalanche-fuji"
    blockchain_confirmations: int = 3
    blockchain_request_timeout_seconds: int = 30
    carbon_project_contract_address: str | None = None
    carbon_credit_contract_address: str | None = None
    blockchain_operator_address: str | None = None
    blockchain_operator_private_key: str | None = None
    blockchain_signer_url: str | None = None

    @field_validator("jwt_secret")
    @classmethod
    def secure_secret(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("JWT_SECRET must contain at least 32 characters")
        return value

    @model_validator(mode="after")
    def validate_blockchain(self):
        if self.environment == "production":
            if self.jwt_secret == "local-development-secret-change-this":
                raise ValueError("Production requires a non-default JWT_SECRET")
            if self.bootstrap_admin_password == "ChangeMe123!":
                raise ValueError("Production requires a non-default BOOTSTRAP_ADMIN_PASSWORD")
            if "carbon-dev" in self.database_url or "change-me" in self.database_url:
                raise ValueError("Production requires a non-default database password")
        if not self.blockchain_enabled:
            return self
        required = {
            "BLOCKCHAIN_RPC_URL": self.blockchain_rpc_url,
            "CARBON_PROJECT_CONTRACT_ADDRESS": self.carbon_project_contract_address,
            "CARBON_CREDIT_CONTRACT_ADDRESS": self.carbon_credit_contract_address,
            "BLOCKCHAIN_OPERATOR_ADDRESS": self.blockchain_operator_address,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"Blockchain is enabled but configuration is missing: {', '.join(missing)}")
        if not self.blockchain_operator_private_key and not self.blockchain_signer_url:
            raise ValueError("Configure BLOCKCHAIN_OPERATOR_PRIVATE_KEY or BLOCKCHAIN_SIGNER_URL when blockchain is enabled")
        return self

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
