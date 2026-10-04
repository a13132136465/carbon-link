import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { installTestWallet } from './wallet-provider.mjs'

export class AgentSession {
  constructor({ browser, baseUrl, artifactDir, identity, timeoutMs, video, wallet }) {
    this.browser = browser
    this.baseUrl = baseUrl
    this.artifactDir = artifactDir
    this.identity = identity
    this.timeoutMs = timeoutMs
    this.video = video
    this.wallet = wallet
    this.events = []
    this.context = null
    this.page = null
  }

  async start() {
    await mkdir(this.artifactDir, { recursive: true })
    this.context = await this.browser.newContext({
      baseURL: this.baseUrl,
      locale: 'zh-CN',
      timezoneId: 'Asia/Hong_Kong',
      viewport: { width: 1440, height: 1000 },
      recordVideo: this.video ? { dir: path.join(this.artifactDir, 'video') } : undefined,
    })
    await this.context.tracing.start({ screenshots: true, snapshots: true, sources: true })
    this.page = await this.context.newPage()
    if (this.wallet) {
      this.walletInfo = await installTestWallet(this.page, this.wallet)
      this.events.push({ type: 'wallet', address: this.walletInfo.address, chainId: this.walletInfo.chainId, writesEnabled: this.walletInfo.writesEnabled, at: new Date().toISOString() })
    }
    this.page.setDefaultTimeout(this.timeoutMs)
    this.page.on('console', message => {
      if (message.type() === 'error') this.events.push({ type: 'browser-console', text: message.text(), at: new Date().toISOString() })
    })
    this.page.on('pageerror', error => {
      this.events.push({ type: 'browser-error', text: error.message, at: new Date().toISOString() })
    })
  }

  async step(name, action) {
    const startedAt = Date.now()
    process.stdout.write(`[${this.identity.id}] ${name} ... `)
    try {
      const value = await action()
      const durationMs = Date.now() - startedAt
      this.events.push({ type: 'step', name, status: 'passed', durationMs, at: new Date().toISOString() })
      process.stdout.write(`OK (${durationMs}ms)\n`)
      return value
    } catch (error) {
      const durationMs = Date.now() - startedAt
      this.events.push({ type: 'step', name, status: 'failed', durationMs, error: error.message, at: new Date().toISOString() })
      process.stdout.write(`FAILED (${durationMs}ms)\n`)
      throw error
    }
  }

  async finish(status) {
    if (!this.context) return
    if (status === 'failed' && this.page && !this.page.isClosed()) {
      await this.page.screenshot({ path: path.join(this.artifactDir, 'failure.png'), fullPage: true }).catch(() => {})
    }
    await this.context.tracing.stop({ path: path.join(this.artifactDir, 'trace.zip') }).catch(() => {})
    await this.context.close().catch(() => {})
  }
}
