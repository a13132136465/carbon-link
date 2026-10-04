# CarbonLink smart contracts

The on-chain layer contains three non-upgradeable contracts:

- `CarbonProjectRegistry`: ERC-721 registry for verified projects.
- `CarbonCreditLedger`: ERC-1155 issuance, transfer, batch freeze and permanent retirement.
- `CarbonMarketplace`: one shared `CARBON/USDC` order book; bids accept any issued batch while asks escrow their actual ERC-1155 delivery batch.
- `TestUSDC`: owner-mintable six-decimal `tUSDC` for local chains and public testnets only.

The governed contracts use delayed two-step default-admin transfer, separate operational roles and an emergency pause. They are deliberately non-upgradeable: a replacement requires a new deployment and an explicitly governed migration, avoiding hidden proxy-admin authority. The marketplace has no platform withdrawal or operator trading function.

## Reproducible Docker workflow

```text
docker run --rm --entrypoint forge -v ${PWD}:/work -w /work/contracts \
  ghcr.io/foundry-rs/foundry:v1.7.1 install \
  OpenZeppelin/openzeppelin-contracts@v5.7.0 foundry-rs/forge-std@v1.10.0 --no-git
docker compose -f compose.contracts.yaml --profile tools run --rm contracts
```

Do not commit a private key. For Fuji deployment, populate `contracts/.env` from `.env.example`, then run the deployment script with `forge script` and `--broadcast`. The production administrator should be a multisig, while the API operator receives only registrar and issuer roles.

Deploy test USDC first on a local chain or Fuji. Set `TEST_USDC_OWNER_ADDRESS` to the address that will distribute test balances:

```text
forge script script/DeployTestUSDC.s.sol:DeployTestUSDC --rpc-url fuji --broadcast
```

Copy the deployed `TestUSDC` address into `USDC_CONTRACT_ADDRESS`, then deploy `CarbonMarketplace`. The token symbol is intentionally `tUSDC`; never use this contract on a production network.

Example deployment command from the repository root:

```text
docker run --rm --entrypoint forge --env-file contracts/.env \
  -v ${PWD}:/work -w /work/contracts ghcr.io/foundry-rs/foundry:v1.7.1 \
  script script/DeployCarbonLink.s.sol:DeployCarbonLink \
  --rpc-url fuji --broadcast --verify
```

For an existing CarbonLink deployment, set `CARBON_CREDIT_CONTRACT_ADDRESS` and `USDC_CONTRACT_ADDRESS`, then deploy only the marketplace so the registry and issued batch IDs remain unchanged:

```text
forge script script/DeployMarketplace.s.sol:DeployMarketplace --rpc-url fuji --broadcast
```

## Roles

- Default admin: grants/revokes roles and uses delayed two-step transfer.
- Registrar: registers projects and updates project metadata.
- Issuer: issues a credit batch after verification.
- Verifier: changes project status, freezes batches and updates batch metadata.
- Pauser: activates and releases the emergency stop.

Metadata and evidence are addressed by URI while their digests are committed on chain. Beneficiaries are represented by a hash in the retirement record to avoid placing personal or commercially sensitive data directly on a public chain.


## 治理与结算边界

- 撤销项目阻止后续发行；已发行批次的可交易性由批次冻结和额度合约暂停独立控制，不自动追溯失效。
- 买单按基础单位向下取整，最后一次完全成交支付剩余托管 USDC；分笔实际单价可能有微小舍入差异，但总支付不超过原托管额。
- 市场暂停允许撤单；额度合约暂停或批次冻结时，卖单返还也被底层转账限制，必须先完成治理解锁。
这些既有规则有回归测试覆盖；本次修复不改变已部署合约的资产规则，也不需要重新部署合约。
