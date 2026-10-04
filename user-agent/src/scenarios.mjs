import { runGoalAgent } from './goal-agent.mjs'
import { AgentSession } from './agent-session.mjs'

const pdfBuffer = Buffer.from('%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF')

async function register(session) {
  const { page, identity } = session
  await session.step('打开 CarbonLink', async () => {
    await page.goto('/', { waitUntil: 'domcontentloaded' })
    await page.getByRole('heading', { name: '欢迎回来' }).waitFor()
  })
  await session.step('注册企业用户', async () => {
    await page.getByRole('button', { name: '注册账号' }).click()
    await page.getByLabel('显示名称').fill(identity.displayName)
    await page.getByLabel('邮箱地址').fill(identity.email)
    await page.getByLabel('密码').fill(identity.password)
    await page.getByRole('button', { name: '注册并登录' }).click()
    await page.getByText('Carbon Copilot', { exact: true }).first().waitFor()
  })
}

async function login(session, email, password, expectedHeading) {
  const { page } = session
  await session.step(`登录 ${email}`, async () => {
    await page.goto('/', { waitUntil: 'domcontentloaded' })
    await page.getByLabel('邮箱地址').fill(email)
    await page.getByLabel('密码').fill(password)
    await page.getByRole('button', { name: '登录控制台' }).click()
    await page.getByRole('heading', { name: expectedHeading }).waitFor()
  })
}

async function credentialsExist(session) {
  const response = await session.context.request.post('/api/v1/auth/login', {
    data: { email: session.identity.email, password: session.identity.password },
  })
  return response.ok()
}

async function ensureEnterpriseAccount(session, resume) {
  if (resume && await credentialsExist(session)) {
    await login(session, session.identity.email, session.identity.password, '从一个想法，到一份可信申报。')
  } else {
    await register(session)
  }
}

async function linkWallet(session) {
  const { page } = session
  if (!session.walletInfo) throw new Error('链上场景必须为企业用户注入测试钱包')
  await session.step('绑定企业测试钱包', async () => {
    await page.goto('/account', { waitUntil: 'domcontentloaded' })
    await page.getByRole('heading', { name: '账号设置' }).waitFor()
    await page.getByRole('button', { name: /连接并绑定钱包|重新验证钱包/ }).click()
    await waitForTransactionOutcome(page, '钱包地址已通过签名验证并绑定', '钱包绑定失败', session.timeoutMs)
  })
}

async function loadProjectState(session) {
  return session.page.evaluate(async projectName => {
    const token = localStorage.getItem('carbonlink_token')
    const headers = { Authorization: `Bearer ${token}` }
    const [projectResponse, batchResponse] = await Promise.all([
      fetch('/api/v1/projects?mine=true&limit=100', { headers }),
      fetch('/api/v1/credits/batches?limit=100', { headers }),
    ])
    if (!projectResponse.ok || !batchResponse.ok) throw new Error('读取项目恢复状态失败')
    const project = (await projectResponse.json()).find(item => item.name === projectName) ?? null
    const batch = project ? (await batchResponse.json()).find(item => item.project_id === project.id) ?? null : null
    return { project, batch }
  }, session.identity.projectName)
}

async function createProject(session) {
  const { page, identity } = session
  const project = identity.project
  await session.step('打开项目辅助表单', async () => {
    await page.goto('/', { waitUntil: 'domcontentloaded' })
    await page.getByRole('button', { name: /使用辅助表单新建项目/ }).click()
    await page.getByRole('heading', { name: '创建企业项目档案' }).waitFor()
  })
  await session.step('填写并创建项目', async () => {
    await page.getByLabel('项目名称').fill(project.name)
    await page.getByLabel('项目类型').selectOption(project.projectType)
    await page.getByLabel('所在地区').fill(project.region)
    await page.getByLabel('核证方法学').fill(project.methodology)
    await page.getByLabel('预计减排量（tCO₂e）').fill(project.estimatedTonnes)
    await page.getByLabel('项目说明').fill(project.description)
    await page.getByRole('button', { name: '创建并继续' }).click()
    await page.getByText('项目档案已创建', { exact: true }).waitFor()
    await page.getByRole('heading', { name: identity.projectName }).waitFor()
  })
}

