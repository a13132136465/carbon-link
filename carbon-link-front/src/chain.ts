import { BrowserProvider, Contract, parseEther, parseUnits } from 'ethers'
import { json, request } from './api'
import type { ChainConfig, User } from './types'

declare global { interface Window { ethereum?: { request(args:{method:string;params?:unknown[]}):Promise<unknown> } } }

export const CREDIT_SCALE = 10_000n
export const CREDIT_ABI = [
  'function balanceOf(address account,uint256 id) view returns (uint256)',
  'function isApprovedForAll(address account,address operator) view returns (bool)',
  'function setApprovalForAll(address operator,bool approved)',
  'function retire(uint256 batchId,uint256 amount,bytes32 beneficiaryHash,bytes32 evidenceDigest) returns (uint256)',
]
export const MARKET_ABI = [
  'function nextListingId() view returns (uint256)',
  'function activeListingCount() view returns (uint256)',
  'function activeListingIdAt(uint256 index) view returns (uint256)',
  'function listings(uint256) view returns (address seller,uint256 tokenId,uint256 remainingAmount,uint256 pricePerCreditWei,bool active)',
  'function createListing(uint256 tokenId,uint256 amount,uint256 pricePerCreditWei) returns (uint256)',
  'function buy(uint256 listingId,uint256 amount) payable',
  'function cancel(uint256 listingId)',
]

export async function chainConfig(){ return request<ChainConfig>('/chain/config') }

export async function wallet(user?:User){
  if(!window.ethereum) throw new Error('未检测到 EVM 钱包，请安装 MetaMask 或兼容钱包')
  const config=await chainConfig()
  if(!config.enabled||!config.credit_contract_address) throw new Error('链上资产尚未配置')
  const provider=new BrowserProvider(window.ethereum)
  await provider.send('eth_requestAccounts',[])
  const network=await provider.getNetwork()
  if(network.chainId!==BigInt(config.chain_id)){
    try{await provider.send('wallet_switchEthereumChain',[{chainId:`0x${config.chain_id.toString(16)}`}])}
    catch{throw new Error(`请将钱包切换到 ${config.network}（Chain ID ${config.chain_id}）`)}
  }
  const signer=await provider.getSigner(),address=await signer.getAddress()
  if(user?.wallet_address&&address.toLowerCase()!==user.wallet_address.toLowerCase()) throw new Error(`当前钱包与账号绑定地址不一致：${user.wallet_address}`)
  return {config,provider,signer,address,
    credits:new Contract(config.credit_contract_address,CREDIT_ABI,signer),
    market:config.marketplace_contract_address?new Contract(config.marketplace_contract_address,MARKET_ABI,signer):null}
}

export async function linkWallet(user:User){
  const current=await wallet()
  const challenge=await request<{address:string;message:string}>('/wallet/challenge',json({address:current.address}))
  const signature=await current.signer.signMessage(challenge.message)
  return request<User>('/wallet/link',json({address:current.address,signature}))
}

export const creditAmount=(value:string)=>parseUnits(value,4)
export const nativePrice=(value:string)=>parseEther(value)
export const paymentFor=(amount:bigint,price:bigint)=>(amount*price+CREDIT_SCALE-1n)/CREDIT_SCALE
