import { useEffect, useState, type FormEvent } from 'react'
import { formatEther, formatUnits } from 'ethers'
import { request } from './api'
import { creditAmount, nativePrice, paymentFor, wallet } from './chain'
import type { User } from './types'
import { Empty, fmt, short } from './ui'
import './market.css'

type Notify=(message:string,type?:'success'|'error')=>void
type Instrument={batch_id:string;chain_batch_id?:number;name:string;region:string;vintage:number;methodology:string;serial_prefix:string}
type OnChainListing={id:bigint;seller:string;tokenId:bigint;remaining:bigint;price:bigint;active:boolean}

export function MarketPage({user,notify}:{user:User;notify:Notify}){
  const [instruments,setInstruments]=useState<Instrument[]>([]),[batch,setBatch]=useState(''),[listings,setListings]=useState<OnChainListing[]>([])
  const [loading,setLoading]=useState(true),[busy,setBusy]=useState(false)
  const instrument=instruments.find(i=>i.batch_id===batch)
  const load=async()=>{
    setLoading(true)
    try{
      const items=(await request<Instrument[]>('/market/instruments')).filter(i=>i.chain_batch_id)
      setInstruments(items);setBatch(current=>items.some(i=>i.batch_id===current)?current:items[0]?.batch_id||'')
      if(user.wallet_address){
        const {market}=await wallet(user);if(!market)throw new Error('去中心化市场合约尚未部署或配置');const count=Number(await market.activeListingCount()),rows:OnChainListing[]=[]
        const ids=await Promise.all(Array.from({length:count},(_,index)=>market.activeListingIdAt(index)))
        const active=await Promise.all(ids.map(id=>market.listings(id)))
        active.forEach((row,index)=>rows.push({id:BigInt(ids[index]),seller:row.seller,tokenId:BigInt(row.tokenId),remaining:BigInt(row.remainingAmount),price:BigInt(row.pricePerCreditWei),active:row.active}))
        setListings(rows.reverse())
      }
    }catch(e){notify(e instanceof Error?e.message:'读取链上市场失败','error')}finally{setLoading(false)}
  }
  useEffect(()=>{void load()},[user.wallet_address])
  const scoped=listings.filter(l=>instrument?.chain_batch_id===Number(l.tokenId))
  const transact=async(fn:()=>Promise<void>)=>{if(busy)return;setBusy(true);try{await fn();await load()}catch(e){notify(e instanceof Error?e.message:'链上交易失败','error')}finally{setBusy(false)}}
  const sell=(e:FormEvent<HTMLFormElement>)=>{e.preventDefault();const form=e.currentTarget,f=new FormData(form);void transact(async()=>{
    if(!instrument?.chain_batch_id)throw new Error('该批次尚未完成链上签发')
    const {credits,market,config,address}=await wallet(user),amount=creditAmount(String(f.get('quantity'))),price=nativePrice(String(f.get('price')));if(!market||!config.marketplace_contract_address)throw new Error('去中心化市场合约尚未配置')
    if(!await credits.isApprovedForAll(address,config.marketplace_contract_address)){notify('请先在钱包中授权市场合约');await (await credits.setApprovalForAll(config.marketplace_contract_address,true)).wait()}
    await (await market.createListing(instrument.chain_batch_id,amount,price)).wait();notify('卖单已由您的钱包签名并发布到链上');form.reset()
  })}
  const buy=(listing:OnChainListing)=>{const raw=prompt(`输入购买数量（最多 ${formatUnits(listing.remaining,4)} tCO₂e）`);if(!raw)return;void transact(async()=>{
    const {market}=await wallet(user),amount=creditAmount(raw),value=paymentFor(amount,listing.price);if(!market)throw new Error('去中心化市场合约尚未配置')
    await (await market.buy(listing.id,amount,{value})).wait();notify('购买已链上原子结算：资产到账，原生代币已支付给卖方')
  })}
  const cancel=(listing:OnChainListing)=>void transact(async()=>{const {market}=await wallet(user);if(!market)throw new Error('去中心化市场合约尚未配置');await(await market.cancel(listing.id)).wait();notify('卖单已撤销，托管额度已退回您的钱包')})
  return <section className="dex"><header className="dex-heading"><div><span className="eyebrow">DECENTRALIZED CARBON EXCHANGE</span><h2>链上碳额度市场</h2><p>资产由用户钱包持有，挂单、购买与撤单均由用户签名并由合约原子结算。</p></div><span className="dex-tag">自托管 · 原生代币结算</span></header>
    {!user.wallet_address&&<div className="form-error">请先到“账号设置”连接并签名绑定钱包。</div>}
    <div className="dex-selector"><label>链上批次<select value={batch} onChange={e=>setBatch(e.target.value)}>{instruments.map(i=><option value={i.batch_id} key={i.batch_id}>{i.name} · {i.vintage} · #{i.chain_batch_id}</option>)}</select></label>{instrument&&<div><strong>{instrument.region}</strong><small>{instrument.methodology} · {short(instrument.batch_id)}</small></div>}</div>
    {!instrument&&!loading?<Empty title="暂无链上资产" text="项目核证并完成链上签发后即可交易。"/>:<div className="dex-grid">
      <section className="dex-panel dex-ticket"><header><h3>发布链上卖单</h3><span>价格单位：AVAX / tCO₂e</span></header><form onSubmit={sell}><fieldset disabled={busy||!user.wallet_address}><label>卖出数量<input name="quantity" type="number" min="0.0001" step="0.0001" required/></label><label>每吨价格<input name="price" type="number" min="0.000000000000000001" step="any" required/></label><button className="btn btn-primary btn-wide">{busy?'等待钱包确认…':'签名并发布卖单'}</button></fieldset></form><p className="dex-note">首次挂单需先授权市场合约。只有挂单数量进入合约托管，其余资产始终留在您的钱包。</p></section>
      <section className="dex-panel dex-book"><header><h3>链上卖单</h3><span>{scoped.length} 笔有效委托</span></header>{scoped.length?scoped.map(l=><div className="dex-level" key={l.id.toString()}><b>{fmt(formatEther(l.price),6)} AVAX</b><span>{fmt(formatUnits(l.remaining,4),4)} t</span><span>{short(l.seller,6)}</span>{l.seller.toLowerCase()===user.wallet_address?.toLowerCase()?<button className="dex-link" disabled={busy} onClick={()=>cancel(l)}>签名撤单</button>:<button className="dex-link" disabled={busy||!user.wallet_address} onClick={()=>buy(l)}>签名购买</button>}</div>):<Empty title="暂无卖单" text="您可以成为这个批次的第一个卖方。"/>}</section>
    </div>}
    <div className="info-banner"><div><b>结算规则</b><span>买方支付网络原生代币，合约在同一笔交易中把碳额度转给买方并把款项转给卖方；平台不能代替任何一方签名或挪用资产。</span></div></div>
  </section>
}
