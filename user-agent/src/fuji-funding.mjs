import { Contract, JsonRpcProvider, NonceManager, parseEther, parseUnits, Wallet } from 'ethers'

const USDC_ABI = [
  'function balanceOf(address) view returns (uint256)',
  'function owner() view returns (address)',
  'function mint(address,uint256)',
  'function transfer(address,uint256) returns (bool)',
]

function amount(value, parser, name) {
  try { return parser(String(value)) } catch { throw new Error(`${name} 数值无效`) }
}

export class FujiFundingManager {
  static async create(config) {
    const manager = new FujiFundingManager(config)
    await manager.preflight()
    return manager
  }

  constructor(config) {
    if (!config.rpcUrl) throw new Error('Fuji 资助需要 BLOCKCHAIN_RPC_URL')
    if (!config.gasPrivateKey) throw new Error('启用 --fund-wallets 时需要 FUJI_FUNDER_PRIVATE_KEY')
    if (!config.usdcAddress) throw new Error('Fuji 资助需要 USDC_CONTRACT_ADDRESS')
    this.provider = new JsonRpcProvider(config.rpcUrl, 43113, { staticNetwork: true })
    this.gasSigner = new NonceManager(new Wallet(config.gasPrivateKey, this.provider))
    this.usdcSigner = config.usdcPrivateKey && config.usdcPrivateKey !== config.gasPrivateKey
      ? new NonceManager(new Wallet(config.usdcPrivateKey, this.provider))
      : this.gasSigner
    this.usdc = new Contract(config.usdcAddress, USDC_ABI, this.usdcSigner)
    this.gasTarget = amount(config.gasPerWallet ?? '0.03', parseEther, 'FUJI_GAS_PER_WALLET')
    this.gasWalletCap = amount(config.maxGasPerWallet ?? '0.08', parseEther, 'FUJI_MAX_GAS_PER_WALLET')
    this.gasBatchCap = amount(config.maxGasPerBatch ?? '1.0', parseEther, 'FUJI_MAX_GAS_PER_BATCH')
    this.usdcTarget = amount(config.usdcPerBuyer ?? '1000', value => parseUnits(value, 6), 'FUJI_USDC_PER_BUYER')
    this.usdcWalletCap = amount(config.maxUsdcPerWallet ?? '5000', value => parseUnits(value, 6), 'FUJI_MAX_USDC_PER_WALLET')
    this.usdcBatchCap = amount(config.maxUsdcPerBatch ?? '50000', value => parseUnits(value, 6), 'FUJI_MAX_USDC_PER_BATCH')
    this.gasDistributed = 0n
    this.usdcDistributed = 0n
    this.queue = Promise.resolve()
  }

  async preflight() {
    const network = await this.provider.getNetwork()
    if (Number(network.chainId) !== 43113) throw new Error(`拒绝资助：RPC Chain ID ${network.chainId} 不是 Fuji 43113`)
    if (this.gasTarget > this.gasWalletCap) throw new Error('每钱包 gas 目标超过安全上限')
    if (this.usdcTarget > this.usdcWalletCap) throw new Error('每钱包 tUSDC 目标超过安全上限')
    const code = await this.provider.getCode(await this.usdc.getAddress())
    if (code === '0x') throw new Error('USDC_CONTRACT_ADDRESS 在 Fuji 上没有合约代码')
    return {
      chainId: 43113,
      gasFunder: await this.gasSigner.getAddress(),
      usdcFunder: await this.usdcSigner.getAddress(),
    }
  }

  assertBatchCapacity(walletCount, buyerCount) {
    if (this.gasTarget * BigInt(walletCount) > this.gasBatchCap) throw new Error('按当前 count 计算的 AVAX 目标超过批次安全上限')
    if (this.usdcTarget * BigInt(buyerCount) > this.usdcBatchCap) throw new Error('按当前 count 计算的 tUSDC 目标超过批次安全上限')
  }

  exclusive(task) {
    const run = this.queue.then(task, task)
    this.queue = run.catch(() => {})
    return run
  }

  ensureGas(address) {
    return this.exclusive(async () => {
      const current = await this.provider.getBalance(address)
      if (current >= this.gasTarget) return { funded: false, amount: '0', transactionHash: null }
      const delta = this.gasTarget - current
      if (this.gasDistributed + delta > this.gasBatchCap) throw new Error('本批次 AVAX 资助将超过 FUJI_MAX_GAS_PER_BATCH')
      const funderBalance = await this.provider.getBalance(await this.gasSigner.getAddress())
      if (funderBalance <= delta) throw new Error('Fuji 资助钱包 AVAX 余额不足')
      const tx = await this.gasSigner.sendTransaction({ to: address, value: delta })
      await tx.wait(1)
      this.gasDistributed += delta
      return { funded: true, amount: delta.toString(), transactionHash: tx.hash }
    })
  }

  ensureUsdc(address) {
    return this.exclusive(async () => {
      const current = BigInt(await this.usdc.balanceOf(address))
      if (current >= this.usdcTarget) return { funded: false, amount: '0', transactionHash: null }
      const delta = this.usdcTarget - current
      if (this.usdcDistributed + delta > this.usdcBatchCap) throw new Error('本批次 tUSDC 资助将超过 FUJI_MAX_USDC_PER_BATCH')
      const signerAddress = (await this.usdcSigner.getAddress()).toLowerCase()
      let tx
      let isMintOwner = false
      try {
        const owner = String(await this.usdc.owner()).toLowerCase()
        isMintOwner = owner === signerAddress
      } catch {
        // Canonical testnet USDC has no Ownable.owner(); use ERC-20 transfer below.
      }
      try {
        if (isMintOwner) {
          tx = await this.usdc.mint(address, delta)
        } else {
          const funderBalance = BigInt(await this.usdc.balanceOf(signerAddress))
          if (funderBalance < delta) throw new Error('USDC 分发钱包余额不足')
          tx = await this.usdc.transfer(address, delta)
        }
      } catch (error) {
        throw new Error(`USDC 分发失败；官方 USDC 需要足够余额，自建 TestUSDC 需要 owner 权限：${error.message}`)
      }
      await tx.wait(1)
      this.usdcDistributed += delta
      return { funded: true, amount: delta.toString(), transactionHash: tx.hash }
    })
  }

  async fundSeller(address) {
    return { gas: await this.ensureGas(address) }
  }

  async fundBuyer(address) {
    const gas = await this.ensureGas(address)
    const usdc = await this.ensureUsdc(address)
    return { gas, usdc }
  }
}
