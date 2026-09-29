# Ubuntu 部署指南

本文采用混合部署：Solidity 合约在 Ubuntu 主机上使用原生 Foundry 编译、测试和部署；React 前端、API 与 PostgreSQL 使用 Docker Compose。先部署到 Avalanche Fuji 测试网，确认业务及链上数据无误并完成独立安全审计后，才考虑主网。

## 1. 主机准备

建议 Ubuntu 22.04/24.04 LTS，至少 2 vCPU、4 GB 内存和 30 GB 磁盘。仅对公网开放 SSH、HTTP 和 HTTPS。管理端与 API 在 Compose 中分别绑定 `127.0.0.1:3000`、`127.0.0.1:8000`，应通过 TLS 反向代理访问。

使用 Docker 官方 apt 仓库安装 Engine 和 Compose 插件：

```bash
sudo apt update
sudo apt install -y ca-certificates curl git jq
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

退出 SSH 后重新登录，使 `docker` 用户组生效。然后将当前项目上传或克隆到服务器，例如 `/opt/carbon-link`：

```bash
cd /opt/carbon-link
docker version
docker compose version
```

## 2. 在 Ubuntu 直接安装 Foundry

Foundry 只安装在 Ubuntu 主机，不放入业务容器：

```bash
curl -L https://foundry.paradigm.xyz | bash
source "$HOME/.bashrc"
foundryup --install v1.7.1

forge --version
cast --version
anvil --version
```

如果当前 shell 仍找不到命令，执行：

```bash
export PATH="$PATH:$HOME/.foundry/bin"
```

## 3. 准备三个链上身份

- `deployer`：只负责部署，Fuji 测试时需要少量 AVAX；部署完成后不持有合约角色。
- `admin`：建议使用多签地址，管理角色、暂停和核证权限。
- `operator`：后端热钱包，只拥有项目登记和积分发行权限。

不要把管理员多签和 operator 设置成同一地址。不要将私钥提交到 Git、镜像或 Compose 文件。

## 4. 在 Ubuntu 直接安装依赖并测试合约

`contracts/lib` 不提交到仓库，需要在服务器安装锁定版本：

```bash
cd /opt/carbon-link/contracts

forge install OpenZeppelin/openzeppelin-contracts@v5.7.0 --no-git
forge install foundry-rs/forge-std@v1.10.0 --no-git

forge fmt --check
forge build --sizes
forge test -vvv
```

必须看到 `9 passed; 0 failed` 后再继续。

## 5. 先在 Ubuntu 本地 Anvil 测试部署

打开第一个 SSH 终端运行本地测试链：

```bash
anvil --host 127.0.0.1 --port 8545
```

Anvil 会打印预充值测试账户、地址和私钥。保持它运行。打开第二个终端：

```bash
cd /opt/carbon-link/contracts

export DEPLOYER_PRIVATE_KEY=0xAnvil第1个账户私钥
export CONTRACT_ADMIN_ADDRESS=0xAnvil第2个账户地址
export BLOCKCHAIN_OPERATOR_ADDRESS=0xAnvil第3个账户地址
export ADMIN_TRANSFER_DELAY_SECONDS=60

forge script script/DeployCarbonLink.s.sol:DeployCarbonLink \
  --rpc-url http://127.0.0.1:8545 --broadcast -vvvv
```

本地部署记录应出现在：

```text
broadcast/DeployCarbonLink.s.sol/31337/run-latest.json
```

提取地址并检查字节码：

```bash
REGISTRY=$(jq -r '.transactions[] | select(.contractName == "CarbonProjectRegistry") | .contractAddress' \
  broadcast/DeployCarbonLink.s.sol/31337/run-latest.json)
CREDITS=$(jq -r '.transactions[] | select(.contractName == "CarbonCreditLedger") | .contractAddress' \
  broadcast/DeployCarbonLink.s.sol/31337/run-latest.json)

cast code "$REGISTRY" --rpc-url http://127.0.0.1:8545
cast code "$CREDITS" --rpc-url http://127.0.0.1:8545
cast call "$CREDITS" "projectRegistry()(address)" \
  --rpc-url http://127.0.0.1:8545
