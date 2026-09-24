# CarbonLink smart contracts

The on-chain layer contains two non-upgradeable contracts:

- `CarbonProjectRegistry`: ERC-721 registry for verified projects.
- `CarbonCreditLedger`: ERC-1155 issuance, transfer, batch freeze and permanent retirement.

Both contracts use delayed two-step default-admin transfer, separate operational roles and an emergency pause. They are deliberately non-upgradeable: a replacement requires a new deployment and an explicitly governed migration, avoiding hidden proxy-admin authority.

## Reproducible Docker workflow

```text
docker run --rm --entrypoint forge -v ${PWD}:/work -w /work/contracts \
  ghcr.io/foundry-rs/foundry:v1.7.1 install \
  OpenZeppelin/openzeppelin-contracts@v5.7.0 foundry-rs/forge-std@v1.10.0 --no-git
docker compose -f compose.contracts.yaml --profile tools run --rm contracts
```

Do not commit a private key. For Fuji deployment, populate `contracts/.env` from `.env.example`, then run the deployment script with `forge script` and `--broadcast`. The production administrator should be a multisig, while the API operator receives only registrar and issuer roles.

Example deployment command from the repository root:

```text
docker run --rm --entrypoint forge --env-file contracts/.env \
  -v ${PWD}:/work -w /work/contracts ghcr.io/foundry-rs/foundry:v1.7.1 \
  script script/DeployCarbonLink.s.sol:DeployCarbonLink \
  --rpc-url fuji --broadcast --verify
```

## Roles

- Default admin: grants/revokes roles and uses delayed two-step transfer.
- Registrar: registers projects and updates project metadata.
- Issuer: issues a credit batch after verification.
- Verifier: changes project status, freezes batches and updates batch metadata.
- Pauser: activates and releases the emergency stop.

Metadata and evidence are addressed by URI while their digests are committed on chain. Beneficiaries are represented by a hash in the retirement record to avoid placing personal or commercially sensitive data directly on a public chain.
