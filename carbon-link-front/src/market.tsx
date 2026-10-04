import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { MaxUint256, formatUnits } from 'ethers'
import { request } from './api'
import { creditAmount, quoteAmount, readChain, usdcAmount, wallet } from './chain'
import type { User } from './types'
import { date, Empty, fmt, short } from './ui'
import { MarketChart, type ChartTrade } from './market_chart'
import './market.css'

type Notify=(message:string,type?:'success'|'error')=>void
type Instrument={batch_id:string;chain_batch_id?:number;name:string;region:string;vintage:number;methodology:string;serial_prefix:string}
type Side=0|1
type Order={id:bigint;maker:string;tokenId:bigint;remaining:bigint;price:bigint;remainingQuote:bigint;side:Side;active:boolean;createdAt:number}
type Trade={index:number;orderId:bigint;buyer:string;seller:string;tokenId:bigint;amount:bigint;quote:bigint;price:bigint;takerSide:Side;timestamp:number}
type Level={price:bigint;amount:bigint;orders:Order[]}

export function MarketPage({user,notify}:{user:User;notify:Notify}){
  const [instruments,setInstruments]=useState<Instrument[]>([]),[orders,setOrders]=useState<Order[]>([]),[trades,setTrades]=useState<Trade[]>([])
  const [busy,setBusy]=useState(false),[loading,setLoading]=useState(true),[side,setSide]=useState<Side>(0),[price,setPrice]=useState(''),[quantity,setQuantity]=useState(''),[deliveryToken,setDeliveryToken]=useState('')
  const [balances,setBalances]=useState({credit:0n,usdc:0n,lockedCredit:0n,lockedUsdc:0n,byToken:{} as Record<string,bigint>})

  const load=async(silent=false)=>{
    if(!silent)setLoading(true)
    try{
      const [items,chain]=await Promise.all([request<Instrument[]>('/market/instruments'),readChain()])
      const assets=items.filter(item=>item.chain_batch_id)
      setInstruments(assets)
      if(!chain.market)throw new Error('USDC 市场合约尚未部署或配置')
      const [orderCount,tradeCount]=await Promise.all([chain.market.activeOrderCount(),chain.market.tradeCount()])
      const orderIds=await Promise.all(Array.from({length:Number(orderCount)},(_,index)=>chain.market!.activeOrderIdAt(index)))
      const orderRows=await Promise.all(orderIds.map(id=>chain.market!.orders(id)))
      setOrders(orderRows.map((row,index)=>({id:BigInt(orderIds[index]),maker:row.maker,tokenId:BigInt(row.tokenId),remaining:BigInt(row.remainingAmount),price:BigInt(row.pricePerCredit),remainingQuote:BigInt(row.remainingQuote),side:Number(row.side) as Side,active:row.active,createdAt:Number(row.createdAt)})))
      const total=Number(tradeCount),first=Math.max(0,total-200),tradeRows=await Promise.all(Array.from({length:total-first},(_,offset)=>chain.market!.tradeAt(first+offset)))
      setTrades(tradeRows.map((row,index)=>({index:first+index,orderId:BigInt(row.orderId),buyer:row.buyer,seller:row.seller,tokenId:BigInt(row.tokenId),amount:BigInt(row.amount),quote:BigInt(row.quoteAmount),price:BigInt(row.pricePerCredit),takerSide:Number(row.takerSide) as Side,timestamp:Number(row.timestamp)})))
    }catch(error){if(!silent)notify(message(error),'error')}finally{if(!silent)setLoading(false)}
  }
  useEffect(()=>{void load();const timer=setInterval(()=>void load(true),10_000);return()=>clearInterval(timer)},[])

  const asks=useMemo(()=>levels(orders.filter(o=>o.side===1),true),[orders])
  const bids=useMemo(()=>levels(orders.filter(o=>o.side===0),false),[orders])
  const recentTrades=useMemo(()=>[...trades].sort((a,b)=>b.timestamp-a.timestamp),[trades])
  const chartTrades:ChartTrade[]=useMemo(()=>recentTrades.map(t=>({timestamp:t.timestamp,price:Number(formatUnits(t.price,6)),amount:Number(formatUnits(t.amount,4))})),[recentTrades])
  const ticker=useMemo(()=>{
    const day=recentTrades.filter(t=>t.timestamp>=Date.now()/1000-86400),prices=day.map(t=>Number(formatUnits(t.price,6))),volume=day.reduce((sum,t)=>sum+Number(formatUnits(t.amount,4)),0)
    return {last:recentTrades[0]?Number(formatUnits(recentTrades[0].price,6)):null,high:prices.length?Math.max(...prices):null,low:prices.length?Math.min(...prices):null,volume}
  },[recentTrades])

  useEffect(()=>{
    if(!user.wallet_address||!instruments.length)return setBalances({credit:0n,usdc:0n,lockedCredit:0n,lockedUsdc:0n,byToken:{}})
    readChain().then(async chain=>{
      if(!chain.market||!chain.usdc)return
      const tokenRows=await Promise.all(instruments.map(async asset=>[String(asset.chain_batch_id),BigInt(await chain.credits.balanceOf(user.wallet_address,asset.chain_batch_id))] as const))
      const byToken=Object.fromEntries(tokenRows),credit=tokenRows.reduce((sum,row)=>sum+row[1],0n)
      const [usdc,lockedUsdc]=await Promise.all([chain.usdc.balanceOf(user.wallet_address),chain.market.lockedUsdc(user.wallet_address)])
      const lockedCredit=orders.filter(o=>o.side===1&&same(o.maker,user.wallet_address!)).reduce((sum,o)=>sum+o.remaining,0n)
      setBalances({credit,usdc:BigInt(usdc),lockedCredit,lockedUsdc:BigInt(lockedUsdc),byToken})
      setDeliveryToken(current=>byToken[current]>0n?current:tokenRows.find(row=>row[1]>0n)?.[0]||tokenRows[0]?.[0]||'')
    }).catch(()=>undefined)
  },[user.wallet_address,instruments,orders])

  const sellAvailable=balances.byToken[deliveryToken]||0n
  const transact=async(fn:()=>Promise<void>)=>{if(busy)return;setBusy(true);try{await fn();await load(true)}catch(error){notify(message(error),'error')}finally{setBusy(false)}}
  const place=(event:FormEvent<HTMLFormElement>)=>{event.preventDefault();void transact(async()=>{
    const amount=creditAmount(quantity),unitPrice=usdcAmount(price),current=await wallet(user)
    if(!current.market||!current.usdc||!current.config.marketplace_contract_address)throw new Error('USDC 市场尚未配置')
    if(side===0){
      const quote=quoteAmount(amount,unitPrice);if(quote===0n)throw new Error('订单金额过小')
      if(BigInt(await current.usdc.allowance(current.address,current.config.marketplace_contract_address))<quote){notify('请在钱包中授权 USDC');await(await current.usdc.approve(current.config.marketplace_contract_address,MaxUint256)).wait()}
      await(await current.market.createBuyOrder(amount,unitPrice)).wait()
    }else{
      if(!deliveryToken)throw new Error('没有可交付的碳积分')
      if(amount>sellAvailable)throw new Error('所选交付批次余额不足')
      if(!await current.credits.isApprovedForAll(current.address,current.config.marketplace_contract_address)){notify('请在钱包中授权碳积分');await(await current.credits.setApprovalForAll(current.config.marketplace_contract_address,true)).wait()}
      await(await current.market.createSellOrder(BigInt(deliveryToken),amount,unitPrice)).wait()
    }
    notify(`${side===0?'买入':'卖出'}限价单已上链`);setQuantity('')
  })}
  const take=(order:Order)=>{const maximum=formatUnits(order.remaining,4),raw=prompt(`${order.side===1?'买入':'卖出'}数量（最多 ${maximum} tCO₂e）`);if(!raw)return;void transact(async()=>{
    const amount=creditAmount(raw);if(amount>order.remaining)throw new Error('数量超过订单剩余量')
    const current=await wallet(user);if(!current.market||!current.usdc||!current.config.marketplace_contract_address)throw new Error('USDC 市场尚未配置')
    if(order.side===1){
      const quote=quoteAmount(amount,order.price)
      if(BigInt(await current.usdc.allowance(current.address,current.config.marketplace_contract_address))<quote){notify('请在钱包中授权 USDC');await(await current.usdc.approve(current.config.marketplace_contract_address,MaxUint256)).wait()}
      await(await current.market.fillSellOrder(order.id,amount)).wait()
    }else{
      if(!deliveryToken)throw new Error('请先在卖出面板选择交付批次')
      if(amount>sellAvailable)throw new Error('所选交付批次余额不足')
      if(!await current.credits.isApprovedForAll(current.address,current.config.marketplace_contract_address)){notify('请在钱包中授权碳积分');await(await current.credits.setApprovalForAll(current.config.marketplace_contract_address,true)).wait()}
      await(await current.market.fillBuyOrder(order.id,BigInt(deliveryToken),amount)).wait()
    }
    notify('订单已成交，碳积分与 USDC 已完成原子交割')
  })}
  const cancel=(order:Order)=>void transact(async()=>{const current=await wallet(user);if(!current.market)throw new Error('市场尚未配置');await(await current.market.cancel(order.id)).wait();notify('委托已撤销，托管资产已退回钱包')})
  const pick=(order:Order)=>{setSide(order.side===1?0:1);setPrice(formatUnits(order.price,6))}
  const ownOrders=orders.filter(order=>user.wallet_address&&same(order.maker,user.wallet_address))
  const assetName=(tokenId:bigint)=>instruments.find(item=>BigInt(item.chain_batch_id||0)===tokenId)?.serial_prefix||`#${tokenId}`

  return <section className="dex"><header className="dex-heading"><div><span className="eyebrow">CARBON SPOT EXCHANGE</span><h2>CARBON / USDC 统一现货市场</h2><p>所有核证签发的碳积分共享一个订单簿、一个价格和一套市场流动性。</p></div><span className="dex-tag">统一交易对 · USDC 原子结算</span></header>
    {!user.wallet_address&&<div className="form-error">请先到“账号设置”连接并签名绑定钱包，浏览行情不受影响。</div>}
    {!instruments.length&&!loading?<Empty title="暂无可交付碳积分" text="首个项目审批并完成链上签发后，CARBON/USDC 市场即可开始交易。"/>:<div className="dex-workspace">
      <section className="dex-pairbar"><div><span className="pair-seal">C</span><div><strong>CARBON / USDC</strong><small>统一碳积分现货 · {instruments.length} 个合格交付批次</small></div></div><div className="pair-last"><span>最新价</span><b>{ticker.last===null?'—':fmt(ticker.last,4)}</b><small>USDC</small></div><div><span>24h 最高 / 最低</span><b>{ticker.high===null?'—':`${fmt(ticker.high,4)} / ${fmt(ticker.low!,4)}`}</b></div><div><span>24h 成交量</span><b>{fmt(ticker.volume,4)}</b><small>tCO₂e</small></div><div><span>结算资产</span><b>USDC</b><small>链上即时交割</small></div></section>
      <div className="dex-terminal-grid">
        <OrderBook asks={asks} bids={bids} last={ticker.last} disabled={busy||!user.wallet_address} onPick={pick} onTake={take}/>
        <MarketChart pair="CARBON/USDC" trades={chartTrades}/>
        <section className="dex-panel dex-ticket"><header><h3>现货委托</h3><span>限价单 · 钱包签名</span></header><div className="dex-tabs"><button className={side===0?'active buy':''} onClick={()=>setSide(0)}>买入</button><button className={side===1?'active sell':''} onClick={()=>setSide(1)}>卖出</button></div><form onSubmit={place}><fieldset disabled={busy||!user.wallet_address}><div className="dex-balance"><span>可用</span><b>{side===0?`${fmt(formatUnits(balances.usdc,6),2)} USDC`:`${fmt(formatUnits(sellAvailable,4),4)} tCO₂e`}</b></div>{side===1&&<label>交付批次<select className="dex-asset-select" value={deliveryToken} onChange={e=>setDeliveryToken(e.target.value)} required>{instruments.map(asset=><option value={asset.chain_batch_id} key={asset.batch_id}>{asset.serial_prefix} · {asset.vintage} · 可用 {fmt(formatUnits(balances.byToken[String(asset.chain_batch_id)]||0n,4),4)} t</option>)}</select></label>}<label>限价<div className="dex-price-input"><input value={price} onChange={e=>setPrice(e.target.value)} type="number" min="0.000001" step="0.000001" required/><span>USDC</span></div></label><label>数量<div className="dex-price-input"><input value={quantity} onChange={e=>setQuantity(e.target.value)} type="number" min="0.0001" step="0.0001" required/><span>tCO₂e</span></div></label><div className="dex-percent">{[25,50,75,100].map(p=><button type="button" key={p} onClick={()=>{const available=side===0&&Number(price)>0?Number(formatUnits(balances.usdc,6))/Number(price):Number(formatUnits(sellAvailable,4));setQuantity(String(Math.floor(available*p/100*1e4)/1e4))}}>{p}%</button>)}</div><div className="dex-order-total"><span>委托总额</span><b>{price&&quantity?fmt(Number(price)*Number(quantity),2):'—'} USDC</b></div><button className={`btn btn-wide ${side===0?'btn-primary':'btn-sell'}`}>{busy?'等待钱包确认…':`${side===0?'买入':'卖出'} CARBON`}</button></fieldset></form><p className="dex-note">买单接受任意合格批次；卖单所选批次仅用于实际链上交割，不拆分市场价格。</p></section>
        <RecentTrades trades={recentTrades}/>
      </div>
      <section className="dex-panel dex-history"><header><h3>我的当前委托</h3><span>钱包 {user.wallet_address?short(user.wallet_address,7):'未连接'}</span></header>{ownOrders.length?<div className="dex-table-wrap"><table><thead><tr><th>时间</th><th>方向</th><th>价格 (USDC)</th><th>剩余数量</th><th>交付范围</th><th>托管资产</th><th/></tr></thead><tbody>{ownOrders.sort((a,b)=>b.createdAt-a.createdAt).map(order=><tr key={order.id.toString()}><td>{date(new Date(order.createdAt*1000).toISOString())}</td><td className={order.side===0?'positive':'negative'}>{order.side===0?'买入':'卖出'}</td><td>{fmt(formatUnits(order.price,6),4)}</td><td>{fmt(formatUnits(order.remaining,4),4)} t</td><td>{order.side===0?'任意合格批次':assetName(order.tokenId)}</td><td>{order.side===0?`${fmt(formatUnits(order.remainingQuote,6),2)} USDC`:`${fmt(formatUnits(order.remaining,4),4)} t`}</td><td><button className="dex-link" disabled={busy} onClick={()=>cancel(order)}>签名撤单</button></td></tr>)}</tbody></table></div>:<Empty title="暂无当前委托" text="提交限价单后会显示在这里。"/>}</section>
    </div>}
  </section>
}

