FOUNDRY_IMAGE ?= ghcr.io/foundry-rs/foundry:v1.7.1

.PHONY: install build test fmt snapshot
install:
	forge install OpenZeppelin/openzeppelin-contracts@v5.7.0 foundry-rs/forge-std@v1.10.0 --no-git
build:
	forge build --sizes
test:
	forge test -vvv
fmt:
	forge fmt --check
snapshot:
	forge snapshot
