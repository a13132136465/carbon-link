import assert from 'node:assert/strict'
import test from 'node:test'
import { chromium } from 'playwright'
import { verifyMessage } from 'ethers'
import { installTestWallet } from '../src/wallet-provider.mjs'

test('injects an EIP-1193 wallet that signs messages and blocks writes by default', async () => {
  const browser = await chromium.launch()
  try {
    const page = await browser.newPage()
    const info = await installTestWallet(page, { chainId: 31337, index: 0, allowWrites: false })
    await page.goto('data:text/html,<h1>wallet test</h1>')
    const accounts = await page.evaluate(() => window.ethereum.request({ method: 'eth_requestAccounts' }))
    assert.deepEqual(accounts, [info.address])
    assert.equal(await page.evaluate(() => window.ethereum.request({ method: 'eth_chainId' })), '0x7a69')
    const signature = await page.evaluate(address => window.ethereum.request({ method: 'personal_sign', params: ['hello', address] }), info.address)
    assert.equal(verifyMessage('hello', signature), info.address)
    await assert.rejects(
      page.evaluate(address => window.ethereum.request({ method: 'eth_sendTransaction', params: [{ from: address, to: address, value: '0x0' }] }), info.address),
      /默认禁止链上写入/,
    )
  } finally {
    await browser.close()
  }
})
