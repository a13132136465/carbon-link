# CarbonLink 批量用户 Agent

这个工具用独立的 Chromium 浏览器上下文模拟多个企业用户。它通过页面完成注册、项目创建、材料上传和提交审核，并通过 API 校验最终结果。

## 安装

```powershell
cd user-agent
npm install
npm run install-browser
```

先按照项目根目录的说明启动 CarbonLink，确认 `http://localhost:3000` 可以访问。

## 运行

单个完整申报流程：

```powershell
npm run smoke
```

同时运行 5 个浏览器会话，共模拟 20 个用户：

```powershell
npm run agent -- --scenario application --count 20 --concurrency 5
```

每个 Agent 会生成相互匹配的企业和项目资料，包括不同的企业名称、地区、项目类型、方法学、减排量、项目说明及材料文件名。使用 `--seed` 可以复现同一组业务资料：

```powershell
npm run agent -- --scenario application --count 20 --concurrency 5 --seed acceptance-2026-09
```

同一个 seed 会产生相同的业务字段，但邮箱仍包含批次编号，以避免不同批次注册冲突。报告会保存每个 Agent 的完整非敏感业务画像。

### 自然语言目标 Agent

配置一个 OpenAI 兼容模型后，可以让 Agent 根据当前页面的无障碍树自主选择受限操作：

```powershell
$env:LLM_API_KEY='...'
$env:LLM_BASE_URL='https://api.openai.com/v1'
$env:LLM_MODEL='你的模型名称'
npm run agent -- --scenario goal --goal '注册企业账户，然后打开账号设置页面' --count 2 --concurrency 2
```

模型只能选择点击、填写、选择、上传测试 PDF、同站导航、等待和完成。它不能提供 CSS 选择器、执行脚本、离开目标站点、删除数据、修改密码或发起链上交易。实现采用结构化动作输出；模型不支持 JSON Schema 时会回退到 JSON mode。

### 测试钱包

注入一个随机的只读测试钱包：

```powershell
npm run agent -- --scenario register --wallet
```

批量运行时建议用测试助记词为每个 Agent 派生独立地址：

```powershell
$env:TEST_WALLET_MNEMONIC='仅限本地测试链的助记词'
npm run agent -- --scenario register --wallet --wallet-rpc-url http://127.0.0.1:8545 --wallet-chain-id 31337 --count 10
```

测试钱包默认拒绝 `eth_sendTransaction`。只有显式添加 `--allow-chain-writes` 才会广播交易；该参数只应对本地链或专用测试网使用。

### Fuji 审核、签发与交易全流程

`fuji-market` 场景会依次执行：企业注册 → 测试钱包绑定 → 项目申报 → 管理员审核 → 管理员签发 → 等待链上 Worker 确认 → 企业买卖双方挂单或成交。

默认采用真实市场数据模式。每个 Agent 会按 seed 生成不同的核证年份、签发量、价格、挂单量与成交量，并循环覆盖“卖单挂盘、卖单部分成交、卖单完全成交、买单挂盘、买单部分成交”五种行为。这样一批 5 个 Agent 结束后，订单簿会同时保留买盘、卖盘和成交记录。Fuji 上的订单时间取自区块时间，Agent 不会伪造过去的链上时间；批量顺序执行会让订单和成交自然分布在不同区块与分钟。

先复制密钥模板并只在本机填写。不要把私钥、助记词粘贴到聊天、命令历史或提交到 Git：

```powershell
Copy-Item .env.fuji.example .env.fuji.local
```

然后运行一个最小批次：

```powershell
npm run agent -- `
  --scenario fuji-market `
  --env-file .env.fuji.local `
  --count 1 `
  --fund-wallets `
  --allow-chain-writes `
  --issue-quantity 320 `
  --order-quantity 24 `
  --price 8.5
```

上述三个数值在真实市场数据模式中是分布基准，不是每个 Agent 的固定值。需要复现旧的固定金额和“卖单完全成交”流程时，增加 `--fixed-market-values`。

安全约束：

