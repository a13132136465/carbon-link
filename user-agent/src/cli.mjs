import { chromium } from 'playwright'
import { createHash } from 'node:crypto'
import { config as loadEnvFile } from 'dotenv'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import process from 'node:process'
import { AgentSession } from './agent-session.mjs'
import { createIdentity, createMarketProfile } from './data-factory.mjs'
import { FujiFundingManager } from './fuji-funding.mjs'
import { scenarios } from './scenarios.mjs'

function readArguments(argv) {
  const values = {}
  for (let index = 0; index < argv.length; index += 1) {
    const item = argv[index]
    if (!item.startsWith('--')) continue
    const [rawKey, inlineValue] = item.slice(2).split('=', 2)
    if (inlineValue !== undefined) values[rawKey] = inlineValue
    else if (argv[index + 1] && !argv[index + 1].startsWith('--')) values[rawKey] = argv[++index]
    else values[rawKey] = true
  }
  return values
}

function positiveInteger(value, fallback, name) {
  if (value === undefined) return fallback
  const parsed = Number(value)
  if (!Number.isInteger(parsed) || parsed < 1) throw new Error(`${name} 必须是正整数`)
  return parsed
}

function nonNegativeInteger(value, fallback, name) {
  if (value === undefined) return fallback
  const parsed = Number(value)
  if (!Number.isInteger(parsed) || parsed < 0) throw new Error(`${name} 必须是非负整数`)
  return parsed
}

function batchWalletIndexBase(batchId) {
  const digest = createHash('sha256').update(`carbonlink-user-agent:${batchId}`).digest()
  return digest.readUInt32BE(0) % 2_000_000_000
}

function positiveDecimal(value, fallback, name) {
  const parsed = Number(value ?? fallback)
  if (!Number.isFinite(parsed) || parsed <= 0) throw new Error(`${name} 必须是正数`)
  return String(value ?? fallback)
}

function sanitize(value) {
  return String(value).replace(/[^a-zA-Z0-9_-]/g, '-')
}

function walletConfig(args, index) {
  if (!args.wallet && !args['wallet-private-key'] && !args['wallet-mnemonic']) return null
  const mnemonic = args['wallet-mnemonic'] ?? process.env.TEST_WALLET_MNEMONIC
  const privateKey = mnemonic ? undefined : args['wallet-private-key'] ?? process.env.TEST_WALLET_PRIVATE_KEY
  if (privateKey && index > 0) throw new Error('单个测试私钥只能用于单 Agent；批量运行请使用 --wallet-mnemonic')
  return {
    privateKey,
    mnemonic,
    rpcUrl: args['wallet-rpc-url'] ?? process.env.BLOCKCHAIN_RPC_URL,
    chainId: args['wallet-chain-id'] ?? process.env.BLOCKCHAIN_CHAIN_ID,
    allowWrites: Boolean(args['allow-chain-writes']),
    index,
  }
}