function OrderBook({asks,bids,last,disabled,onPick,onTake}:{asks:Level[];bids:Level[];last:number|null;disabled:boolean;onPick:(o:Order)=>void;onTake:(o:Order)=>void}){
  const max=Math.max(1,...asks.map(l=>Number(l.amount)),...bids.map(l=>Number(l.amount)))
  const rows=(items:Level[],kind:'ask'|'bid')=>items.map(level=><div className={`dex-ob-row ${kind}`} key={`${kind}-${level.price}`} onClick={()=>onPick(level.orders[0])}><i style={{width:`${Number(level.amount)/max*100}%`}}/><b>{fmt(formatUnits(level.price,6),4)}</b><span>{fmt(formatUnits(level.amount,4),4)}</span><span>{level.orders.length}</span><button disabled={disabled} onClick={event=>{event.stopPropagation();onTake(level.orders[0])}}>成交</button></div>)
  return <section className="dex-panel dex-orderbook"><header><h3>统一订单簿</h3><span>价格优先 · 同价时间优先</span></header><div className="dex-ob-head"><span>价格 (USDC)</span><span>数量 (tCO₂e)</span><span>订单</span><span/></div><div className="dex-ob-side asks">{asks.length?rows([...asks].reverse(),'ask'):<small>暂无卖单</small>}</div><div className="dex-midprice">{last===null?'—':fmt(last,4)} <small>USDC</small></div><div className="dex-ob-side bids">{bids.length?rows(bids,'bid'):<small>暂无买单</small>}</div></section>
}

