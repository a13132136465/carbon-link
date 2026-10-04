import { getBytes, HDNodeWallet, JsonRpcProvider, Wallet } from 'ethers'

function messageBytes(value) {
  return typeof value === 'string' && value.startsWith('0x') ? getBytes(value) : String(value)
}

async function buildWallet(config) {
  const provider = config.rpcUrl ? new JsonRpcProvider(config.rpcUrl) : null
  let wallet
  if (config.privateKey) wallet = new Wallet(config.privateKey)
  else if (config.mnemonic) wallet = HDNodeWallet.fromPhrase(config.mnemonic, undefined, `m/44'/60'/0'/0/${config.index ?? 0}`)
  else wallet = Wallet.createRandom()
  return { signer: provider ? wallet.connect(provider) : wallet, provider }
}

export async function installTestWallet(page, config) {
  const { signer, provider } = await buildWallet(config)
  const address = await signer.getAddress()
  const providerChainId = provider ? Number((await provider.getNetwork()).chainId) : null
  const chainId = Number(config.chainId ?? providerChainId ?? 31337)
  const writesEnabled = Boolean(config.allowWrites)

  await page.exposeFunction('__carbonLinkWalletRpc', async ({ method, params = [] }) => {
    if (method === 'eth_accounts' || method === 'eth_requestAccounts') return [address]
    if (method === 'eth_chainId') return `0x${chainId.toString(16)}`
    if (method === 'net_version') return String(chainId)
    if (method === 'wallet_switchEthereumChain') {
      const requested = Number.parseInt(params[0]?.chainId ?? '0x0', 16)
      if (requested !== chainId) throw new Error(`测试钱包仅允许 Chain ID ${chainId}`)
      return null
    }
    if (method === 'personal_sign') {
      const payload = params.find(value => String(value).toLowerCase() !== address.toLowerCase())
      return signer.signMessage(messageBytes(payload ?? ''))
    }
    if (method === 'eth_signTypedData_v4') {
      const raw = params.find(value => String(value).trim().startsWith('{'))
      if (!raw) throw new Error('缺少 EIP-712 typed data')
      const typed = JSON.parse(raw)
      const types = { ...typed.types }
      delete types.EIP712Domain
      return signer.signTypedData(typed.domain, types, typed.message)
    }
    if (method === 'eth_sendTransaction') {
      if (!writesEnabled) throw new Error('测试钱包默认禁止链上写入；显式传入 --allow-chain-writes 才会发送交易')
      if (!provider) throw new Error('发送交易需要 --wallet-rpc-url')
      const transaction = { ...(params[0] ?? {}) }
      if (transaction.from && transaction.from.toLowerCase() !== address.toLowerCase()) throw new Error('交易 from 与测试钱包地址不匹配')
      delete transaction.from
      const response = await signer.sendTransaction(transaction)
      return response.hash
    }
    if (!provider) throw new Error(`测试钱包没有 RPC，无法执行 ${method}`)
    return provider.send(method, params)
  })

  await page.addInitScript(({ address: injectedAddress, chainId: injectedChainId }) => {
    const listeners = new Map()
    const ethereum = {
      isMetaMask: false,
      isCarbonLinkTestWallet: true,
      selectedAddress: injectedAddress,
      chainId: `0x${injectedChainId.toString(16)}`,
      request: request => window.__carbonLinkWalletRpc(request),
      on(event, listener) {
        const current = listeners.get(event) ?? []
        current.push(listener)
        listeners.set(event, current)
        return ethereum
      },
      removeListener(event, listener) {
        listeners.set(event, (listeners.get(event) ?? []).filter(item => item !== listener))
        return ethereum
      },
    }
    Object.defineProperty(window, 'ethereum', { value: ethereum, configurable: false })
  }, { address, chainId })

  return { address, chainId, writesEnabled }
}