```

前两个命令应返回非 `0x` 字节码，最后一个地址必须等于 `$REGISTRY`。停止 Anvil 会清空这条本地测试链。

## 6. 配置 Fuji 部署

```bash
cd /opt/carbon-link/contracts
cp .env.example .env
chmod 600 .env
nano .env
```

填写：

```dotenv
AVALANCHE_FUJI_RPC_URL=https://api.avax-test.network/ext/bc/C/rpc
DEPLOYER_PRIVATE_KEY=0x部署账户私钥
CONTRACT_ADMIN_ADDRESS=0x管理员多签或测试管理员地址
BLOCKCHAIN_OPERATOR_ADDRESS=0x后端操作账户
ADMIN_TRANSFER_DELAY_SECONDS=172800
```

使用 deployer 的 C-Chain `0x...` 地址从 Avalanche 官方测试水龙头取得 Fuji AVAX。先查询余额：

```bash
set -a; source .env; set +a
DEPLOYER_ADDRESS=$(cast wallet address --private-key "$DEPLOYER_PRIVATE_KEY")
cast balance "$DEPLOYER_ADDRESS" --rpc-url "$AVALANCHE_FUJI_RPC_URL" --ether
```

实际支付部署 gas 的是 deployer，输出必须大于零。

## 7. 在 Ubuntu 直接模拟和广播 Fuji 部署

先模拟，不广播：

```bash
forge script script/DeployCarbonLink.s.sol:DeployCarbonLink \
  --rpc-url fuji -vvvv
```

模拟成功后广播：

```bash
forge script script/DeployCarbonLink.s.sol:DeployCarbonLink \
  --rpc-url fuji --broadcast -vvvv
```

部署记录位于：

```text
broadcast/DeployCarbonLink.s.sol/43113/run-latest.json
```

提取两个地址：

```bash
jq -r '.transactions[] | select(.contractName == "CarbonProjectRegistry") | .contractAddress' \
  broadcast/DeployCarbonLink.s.sol/43113/run-latest.json
jq -r '.transactions[] | select(.contractName == "CarbonCreditLedger") | .contractAddress' \
  broadcast/DeployCarbonLink.s.sol/43113/run-latest.json
```

将交易哈希和地址放到 Fuji Explorer 检查。不要只依赖终端输出。

## 8. 使用 Docker 部署其他服务

```bash
cd /opt/carbon-link
cp .env.example .env
chmod 600 .env
nano .env
```

至少设置以下值：

```dotenv
ENVIRONMENT=production
POSTGRES_PASSWORD=使用密码管理器生成的数据库密码
POSTGRES_DB=carbon_link_v2
JWT_SECRET=至少32字符的随机密钥
BOOTSTRAP_ADMIN_EMAIL=你的管理员邮箱
BOOTSTRAP_ADMIN_PASSWORD=强随机管理员密码
CORS_ORIGINS=["https://你的域名"]

BLOCKCHAIN_ENABLED=true
BLOCKCHAIN_NAME=avalanche-fuji
BLOCKCHAIN_RPC_URL=https://api.avax-test.network/ext/bc/C/rpc
BLOCKCHAIN_CHAIN_ID=43113
BLOCKCHAIN_CONFIRMATIONS=3
CARBON_PROJECT_CONTRACT_ADDRESS=0x项目合约地址
CARBON_CREDIT_CONTRACT_ADDRESS=0x积分合约地址
BLOCKCHAIN_OPERATOR_ADDRESS=0x后端操作账户
BLOCKCHAIN_OPERATOR_PRIVATE_KEY=0x后端操作账户私钥
```

生产环境应改用 `BLOCKCHAIN_SIGNER_URL` 对接 Vault/KMS/独立签名服务，并删除本地私钥配置。

启动并检查：

```bash
docker compose up -d --build
docker compose ps
curl --fail http://127.0.0.1:3000/health
curl --fail http://127.0.0.1:8000/health/ready
docker compose logs --tail=100 api
docker compose logs --tail=100 chain-worker
```

## 9. TLS 与防火墙

用宿主机 Nginx、Caddy 或云负载均衡器将 `https://你的域名` 反向代理到 `http://127.0.0.1:3000`。前端容器会把同域 `/api` 请求转发给 API 容器；不要把 PostgreSQL 或 8000 端口直接暴露到公网。Docker 发布端口可能绕过部分 UFW 规则，因此 Compose 已限定管理端与 API 只能从本机访问。

## 10. 备份与升级

升级前先备份数据库：

```bash
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
  > "carbon_link_$(date +%F_%H%M).dump"
```

升级：

```bash
docker compose pull
docker compose up -d --build
docker compose logs --tail=100 api
curl --fail http://127.0.0.1:3000/health
curl --fail http://127.0.0.1:8000/health/ready
```

数据库迁移由 API 启动命令中的 `alembic upgrade head` 自动执行。备份文件应复制到虚拟机之外并定期做恢复演练。

## 链上 Worker 验收

API 会将项目登记、额度签发和注销写入事务性 `chain_operations` Outbox，`chain-worker` 随 Compose 自动启动并负责签名、广播、确认数监听和失败退避重试。管理员可在控制台“链上存证”查看状态和交易哈希。上线前应确认操作账户具有项目合约 `REGISTRAR_ROLE`、额度合约 `ISSUER_ROLE`，并持有足够的原生代币支付 gas。生产环境优先配置 `BLOCKCHAIN_SIGNER_URL`，避免在 Compose 环境变量中保存私钥。
