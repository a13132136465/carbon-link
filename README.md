# CarbonLink 碳积分管理与交易平台

CarbonLink 是从 `carbin-ai` 教学原型演进而来的可部署业务系统，覆盖碳项目登记、核证、积分发行、托管余额、市场交易、注销与公开证书。系统以数据库不可变流水为事实依据，链上存证可作为后续适配器接入，而不会阻塞核心业务。

## 已实现能力

- JWT 登录、Argon2 密码哈希、管理员/核证员/成员三级权限。
- 碳项目申报、提交、核证通过或驳回，以及完整审计事件。
- 按项目与年份发行唯一碳积分批次，数据库约束防止超发和负余额。
- 钱包可用余额与挂单锁定余额分离；成交在一个数据库事务中同步更新买卖双方、挂单、交易和双向流水。
- 市场限价挂单、部分成交、撤单、交易统计。
- 永久注销与公开查询的唯一注销证书。
- 关键发行、购买和注销接口要求 `Idempotency-Key`，防止客户端重试造成重复处理。
- PostgreSQL、Alembic 迁移、健康检查、非 root 容器、Docker Compose 和端到端测试。
- React + TypeScript 管理控制台，覆盖项目、资产、交易、注销、链上任务与审计日志，并由 Nginx 同域代理 API。
- 自助注册、管理员用户/角色管理、修改密码与邮件令牌找回密码。
- 项目草稿/驳回状态编辑删除、公开证书核验页和主要列表分页。
- 独立链上 Worker 自动签名、持久化原始交易、广播、确认和退避重试 Outbox 任务。

## 快速启动

1. 复制 `.env.example` 为 `.env`，至少修改数据库密码、`JWT_SECRET` 和初始管理员密码。
2. 启动：`docker compose up --build -d`。
3. 管理控制台：打开 `http://localhost:3000`。
4. 检查 API：打开 `http://localhost:8000/health/ready`；API 文档位于 `http://localhost:8000/docs`。

前端默认端口为 `3000`，可通过 `.env` 中的 `FRONTEND_PORT` 修改。浏览器请求同域 `/api`，由前端 Nginx 转发到 API 容器，无需为部署主机单独编译 API 地址。
如果宿主机的 `8000` 已被占用，可设置 `API_PORT=8001`；容器间通信仍使用固定的 `8000` 端口，不受影响。

默认 Compose 仅用于本机验收。公网部署时应由 TLS 反向代理暴露 API，不应暴露 PostgreSQL，并应把密码放入密钥管理服务。

## 本地开发与测试

```text
python -m venv .venv
.venv\Scripts\pip install -e ".[test]"
.venv\Scripts\pytest
```

数据库结构由 `alembic upgrade head` 创建。生产启动命令已自动执行迁移。

也可完全在 Docker 中运行测试：

```text
docker build --target test -t carbon-link-test .
docker run --rm carbon-link-test
```

## 业务边界

当前交易表示碳积分的原子交割和应付金额记录，不直接划转法币。接入支付机构时应采用“支付授权—积分交割—支付捕获”的 Saga，并通过支付回调幂等确认。链上模块建议采用异步 Outbox 写入交易哈希，数据库仍保留业务状态与审计事实，避免 RPC 故障破坏交易一致性。

## 区块链配置

区块链功能默认关闭，因此不配置 RPC 也不会影响登记和交易主流程。配置项位于 `.env.example`，Compose 会将它们传入 API：

