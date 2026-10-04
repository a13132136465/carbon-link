# CarbonLink Code Review 与安全审计报告

审计日期：2026-10-04（Asia/Hong_Kong）  
项目：`D:\project\carbon-link`  
基准提交：`afee1905b47b502a56dfb667bb555bd31ce059e1`  
审计对象：**当前工作区，包括已有未提交修改及未跟踪的 user-agent、TestUSDC 等代码**。本报告不是仅针对上述提交的差异审查。

## 1. 结论

当前版本具备角色授权、密码哈希、数据库交易锁、钱包签名绑定、链上资产托管与原子结算等基础控制，但仍有需要修复的数据隔离、恢复流程、文件持久化及审批一致性问题。**建议完成 P1 问题修复与回归后再用于承载真实企业材料或正式资产的生产环境。**

本次记录 **14 项发现：P1 5 项、P2 9 项**。其中 4 项行为在隔离环境实际复现；其余有静态代码或配置证据，未将未执行的验证描述为已复现。没有确认 P0 级问题；这不代表不存在其他漏洞。

现有测试全部通过：PostgreSQL 后端 **34/34**、智能合约 **14/14**、用户 Agent **4/4**，前端生产构建成功。测试通过并不覆盖本报告指出的权限绕过、部署持久化和异常恢复场景。

JavaScript 两个子项目的 npm audit 均为 0 条已知漏洞。Python 测试镜像依赖扫描返回 **66 条公告匹配、涉及 11 个包**，包含同一 CVE 的重复记录，不能解释为 66 个独立、可利用的项目漏洞。已单独确认 Starlette 文件响应公告与本项目下载接口存在代码路径关联。

## 2. 范围、方法与限制

审查覆盖：

- `app/`：认证、用户角色、项目和材料、签发、市场、注销、Agent、链上 Worker、自托管迁移。
- `carbon-link-front/src/`：钱包交互、市场读写、注销与后台展示；前端构建及 Nginx。
- `contracts/src/`、部署脚本和测试：项目登记、碳额度、订单托管、结算、撤单及测试 USDC。
- `user-agent/`：测试执行器、模型动作及钱包适配。
- Docker Compose、Dockerfile、依赖声明、迁移和现有测试。

方法为人工代码审查、隔离行为复现、现有测试执行、构建验证和公开依赖漏洞扫描。未修改业务源码，未向真实链发交易，未读取或披露真实私钥，未对在线服务执行攻击或压力测试。复现只使用虚构账号和临时数据库；临时 PostgreSQL 容器及其数据卷已清理。

后端运行使用已有 `carbon-link-test:latest` 镜像，但挂载了当前工作区源码。逐项核对后，镜像中 15 项直接运行依赖均符合当前 `pyproject.toml` 声明。Python 传递依赖没有完整锁文件，因此镜像扫描结果不等于所有未来重建环境的结果。

未执行：正式链状态及已部署字节码比对、全量秘密历史扫描、容器 OS 漏洞扫描、Solidity 形式化证明、专门的静态分析器扫描，以及生产备份恢复演练。链上故障与多 Worker 问题主要依据状态机分析，未在真实 RPC 故障环境复现。

分级：P1 表示生产发布前应优先修复；P2 表示具有明确触发条件的安全、正确性或可靠性问题。分级结合本项目使用条件，不直接照搬第三方公告 CVSS。

## 3. 发现总览

| 编号 | 优先级 | 问题 | 证据状态 |
| --- | --- | --- | --- |
| R01 | P1 | 普通账号可读取其他企业的草稿和驳回项目详情 | 已复现 |
| R02 | P1（配置条件） | 非 production 且邮件未送达时，匿名找回密码直接返回重置令牌 | 已复现 |
| R03 | P2 | 旧项目提交接口绕过必需材料检查 | 已复现 |
| R04 | P2 | 修改或重置密码没有撤销已有登录令牌 | 改密路径已复现；重置路径静态确认 |
| R05 | P1 | 附件保存在 API 容器可写层，重建容器后丢失 | 配置及文件路径确认 |
| R06 | P2 | Nginx 默认上传限制与后端 20 MiB 限制不一致 | 配置及官方文档确认 |
| R07 | P2 | 上传先完整读入内存，再执行大小检查 | 静态确认 |
| R08 | P1 | 审核状态未加锁，竞争审批可导致数据库拒绝但链上登记成功 | 静态并发时序分析 |
| R09 | P2 | 注销确认未校验链上 evidenceDigest 与提交用途一致 | 静态跨端核对 |
| R10 | P2 | 多 Worker 缺少签名账户级 nonce 协调 | 静态并发时序分析 |
| R11 | P2 | 已广播交易确认异常越过重试逻辑，并存在队头阻塞 | 静态状态机分析 |
| R12 | P2 | 链上模式的仪表盘和资产流水继续读取旧数据库交易表 | 静态跨端核对 |
| R13 | P2 | 测试 Agent 将“受阻结束”也记为完成 | 静态确认 |
| R14 | P1 | 后端依赖存在已知漏洞，文件下载使用受影响 Starlette | 扫描及官方公告核对 |

