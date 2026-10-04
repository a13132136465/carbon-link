import OpenAI from 'openai'

const actionSchema = {
  type: 'object',
  properties: {
    action: { type: 'string', enum: ['click', 'fill', 'select', 'upload_pdf', 'navigate', 'wait', 'finish', 'blocked', 'failed'] },
    target: { type: 'string', description: 'Visible button/link name, form label, text, or same-origin path.' },
    value: { type: 'string', description: 'Text/select value, or empty string when unused.' },
    reason: { type: 'string', description: 'Short explanation of why this is the next action.' },
  },
  required: ['action', 'target', 'value', 'reason'],
  additionalProperties: false,
}

const allowedActions = new Set(actionSchema.properties.action.enum)
const blockedTargets = /删除|移除|修改密码|更新密码|连接并绑定钱包|重新验证钱包|买入|卖出|签名撤单|签发|注销/

function validateAction(action) {
  if (!action || typeof action !== 'object') throw new Error('模型动作不是对象')
  if (!allowedActions.has(action.action)) throw new Error(`模型返回了不允许的动作 ${action.action}`)
  for (const key of ['target', 'value', 'reason']) {
    if (typeof action[key] !== 'string') throw new Error(`模型动作缺少字符串字段 ${key}`)
  }
  if (!['finish', 'blocked', 'failed'].includes(action.action) && blockedTargets.test(action.target)) throw new Error(`安全策略阻止操作：${action.target}`)
  return action
}

function createClient(config) {
  if (!config.apiKey) throw new Error('goal 场景需要 LLM_API_KEY 或 --llm-api-key')
  if (!config.model) throw new Error('goal 场景需要 LLM_MODEL 或 --llm-model')
  return new OpenAI({ apiKey: config.apiKey, baseURL: config.baseUrl || undefined })
}

async function accessiblePageState(page) {
  const snapshot = await page.locator('body').ariaSnapshot()
  return `URL: ${page.url()}\nTITLE: ${await page.title()}\nACCESSIBILITY TREE:\n${snapshot}`.slice(0, 18_000)
}

async function chooseAction(client, model, prompt, state, history) {
  const messages = [
    {
      role: 'system',
      content: [
        'You are a browser acceptance-test agent operating the CarbonLink Chinese web UI.',
        'Choose exactly one safe action that advances the user goal.',
        'Use only visible accessible names and labels from the supplied accessibility tree.',
        'Never invent selectors, run scripts, leave the configured origin, delete data, change passwords, or initiate financial/blockchain transactions.',
        'Use finish only when the goal is visibly achieved; its target must be exact visible success text. Use blocked or failed when the goal cannot be completed, and explain the reason.',
      ].join(' '),
    },
    {
      role: 'user',
      content: `GOAL:\n${prompt}\n\nIDENTITY:\n${JSON.stringify(history.identity)}\n\nRECENT ACTIONS:\n${JSON.stringify(history.actions.slice(-8))}\n\nCURRENT PAGE:\n${state}`,
    },
  ]
  const request = {
    model,
    messages,
    temperature: 0,
    response_format: { type: 'json_schema', json_schema: { name: 'browser_action', strict: true, schema: actionSchema } },
  }
  try {
    const completion = await client.chat.completions.create(request)
    return validateAction(JSON.parse(completion.choices[0].message.content))
  } catch (error) {
    const fallback = await client.chat.completions.create({
      ...request,
      messages: [...messages, { role: 'system', content: 'Return one JSON object matching the requested action schema.' }],
      response_format: { type: 'json_object' },
    })
    const content = fallback.choices[0].message.content
    if (!content) throw new Error(`模型未返回动作：${error.message}`)
    return validateAction(JSON.parse(content))
  }
}

function buttonOrLink(page, name) {
  return page.getByRole('button', { name, exact: true }).or(page.getByRole('link', { name, exact: true })).first()
}

async function performAction(session, action, stepNumber) {
  const { page } = session
  const label = `自主步骤 ${stepNumber}: ${action.action} ${action.target}`
  return session.step(label, async () => {
    switch (action.action) {
      case 'click':
        await buttonOrLink(page, action.target).click()
        break
      case 'fill':
        await page.getByLabel(action.target, { exact: true }).fill(action.value)
        break
      case 'select':
        await page.getByLabel(action.target, { exact: true }).selectOption({ label: action.value }).catch(() => page.getByLabel(action.target, { exact: true }).selectOption(action.value))
        break
      case 'upload_pdf':
        await page.getByLabel(action.target, { exact: true }).setInputFiles({
          name: action.value || 'agent-document.pdf',
          mimeType: 'application/pdf',
          buffer: Buffer.from('%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF'),
        })
        break
      case 'navigate': {
        const target = new URL(action.target, session.baseUrl)
        if (target.origin !== new URL(session.baseUrl).origin) throw new Error('Agent 不允许离开目标站点')
        await page.goto(target.href, { waitUntil: 'domcontentloaded' })
        break
      }
      case 'wait':
        await page.getByText(action.target, { exact: false }).first().waitFor()
        break
      default:
        throw new Error(`不支持动作 ${action.action}`)
    }
    await page.waitForTimeout(150)
  })
}

export async function runGoalAgent(session, config) {
  const client = createClient(config)
  const actions = []
  await session.step('打开 CarbonLink', () => session.page.goto('/', { waitUntil: 'domcontentloaded' }))
  for (let step = 1; step <= config.maxSteps; step += 1) {
    const state = await accessiblePageState(session.page)
    const action = await chooseAction(client, config.model, config.goal, state, { identity: session.identity, actions })
    actions.push(action)
    session.events.push({ type: 'planner', step, action, at: new Date().toISOString() })
    if (['finish', 'blocked', 'failed'].includes(action.action)) {
      return resolveOutcome(session.page, action, { goal: config.goal, steps: actions.length, actions })
    }
    await performAction(session, action, step)
  }
  throw new Error(`达到最大自主步骤 ${config.maxSteps}，目标仍未完成`)
}

export async function resolveOutcome(page, action, detail = {}) {
  if (action.action !== 'finish') {
    return { ...detail, completed: false, status: action.action === 'blocked' ? 'blocked' : 'failed', reason: action.reason }
  }
  const visible = action.target.trim() && await page.getByText(action.target, { exact: true }).first().isVisible()
  if (!visible) return { ...detail, completed: false, status: 'failed', reason: '缺少可见的完成证据' }
  return { ...detail, completed: true, status: 'success', reason: action.reason }
}
