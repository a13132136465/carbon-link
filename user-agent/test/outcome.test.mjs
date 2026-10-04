import test from 'node:test'
import assert from 'node:assert/strict'
import { resolveOutcome } from '../src/goal-agent.mjs'

test('blocked goals are never successful', async () => {
  const result = await resolveOutcome({}, { action: 'blocked', reason: 'Service unavailable' })
  assert.equal(result.completed, false)
  assert.equal(result.status, 'blocked')
})

test('finish requires visible evidence', async () => {
  const page = { getByText: () => ({ first: () => ({ isVisible: async () => false }) }) }
  const result = await resolveOutcome(page, { action: 'finish', target: 'Success', reason: 'Done' })
  assert.equal(result.completed, false)
  assert.equal(result.status, 'failed')
})