## 4. 详细发现

### R01 — 普通账号可读取其他企业的草稿和驳回项目详情

**位置：** [app/api.py:201](D:/project/carbon-link/app/api.py:201)。

`GET /api/v1/projects` 默认 `mine=false`，只有调用者主动传入 `mine=true` 才增加 `owner_id` 过滤，未按普通成员角色强制隔离。返回的是完整 `ProjectOut`，包含描述、方法学、预计减排量、审核意见等，而不是经过裁剪的公开市场摘要。

**实际复现：** Alice 创建带 `CONFIDENTIAL` 描述的草稿；Bob 登录后调用项目列表，响应包含 Alice 的项目 ID 和该描述。无需猜测项目 ID，分页即可枚举。

**影响：** 注册用户可访问其他企业尚未提交或审核失败的业务资料。附件下载接口有单独授权，未发现可直接借此下载他人附件。

**修复与验收：** 普通成员始终限制为本人项目；管理员和核证员按工作职责授权。若已审核项目需要公开展示，另建公开响应模型和明确状态过滤。回归覆盖普通成员在省略、开启、关闭 `mine` 及不同 `status` 参数下均看不到他人非公开资料。

### R02 — 非 production 模式可匿名获得密码重置令牌

**位置：** [app/api.py:83](D:/project/carbon-link/app/api.py:83)、[app/notifications.py:5](D:/project/carbon-link/app/notifications.py:5)、[app/config.py:7](D:/project/carbon-link/app/config.py:7)、[compose.yaml:24](D:/project/carbon-link/compose.yaml:24)。

找回接口在账号存在时生成令牌；只有 `environment == "production"` 或邮件投递成功才清除响应中的 `reset_token`。环境是任意字符串，默认 `development`；SMTP 缺失或发送失败均可能进入返回原始令牌的分支。

**实际复现：** 在 `ENVIRONMENT=test` 且 SMTP 不可用的隔离环境，未登录请求已知邮箱，响应包含有效重置令牌。随后可按接口设计用该令牌设置新密码。

**影响与边界：** 如果此模式的 API 对不可信用户开放，可接管已知邮箱账号，包括管理员；严格设置 `production` 时此返回路径关闭。默认 Compose 只绑定回环地址，不能据此声称默认部署已暴露公网，但被反向代理开放时风险成立。

**修复与验收：** HTTP 响应始终不返回令牌。测试通过邮件桩获取令牌；开发体验使用独立测试邮箱。限制环境枚举，并在公开部署时验证必要配置。分别测试 SMTP 缺失、异常、成功，所有情况下响应都不含令牌。

### R03 — 旧提交接口绕过必需材料检查

**位置：** [app/api.py:230](D:/project/carbon-link/app/api.py:230) 与 [app/api.py:302](D:/project/carbon-link/app/api.py:302)。

`/applications/{id}/submit` 强制检查四类必需材料，而 `/projects/{id}/submit` 直接把项目设置为 `pending`。审核接口也没有再次校验材料完整性。

**实际复现：** 对同一份无附件草稿，application 提交返回 409，旧 project 提交返回 200 并进入待审核状态。现有完整流程测试实际使用旧路径，因此没有检测这个绕过。

**影响：** “材料齐全后才可提交”的业务约束可被普通用户绕过。后续仍需审核员批准，不能直接推导为普通用户可自行发行资产。

**修复与验收：** 合并两条入口到同一个领域服务；需要兼容时由旧路由委托新逻辑。两条接口对相同材料状态返回一致结果，缺任意一种必需材料均不可提交。

### R04 — 改密、密码找回不撤销旧会话