- 场景硬性校验 Avalanche Fuji Chain ID `43113`。
- `FUJI_FUNDER_PRIVATE_KEY` 只向派生用户钱包补足测试 AVAX，不会进入浏览器或报告。
- 买方还需要结算 USDC。若市场使用 Circle 官方 Fuji USDC，分发钱包必须持有足够余额，Agent 使用标准 ERC-20 `transfer`；若使用仓库的 `TestUSDC`，分发钱包也可以是 owner，由 Agent 调用 `mint`。两者都可通过 `FUJI_USDC_FUNDER_PRIVATE_KEY` 单独配置。
- 每钱包和每批次的 AVAX、tUSDC 都有独立上限，见 `.env.fuji.example`。
- 每个新 `batch-id` 会得到一段独立的助记词派生索引，避免新账号重复绑定历史批次的钱包；同一 `batch-id` 恢复运行时地址保持不变。
- 如果派生钱包已经预充值，可以省略 `--fund-wallets`；仍必须显式提供 `--allow-chain-writes`。
- Fuji 场景默认并发为 `1`。确认稳定后再逐步增加，避免公开 RPC 限流和订单竞争。

如果运行在审核、签发或链上确认阶段中断，可以使用原批次编号继续，不会重新注册已有账号或重复创建项目：

```powershell
npm run agent -- `
  --scenario fuji-market `
  --env-file .env.fuji.local `
  --batch-id 原批次编号 `
  --count 5 `
  --resume `
  --fund-wallets `
  --allow-chain-writes
```

恢复运行会写入新的 `*-resume-*` 报告目录，保留原始失败现场。

常用参数：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--scenario` | `application` | `register` 或 `application` |
| `--count` | `1` | Agent 总数 |
| `--concurrency` | 最多 `4` | 同时运行数量 |
| `--base-url` | `http://localhost:3000` | CarbonLink 前端地址 |
| `--timeout` | `30000` | 单个页面操作超时，单位毫秒 |
| `--headed` | 关闭 | 显示浏览器窗口 |
| `--video` | 关闭 | 为每个 Agent 录制视频 |
| `--seed` | 当前批次编号 | 模拟业务数据的随机种子，可用于复现 |
| `--goal` | 空 | `goal` 场景的自然语言目标 |
| `--max-steps` | `24` | 自主 Agent 最大动作数 |
| `--wallet` | 关闭 | 注入测试 EIP-1193 钱包 |
| `--wallet-index-offset` | 根据 `batch-id` 生成 | 指定助记词派生索引起点；旧版批次需要原地址时可设为 `0` |
| `--allow-chain-writes` | 关闭 | 允许测试钱包广播交易 |
| `--fund-wallets` | 关闭 | 从专用 Fuji 资助钱包补足 AVAX 和 tUSDC |
| `--issue-quantity` | `320` | 每个项目签发量的分布基准；真实模式约在基准的 70%–140% 波动 |
| `--order-quantity` | `24` | 挂单量的分布基准；真实模式约在基准的 55%–165% 波动 |
| `--price` | `8.5` | 每 tCO₂e 限价的分布基准；真实模式约在基准的 72%–148% 波动 |
| `--fixed-market-values` | 关闭 | 固定使用上述三个值，并执行卖单完全成交 |
| `--chain-timeout` | `600000` | 等待链上 Worker 和交易确认的最长毫秒数 |
| `--env-file` | 空 | 显式读取本地密钥配置文件 |
| `--resume` | 关闭 | 使用原 `batch-id` 登录已有账号并从项目当前状态继续 |
| `--batch-id` | 当前时间 | 固定批次编号，重复使用会造成注册邮箱冲突 |
| `--output` | `artifacts` | 报告输出目录 |

也可以使用环境变量指定地址：

```powershell
$env:CARBONLINK_BASE_URL='http://localhost:3000'
npm run agent -- --count 10 --concurrency 3
```

## 结果

每个批次会生成：

- `report.json`：批次汇总和每个 Agent 的完整步骤。
- `results.jsonl`：每行一个 Agent，便于导入分析系统。
- `<agent-id>/trace.zip`：可使用 Playwright Trace Viewer 打开。
- `<agent-id>/failure.png`：失败时的完整页面截图。
- `<agent-id>/video/`：启用 `--video` 时的录像。

查看 Trace：

```powershell
npx playwright show-trace artifacts/<batch-id>/<agent-id>/trace.zip
```

## 隔离与限制

- 每个 Agent 使用唯一邮箱、独立 Cookie 和独立本地存储。
- 当前场景会向目标环境写入真实的测试用户、项目和材料，请只在测试环境运行。
- 测试钱包直接注入兼容 EIP-1193 Provider，不控制 MetaMask 窗口，也不会把私钥写入报告。
- 同一个 `batch-id` 不应重复执行，否则邮箱已经注册会导致测试失败。