function RecentTrades({trades}:{trades:Trade[]}){return <section className="dex-panel dex-tape"><header><h3>最近成交</h3><span>全市场链上成交</span></header><div className="dex-tape-head"><span>价格</span><span>数量</span><span>时间</span></div><div className="dex-tape-list">{trades.length?trades.slice(0,30).map(trade=><div key={trade.index} className={trade.takerSide===0?'buy':'sell'}><b>{fmt(formatUnits(trade.price,6),4)}</b><span>{fmt(formatUnits(trade.amount,4),4)}</span><time>{new Date(trade.timestamp*1000).toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit',second:'2-digit'})}</time></div>):<Empty title="暂无成交" text="首笔链上成交后显示。"/>}</div></section>}

function levels(rows:Order[],ascending:boolean):Level[]{const grouped=new Map<bigint,Order[]>();rows.forEach(order=>grouped.set(order.price,[...(grouped.get(order.price)||[]),order]));return [...grouped.entries()].map(([price,orders])=>({price,orders:orders.sort((a,b)=>a.createdAt-b.createdAt),amount:orders.reduce((sum,o)=>sum+o.remaining,0n)})).sort((a,b)=>ascending?(a.price<b.price?-1:1):(a.price>b.price?-1:1)).slice(0,12)}
const same=(a:string,b:string)=>a.toLowerCase()===b.toLowerCase()
const message=(error:unknown)=>error instanceof Error?error.message:'链上交易失败，请重试'