**位置：** [app/api.py:100](D:/project/carbon-link/app/api.py:100)、[app/api.py:170](D:/project/carbon-link/app/api.py:170)、[app/deps.py:12](D:/project/carbon-link/app/deps.py:12)、[app/security.py:17](D:/project/carbon-link/app/security.py:17)。

改密只更新密码哈希；JWT 只包含用户、角色、签发时间和过期时间。鉴权查询用户是否存在、是否启用，但不比较密码变更时间或会话版本。

**实际复现：** 使用 token A 修改密码后，继续用 token A 调用 `/users/me`，仍返回 200。

**影响：** 密码泄露后的恢复操作无法立即驱逐已经取得令牌的攻击者，默认剩余风险窗口最多约 30 分钟。重置密码只消耗当前重置令牌，其他尚未过期的重置令牌也没有统一撤销。

**修复与验收：** 增加 `token_version` 或精确定义的 `credentials_changed_at` 校验；改密、找回和安全恢复时撤销旧访问令牌及其余重置令牌。验证恢复后旧令牌失败，新密码登录得到的新令牌正常。

### R05 — 上传附件没有持久化存储

**位置：** [app/config.py:38](D:/project/carbon-link/app/config.py:38)、[app/api.py:273](D:/project/carbon-link/app/api.py:273)、[compose.yaml:20](D:/project/carbon-link/compose.yaml:20)、[compose.yaml:108](D:/project/carbon-link/compose.yaml:108)。

默认附件路径是 `/app/uploads`，API 服务未挂载附件卷；Compose 只为 PostgreSQL 配置了数据卷。数据库保存附件记录，文件写入 API 容器可写层。

**影响：** 删除并重建 API 容器或滚动部署后，数据库材料记录仍在，下载文件却不存在。普通进程重启、同一容器 stop/start 不等同于容器重建，不应混淆。

**验证依据：** 容器工作目录、`UPLOAD_ROOT`、写入代码及挂载配置一致，未实际重建用户现有服务。

**修复与验收：** 配置专门持久卷或对象存储；API 实例共享文件存储并纳入备份。用测试材料完成“上传—重建 API—下载—校验哈希”验收，并验证数据库与文件联合恢复。项目删除与写入失败还需处理孤儿文件。

### R06 — 代理与后端上传大小限制不一致

**位置：** [carbon-link-front/nginx.conf:19](D:/project/carbon-link/carbon-link-front/nginx.conf:19)、[app/config.py:39](D:/project/carbon-link/app/config.py:39)。

