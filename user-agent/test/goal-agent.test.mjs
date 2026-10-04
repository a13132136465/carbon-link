import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { mkdtemp, rm } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'
import { chromium } from 'playwright'
import { AgentSession } from '../src/agent-session.mjs'
import { runGoalAgent } from '../src/goal-agent.mjs'

const actions = [
  { action: 'click', target: '注册账号', value: '', reason: '打开注册表单' },
  { action: 'fill', target: '显示名称', value: '测试企业', reason: '填写名称' },
  { action: 'fill', target: '邮箱地址', value: 'goal@example.com', reason: '填写邮箱' },
  { action: 'fill', target: '密码', value: 'AgentPassword123!', reason: '填写密码' },
  { action: 'click', target: '注册并登录', value: '', reason: '提交表单' },
  { action: 'finish', target: '注册成功', value: '', reason: '页面显示注册成功' },
]

function listen(server) {
  return new Promise(resolve => server.listen(0, '127.0.0.1', () => resolve(server.address().port)))
}

test('uses structured model actions to complete a browser goal', async () => {
  let actionIndex = 0
  const app = createServer((request, response) => {
    response.setHeader('Content-Type', 'text/html; charset=utf-8')
    response.end(`<!doctype html><button onclick="document.querySelector('form').hidden=false;this.hidden=true">注册账号</button><form hidden onsubmit="event.preventDefault();document.body.innerHTML='<h1>注册成功</h1>'"><label>显示名称<input></label><label>邮箱地址<input></label><label>密码<input type="password"></label><button>注册并登录</button></form>`)
  })
  const model = createServer((request, response) => {
    let body = ''
    request.on('data', chunk => { body += chunk })
    request.on('end', () => {
      JSON.parse(body)
      const action = actions[actionIndex++] ?? actions.at(-1)
      response.setHeader('Content-Type', 'application/json')
      response.end(JSON.stringify({
        id: `mock-${actionIndex}`,
        object: 'chat.completion',
        created: Math.floor(Date.now() / 1000),
        model: 'mock-model',
        choices: [{ index: 0, message: { role: 'assistant', content: JSON.stringify(action) }, finish_reason: 'stop' }],
        usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
      }))
    })
  })
  const [appPort, modelPort] = await Promise.all([listen(app), listen(model)])
  const temp = await mkdtemp(path.join(os.tmpdir(), 'carbon-link-agent-'))
  const browser = await chromium.launch()
  const session = new AgentSession({
    browser,
    baseUrl: `http://127.0.0.1:${appPort}`,
    artifactDir: temp,
    identity: { id: 'goal-test', displayName: '测试企业', email: 'goal@example.com', password: 'AgentPassword123!' },
    timeoutMs: 5_000,
    video: false,
  })
  try {
    await session.start()
    const result = await runGoalAgent(session, {
      goal: '注册一个测试企业账号',
      maxSteps: 8,
      apiKey: 'test-key',
      baseUrl: `http://127.0.0.1:${modelPort}`,
      model: 'mock-model',
    })
    assert.equal(result.completed, true)
    assert.equal(result.steps, 6)
    assert.equal(await session.page.getByRole('heading', { name: '注册成功' }).isVisible(), true)
  } finally {
    await session.finish('passed')
    await browser.close()
    app.close()
    model.close()
    await rm(temp, { recursive: true, force: true })
  }
})
