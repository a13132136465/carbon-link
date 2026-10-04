import assert from 'node:assert/strict'
import test from 'node:test'
import { createIdentity, createMarketProfile } from '../src/data-factory.mjs'

test('generates varied but reproducible business profiles', () => {
  const options = { batchId: 'batch-a', seed: 'demo-seed' }
  const first = Array.from({ length: 40 }, (_, index) => createIdentity({ ...options, index }))
  const repeated = Array.from({ length: 40 }, (_, index) => createIdentity({ ...options, index }))
  assert.deepEqual(first, repeated)
  assert.ok(new Set(first.map(item => item.company)).size > 20)
  assert.ok(new Set(first.map(item => item.project.projectType)).size >= 4)
  assert.ok(new Set(first.map(item => item.project.region)).size >= 7)
  assert.equal(new Set(first.map(item => item.email)).size, first.length)
  assert.equal(new Set(first.map(item => item.project.name)).size, first.length)
  for (const identity of first) {
    assert.match(identity.project.description, new RegExp(identity.project.region))
    assert.match(identity.documents.methodology, new RegExp(identity.project.methodology))
    assert.ok(Number(identity.project.estimatedTonnes) > 0)
  }
})

test('generates varied reproducible market profiles with a realistic order-book mix', () => {
  const options = { seed: 'market-seed', issueBase: 320, orderBase: 24, priceBase: 8.5 }
  const profiles = Array.from({ length: 10 }, (_, index) => createMarketProfile({ ...options, index }))
  const repeated = Array.from({ length: 10 }, (_, index) => createMarketProfile({ ...options, index }))
  assert.deepEqual(profiles, repeated)
  assert.equal(new Set(profiles.map(item => item.price)).size, profiles.length)
  assert.ok(new Set(profiles.map(item => item.issueQuantity)).size >= 7)
  assert.ok(new Set(profiles.map(item => item.orderQuantity)).size >= 7)
  assert.deepEqual(new Set(profiles.map(item => item.behavior.side)), new Set(['sell', 'buy']))
  assert.ok(profiles.some(item => Number(item.fillQuantity) === 0))
  assert.ok(profiles.some(item => Number(item.fillQuantity) > 0 && Number(item.fillQuantity) < Number(item.orderQuantity)))
  assert.ok(profiles.some(item => Number(item.fillQuantity) === Number(item.orderQuantity)))
  assert.ok(new Set(profiles.map(item => item.vintageYear)).size >= 3)
  for (const profile of profiles) {
    assert.ok(Number(profile.issueQuantity) >= Number(profile.orderQuantity))
    assert.ok(Number(profile.orderQuantity) >= Number(profile.fillQuantity))
    assert.ok(Number(profile.price) > 0)
  }
})