后端允许 20 MiB，仓库 Nginx 配置没有 `client_max_body_size`。Nginx 默认值为 1m，超过时返回 413。依据：[Nginx 官方指令说明](https://nginx.org/en/docs/http/ngx_http_core_module.html#client_max_body_size)。

**影响：** 默认同域代理路径中，超过约 1 MiB、但符合后端限制的正常 PDF 或 Office 文件被代理拒绝；直接访问后端的测试不能覆盖该问题。

**修复与验收：** 显式设置代理上限并与应用保持一致；用经前端代理的真实上传请求测试 1 MiB、2 MiB、20 MiB 及超限边界，确认错误消息可读。

### R07 — 上传限制发生在内存分配之后

**位置：** [app/api.py:266](D:/project/carbon-link/app/api.py:266)。

`await request.body()` 先读取完整请求体，再用 `len(content)` 判断最大字节数。攻击者可以用有效成员账号直接访问 API，或在代理上限被调大后发送超大请求。

**影响：** 应用层 20 MiB 限制并不能限制读取阶段内存占用，多个并发请求可能耗尽 Worker 内存。当前 Nginx 1m 默认值对经过该代理的流量有缓解作用，但不是应用自身的保证。

**修复与验收：** 流式读取并累计长度，超过阈值立刻终止并清理临时文件；限制单账号存储配额、并发和速率。不能只信任 `Content-Length`。覆盖 chunked 请求、伪造长度及超限中断后的文件清理。

### R08 — 竞争审核可能产生拒绝状态和链上有效项目

**位置：** [app/api.py:334](D:/project/carbon-link/app/api.py:334)。

审核使用 `db.get` 读取 `pending` 状态，随后修改状态并在批准时写入登记 Outbox，没有行锁、版本列或条件更新。

**可触发时序（静态分析）：** A 和 B 分别读取同一待审项目；A 批准并提交登记任务；B 基于此前读取的 `pending` 对象驳回并提交。最终项目为 `rejected`，A 创建的登记任务仍可被 Worker 执行。批准/驳回之间没有 Outbox 唯一约束能够阻止这种交错。

**影响：** 数据库审核事实与链上有效登记不一致，后续用户可重新编辑被驳回项目，导致材料与已经登记的承诺进一步偏离。

**修复与验收：** 项目审核、提交和材料状态变更使用同一套行锁或乐观版本控制；审核通过与 Outbox 写入同一事务；状态过期的一方返回 409。增加 PostgreSQL 双审核者批准/驳回并发测试，断言只能一个结果成功，最终状态与任务一致。

### R09 — 注销用途未与链上证据哈希比对

**位置：** [app/api.py:494](D:/project/carbon-link/app/api.py:494)、[carbon-link-front/src/pages.tsx:88](D:/project/carbon-link/carbon-link-front/src/pages.tsx:88)。

前端把 `keccak256(reason)` 传入合约的 `evidenceDigest`。确认接口验证批次、数量、账户和受益人哈希，但没有验证 `evidenceDigest`，随后把本次请求的 `reason` 保存为证书用途。

**触发条件：** 持有人以用途 A 签名注销后，使用相同交易哈希、批次、数量和受益人，以用途 B 调用确认接口。

**影响：** 可生成用途文本与原始签名承诺不一致的证书。该问题不会绕过数量核验，也不允许其他账户领取该交易的证书。

**修复与验收：** 对 `match.args.evidenceDigest` 与约定编码的 `Web3.keccak(text=body.reason)` 做严格比对，并定义 Unicode/编码规则。用途被替换时返回 422；正确用途成功；重复提交不生成第二张证书。

### R10 — 多 Worker 缺少签名账户级 nonce 分配

**位置：** [app/chain_worker.py:105](D:/project/carbon-link/app/chain_worker.py:105)、[app/chain_worker.py:168](D:/project/carbon-link/app/chain_worker.py:168)。

`skip_locked` 锁定的是不同 Outbox 行。两个 Worker 可分别拿到任务，在任一交易广播之前都读取同一个账户的 pending nonce。`prepare` 保存后立即提交，行锁也在广播之前释放。

**影响与边界：** 扩容为多个 Worker、重复启动实例或其他程序共用操作账户时，可能发生 nonce 冲突、交易替换或重复处理。默认单 Worker 不等同于必然发生此问题。

**修复与验收：** 对 `(chain_id, operator)` 做账户级串行协调，持久化 nonce 预留并与链上 pending 状态对账；若只支持一个 Worker，应明确部署约束并阻止重复消费者。测试并发准备两条不同任务时 nonce 不重复，且崩溃后原始交易可重播。

### R11 — 确认阶段异常未进入重试策略

**位置：** [app/chain_worker.py:133](D:/project/carbon-link/app/chain_worker.py:133)、[app/chain_worker.py:170](D:/project/carbon-link/app/chain_worker.py:170)、[app/chain_worker.py:211](D:/project/carbon-link/app/chain_worker.py:211)。

`run_once` 优先取最早的 submitted 任务并调用 `confirm`，该分支位于处理 pending/prepared 的 `try/except` 外。`confirm` 只捕获 `TransactionNotFound`；RPC 超时、网络错误等会直接逃出主循环，无法写入任务错误和退避时间。

此外，只要存在一个未达到确认数的 submitted 任务，每轮都会提前返回，其他 pending 任务不能继续发送。短暂等待是串行设计取舍，但长期挂起交易会形成全队列阻塞。

**影响：** RPC 波动引发容器反复重启，任务状态缺少诊断信息；单笔交易迟迟未确认影响后续项目登记和签发。

**修复与验收：** 给确认阶段添加持久化错误、退避和总超时策略；明确如何处理掉池、低费率、链重组和 nonce 被占用。通过 RPC 桩模拟超时、未找到、回执回滚和确认延迟，验证进程不中断且队列能按策略恢复。

### R12 — 链上模式的统计与资产流水不反映真实成交

**位置：** [app/api.py:393](D:/project/carbon-link/app/api.py:393)、[app/api.py:530](D:/project/carbon-link/app/api.py:530)、[carbon-link-front/src/market.tsx:28](D:/project/carbon-link/carbon-link-front/src/market.tsx:28)、[carbon-link-front/src/pages.tsx:79](D:/project/carbon-link/carbon-link-front/src/pages.tsx:79)。

市场直接通过合约成交，后台没有相应链上交易事件索引写入 `Trade`、`Listing` 和 `LedgerEntry`。但 `/dashboard` 继续从这些旧数据库表计算挂单量和交易量，钱包流水也仍只读 `LedgerEntry`。启用链上模式后签发路径也不再写本地资产流水。

**影响：** 用户已完成链上成交，市场可显示该成交，控制台总成交量或钱包流水却保持 0/旧值。直接在链上注销但未调用确认接口时，数据库累计注销也不完整。

**修复与验收：** 实现有确认高度、幂等事件键和重组处理的事件索引；或者明确隐藏尚未支持的指标和流水，不以旧账本值冒充实时链上统计。验收覆盖签发、挂单、部分成交、撤单和注销后的跨页面一致性。

### R13 — Agent 将受阻结束报告为成功

**位置：** [user-agent/src/goal-agent.mjs:48](D:/project/carbon-link/user-agent/src/goal-agent.mjs:48)、[user-agent/src/goal-agent.mjs:127](D:/project/carbon-link/user-agent/src/goal-agent.mjs:127)、[user-agent/src/cli.mjs:169](D:/project/carbon-link/user-agent/src/cli.mjs:169)。

系统提示允许模型“受阻时 finish 并解释原因”，代码却把所有 `finish` 都转换为 `completed: true`。CLI 默认记录 passed，只有异常才改成 failed。

**影响：** 页面报错或任务未完成，只要模型按提示以 finish 退出，批量验收就可能统计成功。现有测试只覆盖真实完成，没有覆盖受阻结束。

**修复与验收：** 区分 `success`、`blocked`、`failed`；关键目标由可观察页面断言或业务只读查询验证。给模型返回“无法继续”的 finish 添加测试，结果必须不是 passed。

### R14 — 后端依赖存在已知漏洞，FileResponse 路径可达

**位置：** [pyproject.toml:13](D:/project/carbon-link/pyproject.toml:13)、[app/api.py:288](D:/project/carbon-link/app/api.py:288)。

测试镜像使用 FastAPI 0.116.1 / Starlette 0.47.3。扫描命中 **CVE-2025-62727 / GHSA-7f5h-v6xp-fcq8**；官方公告说明受影响 Starlette 的文件响应 Range 处理存在平方复杂度，0.49.1 修复该项问题。依据：[Starlette 官方安全公告](https://github.com/Kludex/starlette/security/advisories/GHSA-7f5h-v6xp-fcq8)。

**项目可达性：** 材料下载返回 `FileResponse`。攻击者需要有权访问某个文件；普通自注册用户可以创建草稿并上传自己的文件。因此不能照搬公告声称本项目下载入口完全无需登录，但也不能当成未使用依赖忽略。未在本次审计中发送耗时攻击请求。

**修复与验收：** 联动升级 FastAPI 和兼容的 Starlette，确保当前全部适用公告得到处理；0.49.1 只是此 CVE 的修复点，不是所有扫描结果的最终安全版本。重建镜像、锁定传递依赖并重新扫描。临时措施可以限制/拒绝下载接口多范围请求，仍需正式修复。

其他依赖命中见下一节，不能一概断言具有 RCE、SSRF 或认证绕过的项目可达性。当前 `app/` 未发现 LangChain/LangGraph 导入，申报 Agent 实际调用 OpenAI SDK；优先移除不再需要的旧依赖链。

## 5. 依赖审计明细

扫描时间为审计当日。`npm audit --json` 检查了两个子项目的锁文件，均未返回已知漏洞。Python 扫描基于安装审计工具前导出的镜像 `pip freeze`，以 `--no-deps --disable-pip` 对已解析版本查询公告，避免审计工具安装本身改变扫描基线；项目 editable 条目无法按包版本扫描，项目源码由人工审查覆盖。

| 包 | 实际版本 | 扫描返回的公告匹配数（未去重） | 处置与可达性判断 |
| --- | --- | ---: | --- |
| langchain | 0.3.27 | 3 | 未发现应用导入；删除无用依赖优先，不能据此宣称应用存在任意文件读取 |
| langchain-core | 0.3.86 | 3 | 同上；检查其他使用方后删除或整体升级 |
| langchain-openai | 0.3.32 | 2 | 当前应用直接使用 OpenAI SDK，未确认公告所述图像计数路径可达 |
| langchain-text-splitters | 0.3.11 | 2 | 旧依赖链，未确认业务调用 |
| langgraph | 0.6.6 | 2 | 未发现当前应用导入 |
| langgraph-checkpoint | 2.1.2 | 6 | 未发现 checkpoint 反序列化调用，不能宣称当前可远程执行代码 |
| langgraph-sdk | 0.2.15 | 2 | 未发现当前业务调用 |
| PyJWT | 2.10.1 | 20 | 实际使用；逐条按 HS256、固定算法白名单及必需 claim 配置筛选，不能将所有条目视为可绕过登录 |
| pytest | 8.4.2 | 2 | 测试依赖，不是生产 HTTP 攻击面；开发/CI 仍应更新 |
| python-multipart | 0.0.20 | 12 | 当前附件上传直接读 raw body，未确认公告对应 multipart 路径可达 |
| starlette | 0.47.3 | 12 | FileResponse Range 公告与当前业务明确关联；其他条目仍需按平台和调用路径筛选 |
| **合计** | | **66** | **11 个包；不是 66 个独立漏洞** |

多个记录共享同一 CVE/PYSEC ID，公告别名及版本建议存在重复；本报告保留扫描原始计数，没有累加为项目独立漏洞数。`PyJWT` 某些扫描条目未提供修复版本，不能通过取一个最大版本号就宣称全部解决。

构建可复现性方面，后端缺少完整传递依赖锁定，OpenAI 允许范围升级；前端使用多处 `latest`，但已有 lockfile 且 Docker 使用 `npm ci`，因此“当前构建完全不锁版本”的说法不成立。建议统一锁文件更新、依赖审计和镜像重建验证流程。

## 6. 合约与前端专项观察

以下是需要明确业务规则或补充验证的项目，不计入上述 14 项已列问题，也不声称均为可利用漏洞。

1. **项目撤销与已发行批次资格。** `CarbonCreditLedger.issueBatch` 检查项目 active，但转账和 retire 只检查批次冻结/暂停。项目被撤销后，旧批次仍可能交易、注销。若业务要求撤销连带失效，需批次冻结或资格检查；若只禁止后续发行，应在界面与治理文档明确。现有测试仅验证撤销阻止新发行。
2. **买单最后一笔承担舍入余量。** `fillBuyOrder` 最后一笔支付 `remainingQuote`，不是单独 `quoteFor`。例如总量 3 个基础单位、价格 19,999 个 USDC 最小单位时，托管为 5；三次各成交 1 单位，支付 1、1、3。总额守恒，但最后成交者的实际单价不同。单笔分割误差很小，不应夸大为巨额资金漏洞；需定义舍入归属和最小成交金额并添加边界测试。
3. **暂停/冻结时卖方撤单。** 市场 cancel 不受市场暂停约束，这是合理的紧急退出设计；但返还 ERC-1155 仍会受底层 credit 合约暂停或批次冻结影响。需明确资产何时可解锁，不能承诺任何暂停情况下都能立即退回。
4. **订单簿读取没有固定区块。** 前端先读 activeOrderCount，再读所有索引和订单，期间合约删除订单会交换并缩短数组；多个 latest 调用可能越界或混合快照。每 10 秒全量读取也随订单数增长。建议指定同一 blockTag、限制并发并引入索引/分页。
5. **24h 指标只取最近 200 笔。** 活跃市场在一天超过 200 笔后，当前前端统计会截断成交量和高低价。应聚合完整时间窗口，或标注统计仅覆盖采样。
6. **链配置中的 RPC URL 可见。** `/chain/config` 向所有登录用户返回服务端 RPC 地址，前端直接使用。若地址带提供商 key，该 key 会被用户获得。建议区分服务端私有 RPC 与浏览器公开 RPC；未读取实际配置，因此未认定当前已泄露凭据。
7. **Nginx 安全头继承。** 页面和静态资源 location 各自设置 `add_header Cache-Control`，按当前镜像版本的继承规则，不再继承 server 级安全头。建议在对应 location 包含统一安全头配置并对 HTML/JS 响应验证。依据：[Nginx add_header 文档](https://nginx.org/en/docs/http/ngx_http_headers_module.html#add_header)。
8. **资源滥用保护。** 应用和仓库 Nginx 未见登录、注册、找回密码、LLM 调用的速率/配额控制。建议覆盖 Argon2 CPU 成本、邮件发送和模型费用；不能假设外部部署没有额外网关保护。

积极控制包括：密码使用 Argon2；鉴权从数据库读取实时角色和启用状态；钱包绑定核验挑战签名并拒绝自动换绑；中心化成交在链上模式下被拒绝；合约关键市场写操作采用 `nonReentrant`、`SafeERC20` 和原子交割；批次发行有唯一验证哈希；注销确认核验发送者、目标合约、回执成功和确认数。这些控制已纳入判断，但不抵消上述跨层缺陷。

## 7. 验证记录

| 检查 | 执行结果 | 说明 |
| --- | --- | --- |
| 本机 `python -m pytest` | 环境不足 | 本机 Python 缺少 SQLAlchemy；之后用现有镜像成功验证 |
| 当前源码 + SQLite 后端测试 | 32 通过、2 跳过 | 跳过项明确要求 PostgreSQL 行锁 |
| 当前源码 + 临时 PostgreSQL 后端测试 | **34 通过** | 包含两个并发库存测试；1 条 TestClient 弃用告警 |
| `npm run build` | **通过** | TypeScript 与 Vite 通过；JS 主包约 765 kB，产生分包建议 |
| `node --test --test-reporter=tap --test-timeout=15000` | **4 通过** | 首次沙箱执行浏览器受限；允许浏览器子进程后全部通过 |
| 临时 Foundry 容器 `forge test -vv` | **14 通过** | Solc 0.8.30；包含 256 次 retirement fuzz |
| 前端 npm audit | **0 条** | 公告查询成功；不是所有供应链风险的证明 |
| user-agent npm audit | **0 条** | 公告查询成功 |
| Python pip-audit | **66 条匹配 / 11 包** | 未去重；详细适用性见第 5 节 |
| 隔离行为复现 | **4 项断言成立** | 草稿跨账号读取、材料检查绕过、旧 JWT 继续有效、非生产返回重置令牌 |

后端测试使用只读源码挂载，数据库和上传文件写入临时容器。PostgreSQL 容器未开放宿主端口，测试通过共享临时容器网络访问。合约测试复制 src/test/lib/script 与配置到临时工作目录，未读取合约 `.env`，也未向已部署合约发送交易。

复现关键步骤（仅在隔离测试环境执行）：

```text
R01: 注册 Alice、Bob -> Alice 创建草稿 -> Bob GET /api/v1/projects
     实际：200，包含 Alice 的草稿描述。

R02: 环境非 production、邮件服务不可用 -> 匿名 POST /auth/password/forgot
     实际：已知邮箱的响应中 reset_token 非空。

R03: 无材料草稿 -> POST /applications/{id}/submit -> 409
     同一草稿 -> POST /projects/{id}/submit -> 200，状态 pending。

R04: 登录取得 token A -> POST /users/me/password -> 200
     使用原 token A GET /users/me -> 200。
```

所有路径均相对 `/api/v1`。材料检查绕过和会话问题的回归应断言修复后的拒绝行为，不能继续把当前行为作为正确预期。

## 8. 修复顺序与发布验收

**第一批：安全和数据完整性。** 修复项目列表隔离、重置令牌返回、附件持久化、审批并发，以及可达的 Starlette 漏洞。优先添加对应的负向权限测试、审批竞争测试和容器重建附件测试。

**第二批：跨层一致性和恢复。** 合并提交校验、实现会话撤销、核验注销用途哈希、统一上传限制、实现流式大小限制，补齐 Worker nonce 和故障处理。

**第三批：可信展示与验收。** 补链上事件索引、统一指标来源、修复 Agent 受阻结果判定，处理行情采样和读快照问题。

建议发布验收必须满足：

- 普通成员不能读取其他企业草稿；两条提交入口对材料完整性一致。
- HTTP 响应不再返回重置令牌；恢复密码后旧会话和其他重置令牌失效。
- 容器重建后材料可下载，文件哈希不变，并具备恢复演练结果。
- 审核竞争只有一个成功状态，Outbox 与数据库最终状态一致。
- 注销用途与链上签名承诺一致；链上统计与实际交易一致。
- Worker 在超时、重复消费者和重播场景下不重复分配 nonce，不静默退出。
- 依赖重新锁定并扫描，对剩余告警逐项记录可达性判断、责任人和处理计划。
- PostgreSQL、合约、前端和 Agent 测试重新通过，新增负向与故障测试覆盖本次发现。

本次交付仅为审查与报告，未代替业务修复。问题位置对应审计时工作区，后续代码移动后行号可能变化。