- `BLOCKCHAIN_ENABLED`：是否启用 EVM 链上适配器。
- `BLOCKCHAIN_RPC_URL`、`BLOCKCHAIN_CHAIN_ID`、`BLOCKCHAIN_NAME`：网络连接信息，默认网络参数为 Avalanche Fuji（43113）。
- `CARBON_PROJECT_CONTRACT_ADDRESS`、`CARBON_CREDIT_CONTRACT_ADDRESS`：项目 NFT 和碳积分合约地址。
- `BLOCKCHAIN_OPERATOR_ADDRESS`：链上操作账户。
- `BLOCKCHAIN_SIGNER_URL`：推荐的生产签名服务地址；或者在本地测试中使用 `BLOCKCHAIN_OPERATOR_PRIVATE_KEY`，两者至少配置一个。
- `BLOCKCHAIN_CONFIRMATIONS`、`BLOCKCHAIN_REQUEST_TIMEOUT_SECONDS`：确认数与 RPC 超时。

当 `BLOCKCHAIN_ENABLED=true` 时，应用启动阶段会检查必需配置，缺失时直接拒绝启动。管理员可通过 `GET /api/v1/system/blockchain` 查看脱敏后的生效配置和签名模式；接口永远不会返回私钥。

项目核证通过、积分发行和积分注销会与业务数据在同一个数据库事务中写入 `chain_operations` Outbox。管理员可通过 `GET /api/v1/system/blockchain/operations` 查看待提交、已提交、已确认或失败的链上任务。链上执行器可以安全重试这些任务，而不会重复修改用户余额。

`chain-worker` 服务会消费异步 Outbox，自动调用已部署合约并回填交易哈希和区块号。数据库账本仍是交易事实源，避免 RPC 中断导致余额或成交状态不一致；不应把私钥提交到仓库，生产环境优先使用 Vault/KMS 或独立签名服务。链上额度采用 4 位精度基础单位，即 `1 tCO₂e = 10,000` 个合约单位。

生产化 Solidity 合约位于 `contracts/`：

- `CarbonProjectRegistry.sol`：ERC-721 项目登记、状态管理、元数据承诺和紧急暂停。
- `CarbonCreditLedger.sol`：ERC-1155 批次发行、转移、冻结和永久注销。
- `DeployCarbonLink.s.sol`：角色分离的部署脚本。
- `CarbonLink.t.sol`：权限、安全状态、发行、转移、注销及模糊测试。

运行合约测试：`docker compose -f compose.contracts.yaml --profile tools run --rm contracts`。

## 主要接口

- `POST /api/v1/auth/register`、`POST /api/v1/auth/login`
- `POST /api/v1/projects`、`POST /api/v1/projects/{id}/submit`、`POST /api/v1/projects/{id}/review`
- `POST /api/v1/credits/issue`、`GET /api/v1/wallet/holdings`
- `POST /api/v1/market/listings`、`POST /api/v1/market/listings/{id}/buy`、`DELETE /api/v1/market/listings/{id}`
- `POST /api/v1/retirements`、`GET /api/v1/retirements/{certificate_no}`
- `GET /api/v1/dashboard`

完整请求模型和响应示例以 OpenAPI 页面为准。

## 企业申报 Agent

企业用户可直接用自然语言描述项目，Agent 会结合当前草稿和最近对话，提取名称、归类项目类型、整理地区及项目说明，并将明确的减排量单位换算为 tCO₂e。用户可用自然语言更正或撤回已填内容。系统先校验表单，再由模型针对缺项生成追问；不会自动猜测方法学或缺失数值。信息齐全后，由用户确认创建档案。

配置 `LLM_API_KEY`、`LLM_BASE_URL` 和 `LLM_MODEL` 后即可使用当前的 OpenAI 兼容模型服务（包括兼容 JSON 模式的 DeepSeek 服务）。API 使用 OpenAI SDK 直接调用模型，不再依赖 LangChain 的导入是否成功。Compose 已传入这三个变量；更新容器部署时需重新构建 API 和前端。模型不可用时会明确提示，并保留草稿、提供辅助表单入口。

对话历史与未保存草稿目前保存在当前页面内存中；刷新页面会丢失，已确认创建的项目仍保存在数据库。现有项目问答使用服务端读取的项目资料、材料文件名和审核反馈，不读取附件正文。