async function uploadDocumentsAndSubmit(session) {
  const { page, identity } = session
  const documentRequirements = [
    ['上传项目设计文件（PDD）', identity.documents.projectDesign],
    ['上传项目权属或授权证明', identity.documents.ownership],
    ['上传方法学适用性说明', identity.documents.methodology],
    ['上传监测计划与基线数据', identity.documents.monitoring],
  ]
  await session.step('打开审核材料', async () => {
    await page.getByRole('button', { name: '查看档案与材料' }).click()
    await page.getByRole('heading', { name: '审核材料', exact: true }).waitFor()
  })
  for (const [label, fileName] of documentRequirements) {
    await session.step(`上传 ${fileName}`, async () => {
      await page.getByLabel(label).setInputFiles({ name: fileName, mimeType: 'application/pdf', buffer: pdfBuffer })
      await page.getByText(fileName, { exact: true }).waitFor()
    })
  }
  await session.step('提交平台审核', async () => {
    const submit = page.getByRole('button', { name: /提交平台审核/ })
    await submit.waitFor()
    if (await submit.isDisabled()) throw new Error('材料上传完成后，提交按钮仍不可用')
    await submit.click()
    await page.getByText('项目已提交平台审核', { exact: true }).waitFor()
  })
}

async function verifyProject(session) {
  const { page, identity } = session
  return session.step('通过 API 校验最终状态', async () => {
    const result = await page.evaluate(async projectName => {
      const token = localStorage.getItem('carbonlink_token')
      const response = await fetch('/api/v1/projects?mine=true&limit=100', {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!response.ok) throw new Error(`项目查询失败: HTTP ${response.status}`)
      const projects = await response.json()
      return projects.find(project => project.name === projectName) ?? null
    }, identity.projectName)
    if (!result) throw new Error('未找到刚创建的项目')
    if (result.status !== 'pending') throw new Error(`项目状态应为 pending，实际为 ${result.status}`)
    return { projectId: result.id, projectStatus: result.status }
  })
}

async function reviewAndIssue(admin, projectName, quantity, vintageYear, { needsReview, needsIssue }) {
  const { page } = admin
  const selectFilter = async (label, status) => {
    const loaded = page.waitForResponse(response => {
      const url = new URL(response.url())
      return url.pathname.endsWith('/api/v1/projects') && url.searchParams.get('status') === status && response.ok()
    })
    await page.getByRole('button', { name: label, exact: true }).click()
    await loaded
  }
  const findRow = async () => {
    for (let pageIndex = 0; pageIndex < 30; pageIndex += 1) {
      const row = page.locator('tr').filter({ hasText: projectName })
      if (await row.count()) return row.first()
      const next = page.getByRole('button', { name: '下一页' })
      if (!await next.count() || await next.isDisabled()) break
      const loaded = page.waitForResponse(response => response.url().includes('/api/v1/projects?') && response.ok())
      await next.click()
      await loaded
    }
    throw new Error(`管理端列表中未找到项目：${projectName}`)
  }
  if (needsReview) await admin.step('审核并通过项目', async () => {
    await page.goto('/projects', { waitUntil: 'domcontentloaded' })
    await selectFilter('待审核', 'pending')
    const row = await findRow()
    await row.getByRole('button', { name: '审核' }).click()
    await page.getByLabel('审核结论').selectOption('true')
    await page.getByLabel('审核意见').fill('自动化核证 Agent：材料类别齐全，字段与申报信息一致，同意进入 Fuji 测试网签发流程。')
    await page.getByRole('button', { name: '确认审核' }).click()
    await page.getByText('审核结果已保存', { exact: true }).waitFor()
  })
  if (needsIssue) await admin.step('签发碳额度', async () => {
    if (!needsReview) await page.goto('/projects', { waitUntil: 'domcontentloaded' })
    await selectFilter('已通过', 'approved')
    const row = await findRow()
    await row.getByRole('button', { name: '签发' }).click()
    await page.getByLabel('核证年份').fill(String(vintageYear))
    await page.getByLabel('签发数量（tCO₂e）').fill(String(quantity))
    await page.getByRole('button', { name: '确认签发' }).click()
    await page.getByText('碳额度已签发', { exact: true }).waitFor()
  })
}

async function waitForTransactionOutcome(page, successText, failurePrefix, timeoutMs) {
  const handle = await page.waitForFunction(expected => {
    const error = document.querySelector('.toast.error')?.textContent?.trim()
    if (error) return { error }
    const success = [...document.querySelectorAll('.toast')]
      .some(node => node.textContent?.trim() === expected)
    return success ? { success: true } : null
  }, successText, { timeout: timeoutMs })
  const outcome = await handle.jsonValue()
  if (outcome.error) throw new Error(`${failurePrefix}：${outcome.error}`)
}

async function waitForMarketBalance(page, minimum, timeoutMs) {
  await page.waitForFunction(expected => {
    const text = document.querySelector('.dex-ticket .dex-balance b')?.textContent ?? ''
    const available = Number.parseFloat(text.replace(/,/g, ''))
    return Number.isFinite(available) && available >= Number(expected)
  }, String(minimum), { timeout: timeoutMs })
}

async function findOrderRow(page, side, price, timeoutMs) {
  const expected = Number(price).toFixed(4)
  const row = page.locator(`.dex-ob-side.${side} .dex-ob-row`).filter({ hasText: expected }).first()
  await row.waitFor({ timeout: timeoutMs })
  return row
}

async function waitForIssuedBatch(session, projectId, timeoutMs) {
  return session.step('等待 Fuji 链上签发确认', async () => {
    const deadline = Date.now() + timeoutMs
    while (Date.now() < deadline) {
      const batch = await session.page.evaluate(async id => {
        const token = localStorage.getItem('carbonlink_token')
        const response = await fetch('/api/v1/credits/batches?limit=100', { headers: { Authorization: `Bearer ${token}` } })
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return (await response.json()).find(item => item.project_id === id && item.chain_batch_id)
      }, projectId)
      if (batch) return batch
      await session.page.waitForTimeout(3_000)
    }
    throw new Error(`等待链上签发超过 ${timeoutMs}ms；请检查 chain-worker 和 Outbox`)
  })
}

async function placeSellOrder(session, batch, price, quantity, timeoutMs) {
  const { page } = session
  await session.step('企业卖方发布链上卖单', async () => {
    await page.goto('/market', { waitUntil: 'domcontentloaded' })
    await page.getByRole('heading', { name: 'CARBON / USDC 统一现货市场' }).waitFor()
    await page.getByRole('button', { name: '卖出', exact: true }).click()
    await page.getByLabel('交付批次').selectOption(String(batch.chain_batch_id))
    await waitForMarketBalance(page, quantity, timeoutMs)
    await page.getByLabel('限价').fill(String(price))
    await page.getByLabel('数量').fill(String(quantity))
    await page.getByRole('button', { name: '卖出 CARBON', exact: true }).click()
    await waitForTransactionOutcome(page, '卖出限价单已上链', '卖单挂单失败', timeoutMs)
  })
}

async function placeBuyOrder(session, price, quantity, timeoutMs) {
  const { page } = session
  await session.step('企业买方发布链上买单', async () => {
    await page.goto('/market', { waitUntil: 'domcontentloaded' })
    await page.getByRole('heading', { name: 'CARBON / USDC 统一现货市场' }).waitFor()
    await page.getByRole('button', { name: '买入', exact: true }).click()
    await waitForMarketBalance(page, Number(price) * Number(quantity), timeoutMs)
    await page.getByLabel('限价').fill(String(price))
    await page.getByLabel('数量').fill(String(quantity))
    await page.getByRole('button', { name: '买入 CARBON', exact: true }).click()
    await waitForTransactionOutcome(page, '买入限价单已上链', '买单挂单失败', timeoutMs)
  })
}

async function fillSellOrder(session, price, quantity, timeoutMs) {
  const { page } = session
  await session.step('企业买方成交卖单', async () => {
    await page.goto('/market', { waitUntil: 'domcontentloaded' })
    await page.getByRole('heading', { name: 'CARBON / USDC 统一现货市场' }).waitFor()
    const row = await findOrderRow(page, 'asks', price, timeoutMs)
    page.once('dialog', dialog => dialog.accept(String(quantity)))
    await row.getByRole('button', { name: '成交' }).click()
    await waitForTransactionOutcome(page, '订单已成交，碳积分与 USDC 已完成原子交割', '卖单成交失败', timeoutMs)
  })
}

async function fillBuyOrder(session, batch, price, quantity, timeoutMs) {
  const { page } = session
  await session.step('企业卖方成交买单', async () => {
    await page.goto('/market', { waitUntil: 'domcontentloaded' })
    await page.getByRole('heading', { name: 'CARBON / USDC 统一现货市场' }).waitFor()
    await page.getByRole('button', { name: '卖出', exact: true }).click()
    await page.getByLabel('交付批次').selectOption(String(batch.chain_batch_id))
    await waitForMarketBalance(page, quantity, timeoutMs)
    const row = await findOrderRow(page, 'bids', price, timeoutMs)
    page.once('dialog', dialog => dialog.accept(String(quantity)))
    await row.getByRole('button', { name: '成交' }).click()
    await waitForTransactionOutcome(page, '订单已成交，碳积分与 USDC 已完成原子交割', '买单成交失败', timeoutMs)
  })
}

async function runFujiMarket(session, config) {
  const { page, identity } = session
  const market = config.marketProfile
  const childSessions = []
  let childStatus = 'passed'
  try {
    await ensureEnterpriseAccount(session, config.resume)
    const sellerFunding = config.funding ? await session.step('为卖方钱包分发 Fuji gas', () => config.funding.fundSeller(session.walletInfo.address)) : null
    await linkWallet(session)
    let state = await loadProjectState(session)
    let project
    if (!state.project) {
      await createProject(session)
      await uploadDocumentsAndSubmit(session)
      project = await verifyProject(session)
      state = await loadProjectState(session)
    } else {
      project = { projectId: state.project.id, projectStatus: state.project.status }
      if (!['pending', 'approved'].includes(state.project.status)) throw new Error(`--resume 暂不支持项目状态 ${state.project.status}`)
      session.events.push({ type: 'resume', resource: 'project', id: state.project.id, status: state.project.status, at: new Date().toISOString() })
    }

    const needsReview = state.project.status === 'pending'
    const needsIssue = !state.batch
    if (needsReview || needsIssue) {
      const admin = new AgentSession({
        browser: session.browser,
        baseUrl: session.baseUrl,
        artifactDir: `${session.artifactDir}/admin`,
        identity: { id: `${identity.id}-admin` },
        timeoutMs: session.timeoutMs,
        video: session.video,
      })
      childSessions.push(admin)
      await admin.start()
      await login(admin, config.adminEmail, config.adminPassword, '运营总览')
      await reviewAndIssue(admin, identity.project.name, market.issueQuantity, market.vintageYear, { needsReview, needsIssue })
    }

    const batch = await waitForIssuedBatch(session, project.projectId, config.chainTimeoutMs)
    let buyer = null
    let buyerFunding = null
    const prepareBuyer = async () => {
      if (buyer) return buyer
      buyer = new AgentSession({
        browser: session.browser,
        baseUrl: session.baseUrl,
        artifactDir: `${session.artifactDir}/buyer`,
        identity: config.buyerIdentity,
        timeoutMs: session.timeoutMs,
        video: session.video,
        wallet: config.buyerWallet,
      })
      childSessions.push(buyer)
      await buyer.start()
      await ensureEnterpriseAccount(buyer, config.resume)
      buyerFunding = config.funding ? await buyer.step('为买方钱包分发 Fuji gas 与 tUSDC', () => config.funding.fundBuyer(buyer.walletInfo.address)) : null
      await linkWallet(buyer)
      return buyer
    }

    if (market.behavior.side === 'sell') {
      await placeSellOrder(session, batch, market.price, market.orderQuantity, config.chainTimeoutMs)
      if (Number(market.fillQuantity) > 0) {
        await fillSellOrder(await prepareBuyer(), market.price, market.fillQuantity, config.chainTimeoutMs)
      }
    } else {
      await placeBuyOrder(await prepareBuyer(), market.price, market.orderQuantity, config.chainTimeoutMs)
      if (Number(market.fillQuantity) > 0) {
        await fillBuyOrder(session, batch, market.price, market.fillQuantity, config.chainTimeoutMs)
      }
    }
    return {
      projectId: project.projectId,
      batchId: batch.id,
      chainBatchId: batch.chain_batch_id,
      seller: session.walletInfo.address,
      buyer: buyer?.walletInfo.address ?? null,
      market,
      sellerFunding,
      buyerFunding,
    }
  } catch (error) {
    childStatus = 'failed'
    throw error
  } finally {
    for (const child of childSessions.reverse()) await child.finish(childStatus)
  }
}

export const scenarios = {
  register: async session => {
    await register(session)
    return { registered: true }
  },
  application: async session => {
    await register(session)
    await createProject(session)
    await uploadDocumentsAndSubmit(session)
    return verifyProject(session)
  },
  goal: (session, config) => runGoalAgent(session, config.goalAgent),
  'fuji-market': (session, config) => runFujiMarket(session, config.fuji),
}