async function main() {
  const args = readArguments(process.argv.slice(2))
  if (args['env-file']) {
    const loaded = loadEnvFile({ path: path.resolve(String(args['env-file'])), override: false })
    if (loaded.error) throw new Error(`无法读取 --env-file: ${loaded.error.message}`)
  }
  if (args.help) {
    console.log(`用法:
  npm run agent -- --scenario application --count 10 --concurrency 5
  npm run agent -- --scenario goal --goal "注册企业账号并打开账号设置"

场景: register, application, goal, fuji-market
常用参数: --base-url, --count, --concurrency, --timeout, --video, --headed
自主 Agent: --goal, --max-steps, --llm-api-key, --llm-base-url, --llm-model
测试钱包: --wallet, --wallet-mnemonic, --wallet-rpc-url, --wallet-chain-id, --wallet-index-offset, --allow-chain-writes
Fuji 全流程: --env-file, --fund-wallets, --issue-quantity, --order-quantity, --price, --fixed-market-values`)
    return
  }

  const scenarioName = String(args.scenario ?? 'application')
  const scenario = scenarios[scenarioName]
  if (!scenario) throw new Error(`未知场景 ${scenarioName}；可选值: ${Object.keys(scenarios).join(', ')}`)
  if (scenarioName === 'goal' && !String(args.goal ?? '').trim()) throw new Error('goal 场景必须提供 --goal')
  const count = positiveInteger(args.count, 1, 'count')
  const concurrency = Math.min(positiveInteger(args.concurrency, scenarioName === 'fuji-market' ? 1 : Math.min(count, 4), 'concurrency'), count)
  const timeoutMs = positiveInteger(args.timeout, 30_000, 'timeout')
  const maxSteps = positiveInteger(args['max-steps'], 24, 'max-steps')
  const issueQuantity = positiveDecimal(args['issue-quantity'], '320', 'issue-quantity')
  const orderQuantity = positiveDecimal(args['order-quantity'], '24', 'order-quantity')
  const orderPrice = positiveDecimal(args.price, '8.5', 'price')
  if (Number(orderQuantity) > Number(issueQuantity)) throw new Error('order-quantity 不能超过 issue-quantity')
  const baseUrl = String(args['base-url'] ?? process.env.CARBONLINK_BASE_URL ?? 'http://localhost:3000').replace(/\/$/, '')
  if (args.resume && !args['batch-id']) throw new Error('--resume 必须同时提供原始 --batch-id')
  const batchId = sanitize(args['batch-id'] ?? new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14))
  const seed = String(args.seed ?? batchId)
  const walletIndexOffset = nonNegativeInteger(args['wallet-index-offset'], batchWalletIndexBase(batchId), 'wallet-index-offset')
  const runId = args.resume ? `${batchId}-resume-${new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14)}` : batchId
  const outputRoot = path.resolve(String(args.output ?? 'artifacts'), runId)
  await mkdir(outputRoot, { recursive: true })

  let funding = null
  if (scenarioName === 'fuji-market') {
    if (!args['allow-chain-writes']) throw new Error('fuji-market 必须显式传入 --allow-chain-writes')
    if (!process.env.TEST_WALLET_MNEMONIC && !args['wallet-mnemonic']) throw new Error('fuji-market 需要 TEST_WALLET_MNEMONIC')
    if (!process.env.BOOTSTRAP_ADMIN_PASSWORD && !args['admin-password']) throw new Error('fuji-market 需要 BOOTSTRAP_ADMIN_PASSWORD 或 --admin-password')
    const chainId = Number(args['wallet-chain-id'] ?? process.env.BLOCKCHAIN_CHAIN_ID)
    if (chainId !== 43113) throw new Error(`fuji-market 只允许 Chain ID 43113，当前为 ${chainId}`)
    if (args['fund-wallets']) {
      funding = await FujiFundingManager.create({
        rpcUrl: args['wallet-rpc-url'] ?? process.env.BLOCKCHAIN_RPC_URL,
        usdcAddress: args['usdc-address'] ?? process.env.USDC_CONTRACT_ADDRESS,
        gasPrivateKey: process.env.FUJI_FUNDER_PRIVATE_KEY,
        usdcPrivateKey: process.env.FUJI_USDC_FUNDER_PRIVATE_KEY,
        gasPerWallet: args['gas-per-wallet'] ?? process.env.FUJI_GAS_PER_WALLET,
        maxGasPerWallet: process.env.FUJI_MAX_GAS_PER_WALLET,
        maxGasPerBatch: process.env.FUJI_MAX_GAS_PER_BATCH,
        usdcPerBuyer: args['usdc-per-buyer'] ?? process.env.FUJI_USDC_PER_BUYER,
        maxUsdcPerWallet: process.env.FUJI_MAX_USDC_PER_WALLET,
        maxUsdcPerBatch: process.env.FUJI_MAX_USDC_PER_BATCH,
      })
      funding.assertBatchCapacity(count * 2, count)
    }
  }

  console.log(`CarbonLink 用户 Agent: scenario=${scenarioName}, count=${count}, concurrency=${concurrency}`)
  console.log(`目标: ${baseUrl}`)
  console.log(`报告: ${outputRoot}`)
  if (scenarioName === 'fuji-market') console.log(`钱包派生索引起点: ${walletIndexOffset}`)

  let browser
  try {
    browser = await chromium.launch({ headless: !args.headed })
  } catch (error) {
    if (String(error.message).includes('Executable doesn\'t exist')) {
      throw new Error('Chromium 尚未安装，请先运行 npm run install-browser')
    }
    throw error
  }

  const results = new Array(count)
  let nextIndex = 0
  async function worker() {
    while (nextIndex < count) {
      const index = nextIndex++
      const identity = createIdentity({ batchId, seed, index })
      const marketProfile = createMarketProfile({
        seed,
        index,
        issueBase: issueQuantity,
        orderBase: orderQuantity,
        priceBase: orderPrice,
        fixed: Boolean(args['fixed-market-values']),
      })
      console.log(`[${identity.id}] 市场画像: ${marketProfile.behavior.label}；核证年份=${marketProfile.vintageYear}；签发=${marketProfile.issueQuantity}；挂单=${marketProfile.orderQuantity}；成交=${marketProfile.fillQuantity}；价格=${marketProfile.price}`)
      const artifactDir = path.join(outputRoot, identity.id)
      const sellerWallet = scenarioName === 'fuji-market'
        ? walletConfig({ ...args, wallet: true, 'allow-chain-writes': true }, walletIndexOffset + index * 2)
        : walletConfig(args, index)
      const session = new AgentSession({ browser, baseUrl, artifactDir, identity, timeoutMs, video: Boolean(args.video), wallet: sellerWallet })
      const startedAt = new Date()
      let status = 'passed'
      let data = null
      let error = null
      try {
        await session.start()
        data = await scenario(session, {
          goalAgent: {
            goal: String(args.goal ?? ''),
            maxSteps,
            apiKey: args['llm-api-key'] ?? process.env.LLM_API_KEY,
            baseUrl: args['llm-base-url'] ?? process.env.LLM_BASE_URL,
            model: args['llm-model'] ?? process.env.LLM_MODEL,
          },
          fuji: {
            adminEmail: args['admin-email'] ?? process.env.BOOTSTRAP_ADMIN_EMAIL ?? 'admin@example.com',
            adminPassword: args['admin-password'] ?? process.env.BOOTSTRAP_ADMIN_PASSWORD,
            marketProfile,
            chainTimeoutMs: positiveInteger(args['chain-timeout'], 600_000, 'chain-timeout'),
            resume: Boolean(args.resume),
            funding,
            buyerIdentity: createIdentity({ batchId: `${batchId}-buyer`, seed: `${seed}:buyer`, index }),
            buyerWallet: scenarioName === 'fuji-market'
              ? walletConfig({ ...args, wallet: true, 'allow-chain-writes': true }, walletIndexOffset + index * 2 + 1)
              : null,
          },
        })
      } catch (caught) {
        status = 'failed'
        error = { message: caught.message, stack: caught.stack }
      } finally {
        await session.finish(status)
      }
      results[index] = {
        agentId: identity.id,
        scenario: scenarioName,
        status,
        identity: {
          email: identity.email,
          displayName: identity.displayName,
          behavior: identity.behavior,
          projectCode: identity.projectCode,
          project: identity.project,
          documents: identity.documents,
          market: marketProfile,
        },
        startedAt: startedAt.toISOString(),
        finishedAt: new Date().toISOString(),
        durationMs: Date.now() - startedAt.getTime(),
        data: { ...data, wallet: session.walletInfo ?? null },
        error,
        events: session.events,
        artifacts: path.relative(outputRoot, artifactDir),
      }
      console.log(`[${identity.id}] ${status.toUpperCase()}`)
    }
  }

  try {
    await Promise.all(Array.from({ length: concurrency }, () => worker()))
  } finally {
    await browser.close()
  }

  const passed = results.filter(result => result.status === 'passed').length
  const report = {
    batchId,
    runId,
    scenario: scenarioName,
    baseUrl,
    count,
    concurrency,
    seed,
    passed,
    failed: count - passed,
    successRate: passed / count,
    results,
  }
  await writeFile(path.join(outputRoot, 'report.json'), `${JSON.stringify(report, null, 2)}\n`)
  await writeFile(path.join(outputRoot, 'results.jsonl'), `${results.map(result => JSON.stringify(result)).join('\n')}\n`)
  console.log(`完成: ${passed}/${count} 成功；报告 ${path.join(outputRoot, 'report.json')}`)
  if (passed !== count) process.exitCode = 1
}

main().catch(error => {
  console.error(`运行失败: ${error.message}`)
  process.exitCode = 1
})
