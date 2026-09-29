# CarbonLink 碳积分管理与交易平台

CarbonLink 是从 `carbin-ai` 教学原型演进而来的自托管碳资产系统，覆盖碳项目申报与审核、链上项目登记、额度发行、去中心化交易、持有人签名注销与公开证书。平台负责材料和审批，用户通过自己的 EVM 钱包持有并处分资产；链上状态是资产余额与交易结算的事实来源。

## 已实现能力

- JWT 登录、Argon2 密码哈希、管理员/核证员/成员三级权限。
- 碳项目申报、提交、核证通过或驳回，以及完整审计事件。
- 用户使用签名挑战绑定自托管 EVM 地址，平台不生成或保存用户私钥。
- 项目核证后，项目 NFT 和 ERC-1155 碳额度直接登记或发行到项目方钱包。
- 去中心化市场支持用户签名授权、挂单、部分购买和撤单；碳额度与网络原生代币在同一笔交易中原子结算。
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

从旧托管版本升级时，先让所有资产用户完成钱包绑定并撤销旧数据库挂单，再运行 `python -m app.self_custody_migration` 做只读预检；确认输出后运行 `python -m app.self_custody_migration --execute`。该命令只写入可重试的 Outbox，由现有签名 Worker 把旧平台总钱包中的项目 NFT 和额度逐项转给用户钱包。

也可完全在 Docker 中运行测试：

```text
docker build --target test -t carbon-link-test .
docker run --rm carbon-link-test
```

## 业务边界

平台数据库保存身份、材料、审批和可检索的证书数据，不再作为资产余额或成交结算的权威账本。市场合约托管卖方主动挂出的数量；买方交易同时完成 ERC-1155 交割和网络原生代币付款。当前合约不处理法币或稳定币，若需要稳定计价，应另行接入经过审计的 ERC-20 结算资产。

## 区块链配置

区块链功能默认关闭，因此不配置 RPC 也不会影响登记和交易主流程。配置项位于 `.env.example`，Compose 会将它们传入 API：

- `BLOCKCHAIN_ENABLED`：是否启用 EVM 链上适配器。
- `BLOCKCHAIN_RPC_URL`、`BLOCKCHAIN_CHAIN_ID`、`BLOCKCHAIN_NAME`：网络连接信息，默认网络参数为 Avalanche Fuji（43113）。
- `CARBON_PROJECT_CONTRACT_ADDRESS`、`CARBON_CREDIT_CONTRACT_ADDRESS`、`CARBON_MARKETPLACE_CONTRACT_ADDRESS`：项目 NFT、碳积分和去中心化市场合约地址。
- `BLOCKCHAIN_OPERATOR_ADDRESS`：链上操作账户。
- `BLOCKCHAIN_SIGNER_URL`：推荐的生产签名服务地址；或者在本地测试中使用 `BLOCKCHAIN_OPERATOR_PRIVATE_KEY`，两者至少配置一个。
- `BLOCKCHAIN_CONFIRMATIONS`、`BLOCKCHAIN_REQUEST_TIMEOUT_SECONDS`：确认数与 RPC 超时。

当 `BLOCKCHAIN_ENABLED=true` 时，应用启动阶段会检查必需配置，缺失时直接拒绝启动。管理员可通过 `GET /api/v1/system/blockchain` 查看脱敏后的生效配置和签名模式；接口永远不会返回私钥。

项目核证通过和积分发行会写入 `chain_operations` Outbox，由具备最小 Registrar/Issuer 权限的平台操作账户执行；接收方始终是项目方已验证的钱包。挂单、购买、撤单和注销则只能由用户钱包签名，平台没有代签路径。

`chain-worker` 服务消费审批与发行 Outbox，并回填交易哈希、区块号及链上 token ID。用户余额从合约读取；注销证书只在服务端核验成功回执、签名地址、批次、数量与受益方哈希后生成。链上额度采用 4 位精度基础单位，即 `1 tCO₂e = 10,000` 个合约单位。

生产化 Solidity 合约位于 `contracts/`：

- `CarbonProjectRegistry.sol`：ERC-721 项目登记、状态管理、元数据承诺和紧急暂停。
- `CarbonCreditLedger.sol`：ERC-1155 批次发行、转移、冻结和永久注销。
- `CarbonMarketplace.sol`：用户签名挂单、合约托管和原生代币原子结算。
- `DeployCarbonLink.s.sol`：角色分离的部署脚本。
- `DeployMarketplace.s.sol`：为已有项目/额度合约单独部署市场的滚动升级脚本。
- `CarbonLink.t.sol`：权限、安全状态、发行、转移、注销及模糊测试。

运行合约测试：`docker compose -f compose.contracts.yaml --profile tools run --rm contracts`。

## 主要接口

- `POST /api/v1/auth/register`、`POST /api/v1/auth/login`
- `POST /api/v1/projects`、`POST /api/v1/projects/{id}/submit`、`POST /api/v1/projects/{id}/review`
- `POST /api/v1/credits/issue`、`GET /api/v1/wallet/holdings`
- `POST /api/v1/wallet/challenge`、`POST /api/v1/wallet/link`、`GET /api/v1/chain/config`
- 市场写操作直接调用 `CarbonMarketplace` 合约；中心化成交接口在链上模式下返回 `410`
- `POST /api/v1/retirements/confirm`、`GET /api/v1/retirements/{certificate_no}`
- `GET /api/v1/dashboard`

完整请求模型和响应示例以 OpenAPI 页面为准。

## 企业申报 Agent

企业用户可直接用自然语言描述项目，Agent 会结合当前草稿和最近对话，提取名称、归类项目类型、整理地区及项目说明，并将明确的减排量单位换算为 tCO₂e。用户可用自然语言更正或撤回已填内容。系统先校验表单，再由模型针对缺项生成追问；不会自动猜测方法学或缺失数值。信息齐全后，由用户确认创建档案。

配置 `LLM_API_KEY`、`LLM_BASE_URL` 和 `LLM_MODEL` 后即可使用当前的 OpenAI 兼容模型服务（包括兼容 JSON 模式的 DeepSeek 服务）。API 使用 OpenAI SDK 直接调用模型，不再依赖 LangChain 的导入是否成功。Compose 已传入这三个变量；更新容器部署时需重新构建 API 和前端。模型不可用时会明确提示，并保留草稿、提供辅助表单入口。

对话历史与未保存草稿目前保存在当前页面内存中；刷新页面会丢失，已确认创建的项目仍保存在数据库。现有项目问答使用服务端读取的项目资料、材料文件名和审核反馈，不读取附件正文。
