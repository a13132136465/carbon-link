import { useEffect, useRef, useState, type FormEvent } from 'react'
import { idempotencyKey, json, request, requestPage } from './api'
import type { Holding, Listing, Trade, User } from './types'
import { date as formatDate, Empty, fmt, Modal, Pagination, short, Status } from './ui'
import './market.css'

type Notify = (message: string, type?: 'success' | 'error') => void
type Instrument = { batch_id: string; name: string; region: string; vintage: number; methodology: string; serial_prefix: string; currencies: string[] }
type Tape = { id: string; price: string; quantity: string; time: string }
type Snapshot = {
  as_of: string; available_quantity: string
  asks: { price: string; quantity: string; cumulative: string; orders: number }[]
  ticker: { last: string | null; high: string | null; low: string | null; volume: string; amount: string; count: number }
  trades: Tape[]
}
type Quote = { quantity: string; remaining_quantity: string; total_amount: string; average_price: string | null; fills: number; executable: boolean }
const message = (error: unknown) => error instanceof Error ? error.message : '请求失败，请重试'
// SQLite strips timezone metadata; persisted timestamps are always UTC.
const date = (value: string) => formatDate(/(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`)
const Loader = () => <div className="loading" role="status" aria-label="正在加载市场"><span /><span /><span /></div>

export function MarketPage({ user, notify }: { user: User; notify: Notify }) {
  const [instruments, setInstruments] = useState<Instrument[]>([])
  const [batch, setBatch] = useState('')
  const [currency, setCurrency] = useState('CNY')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    let active = true
    setLoading(true); setError('')
    request<Instrument[]>('/market/instruments').then(items => {
      if (active) { setInstruments(items); setBatch(current => items.some(i => i.batch_id === current) ? current : items[0]?.batch_id || '') }
    }).catch(e => { if (active) setError(message(e)) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [retry])
  const instrument = instruments.find(i => i.batch_id === batch)
  return <section className="dex">
    <header className="dex-heading"><div><span className="eyebrow">CARBON EXCHANGE</span><h2>碳额度交易市场</h2><p>从核证资产到即时交割，让每一笔交易清晰可见。</p></div><span className="dex-tag">按批次交易 · tCO₂e</span></header>
    {error && <div role="alert" className="form-error">{error} <button onClick={() => setRetry(n => n + 1)}>重新加载</button></div>}
    {loading ? <Loader /> : !instruments.length ? !error && <Empty title="暂无已发行碳额度" text="完成项目核证与额度发行后，即可在这里挂单交易。" /> : <>
      <div className="dex-selector"><label>交易批次<select aria-label="交易批次" value={batch} onChange={e => setBatch(e.target.value)}>{instruments.map(i => <option key={i.batch_id} value={i.batch_id}>{i.name} · {i.vintage} · {i.serial_prefix}</option>)}</select></label><label>计价币种<select value={currency} onChange={e => setCurrency(e.target.value)}>{[...new Set(['CNY', 'USD', 'EUR', ...(instrument?.currencies || [])])].map(c => <option key={c}>{c}</option>)}</select></label><div><strong>{instrument?.region}</strong><small>{instrument?.methodology} · {short(batch)}</small></div></div>
      <TradingDesk key={`${batch}:${currency}`} batch={batch} currency={currency} user={user} notify={notify} />
    </>}
  </section>
}

function TradingDesk({ batch, currency, user, notify }: { batch: string; currency: string; user: User; notify: Notify }) {
  const [data, setData] = useState<{ snapshot: Snapshot; holdings: Holding[]; orders: { data: Listing[]; total: number }; trades: { data: Trade[]; total: number } } | null>(null)
  const [error, setError] = useState('')
  const [refresh, setRefresh] = useState(0)
  const [page, setPage] = useState(0)
  const [tab, setTab] = useState<'orders' | 'trades' | 'assets'>('orders')
  const [side, setSide] = useState<'buy' | 'sell'>('buy')
  const [quantity, setQuantity] = useState('')
  const [price, setPrice] = useState('')
  const [policy, setPolicy] = useState<'FOK' | 'IOC'>('FOK')
  const [quote, setQuote] = useState<Quote | null>(null)
  const [busy, setBusy] = useState(false)
  const [confirmSell, setConfirmSell] = useState(false)
  const pending = useRef(false)
  const intent = useRef({ body: '', key: '' })
  const scope = `batch_id=${encodeURIComponent(batch)}&currency=${currency}`
  useEffect(() => {
    let active = true
    let timer: ReturnType<typeof setTimeout>
    const load = async () => {
      try {
        const [snapshot, holdings, orders, trades] = await Promise.all([
          request<Snapshot>(`/market/snapshot?${scope}`), request<Holding[]>('/wallet/holdings'),
          requestPage<Listing[]>(`/market/orders?${scope}&limit=10&offset=${page * 10}`),
          requestPage<Trade[]>(`/market/trades?${scope}&limit=10&offset=${page * 10}`),
        ])
        if (active) { setData({ snapshot, holdings, orders, trades }); setError('') }
      } catch (e) { if (active) setError(message(e)) }
      finally { if (active) timer = setTimeout(load, 5000) }
    }
    void load()
    return () => { active = false; clearTimeout(timer) }
  }, [scope, page, refresh])
  const holding = data?.holdings.find(h => h.batch_id === batch)
  const available = Number(holding?.quantity || 0) - Number(holding?.locked_quantity || 0)
  const snapshot = data?.snapshot
  const best = snapshot?.asks[0]?.price
  const resetQuote = () => { setQuote(null); setConfirmSell(false) }
  async function action(fn: () => Promise<void>) {
    if (pending.current) return
    pending.current = true; setBusy(true)
    try { await fn() } catch (e) { notify(message(e), 'error') }
    finally { pending.current = false; setBusy(false) }
  }
  const body = { batch_id: batch, currency, quantity, max_unit_price: price, time_in_force: policy }
  function preview(e: FormEvent) {
    e.preventDefault()
    if (side === 'sell') { setConfirmSell(true); return }
    void action(async () => { setQuote(await request<Quote>('/market/quote', json(body))) })
  }
  async function submit() {
    await action(async () => {
      const payload = side === 'buy' ? body : { batch_id: batch, currency, quantity, unit_price: price }
      const signature = `${side}:${JSON.stringify(payload)}`
      // Preserve the key across uncertain network failures for this exact intent.
      if (intent.current.body !== signature) intent.current = { body: signature, key: idempotencyKey() }
      const options = { ...json(payload), headers: { 'Idempotency-Key': intent.current.key } }
      if (side === 'buy') {
        const result = await request<{ filled_quantity: string; remaining_quantity: string; total_amount: string }>('/market/execute', options)
        notify(`已交割 ${fmt(result.filled_quantity, 4)} tCO₂e，应付 ${fmt(result.total_amount)} ${currency}${Number(result.remaining_quantity) > 0 ? `；未成交 ${fmt(result.remaining_quantity, 4)} tCO₂e 已取消` : ''}`)
      } else { await request('/market/listings', options); notify('卖出委托已发布，额度已锁定') }
      intent.current = { body: '', key: '' }; resetQuote(); setQuantity(''); setRefresh(n => n + 1)
    })
  }
  if (!data) return error ? <div className="form-error" role="alert">行情加载失败：{error}<button onClick={() => setRefresh(n => n + 1)}>重试</button></div> : <Loader />
  return <>
    <div className="dex-status" role="status"><span className={error ? 'dex-stale' : ''}>● {error ? `更新失败，显示上次数据：${error}` : '每 5 秒更新'}</span><span>更新于 {date(data.snapshot.as_of)}</span></div>
    <div className="dex-ticker">{[
      ['最新成交价', snapshot!.ticker.last === null ? '—' : fmt(snapshot!.ticker.last), `${currency} / tCO₂e`],
      ['24h 最高 / 最低', `${snapshot!.ticker.high === null ? '—' : fmt(snapshot!.ticker.high)} / ${snapshot!.ticker.low === null ? '—' : fmt(snapshot!.ticker.low)}`, currency],
      ['24h 成交量', fmt(snapshot!.ticker.volume, 4), 'tCO₂e'],
      ['在售额度', fmt(snapshot!.available_quantity, 4), 'tCO₂e'],
    ].map(([label, value, unit]) => <div key={label}><span>{label}</span><strong>{value}</strong><small>{unit}</small></div>)}</div>
    <div className="dex-grid">
      <section className="dex-panel dex-book"><header><h3>卖盘深度</h3><span>价格优先 · 前 12 档</span></header><div className="dex-book-head"><span>价格 ({currency})</span><span>数量</span><span>累计 tCO₂e</span></div>
        {snapshot!.asks.length ? snapshot!.asks.map(level => <button className="dex-level" key={level.price} disabled={busy} title={`${level.orders} 笔委托，点击填入最高买价`} onClick={() => { setSide('buy'); setPrice(level.price); resetQuote() }}><i style={{ width: `${Number(level.cumulative) / Number(snapshot!.asks.at(-1)!.cumulative) * 100}%` }} /><b>{fmt(level.price)}</b><span>{fmt(level.quantity, 4)}</span><span>{fmt(level.cumulative, 4)}</span></button>) : <Empty title="暂无卖出委托" text="发布卖单，为该批次提供流动性。" />}
        <p className="dex-note">同价按挂单时间成交。点击价格可填入买入上限；买单立即执行，未成交部分不挂单。</p>
      </section>
      <section className="dex-panel dex-chart"><header><h3>成交价格走势</h3><span>本平台真实成交 · 最近 60 笔</span></header><PriceChart trades={snapshot!.trades} currency={currency} /><div className="dex-chart-foot"><span>24h 成交额 <b>{fmt(snapshot!.ticker.amount)} {currency}</b></span><span>{snapshot!.ticker.count} 笔成交</span></div></section>
      <section className="dex-panel dex-ticket"><header><h3>交易碳额度</h3><span>{currency} / tCO₂e</span></header><div className="dex-tabs">{(['buy', 'sell'] as const).map(s => <button disabled={busy} className={side === s ? 'active' : ''} key={s} onClick={() => { setSide(s); resetQuote() }}>{s === 'buy' ? '买入' : '卖出'}</button>)}</div>
        <form onSubmit={preview}><fieldset disabled={busy}><label>{side === 'buy' ? '最高买入单价' : '卖出限价'}<div className="dex-price-input"><input aria-label={side === 'buy' ? '最高买入单价' : '卖出限价'} type="number" min="0.01" step="0.01" required value={price} onChange={e => { setPrice(e.target.value); resetQuote() }} /><span>{currency}</span></div></label>{best && <button type="button" className="dex-link" onClick={() => { setPrice(best); resetQuote() }}>使用最优卖价 {fmt(best)}</button>}
          <label>数量 (tCO₂e)<input type="number" min="0.0001" step="0.0001" max={side === 'sell' ? available : undefined} required value={quantity} onChange={e => { setQuantity(e.target.value); resetQuote() }} /></label>
          {side === 'sell' ? <><div className="dex-percent">{[25, 50, 75, 100].map(p => <button type="button" key={p} onClick={() => { setQuantity((Math.floor(available * p / 100 * 10000 + 1e-7) / 10000).toFixed(4)); resetQuote() }}>{p}%</button>)}</div><p className="dex-note">可出售 {fmt(available, 4)} tCO₂e</p></> : <label>成交方式<select value={policy} onChange={e => { setPolicy(e.target.value as 'FOK' | 'IOC'); resetQuote() }}><option value="FOK">全部成交，否则取消</option><option value="IOC">允许部分成交，余量取消</option></select></label>}
          <button className="btn btn-primary btn-wide" disabled={busy || !!error || (side === 'sell' && available <= 0)}>{busy ? '处理中…' : side === 'buy' ? '预览买入' : '预览卖出'}</button>
        </fieldset></form><p className="dex-note">成交后交割碳额度并记录应付金额，资金需另行结算。</p>
      </section>
      <section className="dex-panel dex-tape"><header><h3>最近成交</h3><span>价格 / 数量 / 时间</span></header><div className="dex-tape-list">{snapshot!.trades.length ? snapshot!.trades.slice(0, 12).map(t => <div key={t.id}><b>{fmt(t.price)}</b><span>{fmt(t.quantity, 4)}</span><time>{date(t.time)}</time></div>) : <Empty title="尚无成交" text="实际成交后显示价格与数量。" />}</div></section>
    </div>
    <section className="dex-panel dex-history"><div className="dex-tabs">{([['orders', '我的委托'], ['trades', '我的成交'], ['assets', '批次资产']] as const).map(([key, label]) => <button key={key} className={tab === key ? 'active' : ''} onClick={() => { setTab(key); setPage(0) }}>{label}</button>)}</div>
      {tab === 'assets' ? <div className="dex-assets"><div><span>持有总量</span><strong>{fmt(holding?.quantity || 0, 4)}</strong></div><div><span>挂单锁定</span><strong>{fmt(holding?.locked_quantity || 0, 4)}</strong></div><div><span>可用额度</span><strong>{fmt(available, 4)} <small>tCO₂e</small></strong></div></div> : <><div className="dex-table-wrap"><table><thead><tr><th>时间</th><th>{tab === 'orders' ? '委托状态' : '方向'}</th><th>单价 ({currency})</th><th>数量 (tCO₂e)</th><th>{tab === 'orders' ? '剩余数量' : `应付金额 (${currency})`}</th><th>操作</th></tr></thead><tbody>{tab === 'orders' ? data.orders.data.map(o => <tr key={o.id}><td>{date(o.created_at)}</td><td><Status value={o.status} /></td><td>{fmt(o.unit_price)}</td><td>{fmt(o.quantity, 4)}</td><td>{fmt(o.remaining_quantity, 4)}</td><td>{o.status === 'open' && <button className="dex-link" disabled={busy} onClick={() => void action(async () => { await request(`/market/listings/${o.id}`, { method: 'DELETE' }); notify('委托已撤销，剩余额度已解锁'); setRefresh(n => n + 1) })}>撤单</button>}</td></tr>) : data.trades.data.map(t => <tr key={t.id}><td>{date(t.traded_at)}</td><td>{t.buyer_id === user.id ? '买入' : '卖出'}</td><td>{fmt(t.unit_price)}</td><td>{fmt(t.quantity, 4)}</td><td>{fmt(t.total_amount)}</td><td>已交割</td></tr>)}</tbody></table></div>{!(tab === 'orders' ? data.orders.data.length : data.trades.data.length) && <Empty title={tab === 'orders' ? '暂无委托' : '暂无成交记录'} text="此处仅显示您在当前批次和币种下的记录。" />}<Pagination page={page} total={tab === 'orders' ? data.orders.total : data.trades.total} pageSize={10} onChange={setPage} /></>}
    </section>
    {(quote || confirmSell) && <Modal title={side === 'buy' ? '确认买入碳额度' : '确认卖出委托'} onClose={() => { if (!busy) resetQuote() }}><div className="dex-confirm"><p>批次：{batch}</p><p>{side === 'buy' ? '最高单价' : '卖出限价'}：{price} {currency} / tCO₂e</p><p>委托数量：{quantity} tCO₂e</p>{quote && <><p>预计成交：{fmt(quote.quantity, 4)} tCO₂e · {quote.fills} 笔</p><p>预计应付：<b>{fmt(quote.total_amount)} {currency}</b></p><p>未成交余量：{fmt(quote.remaining_quantity, 4)} tCO₂e</p><p>{policy === 'FOK' ? '全部成交，否则整笔取消。' : '允许部分成交，未成交余量取消。'}</p><p className="muted">预览不锁定盘口，确认时重新撮合，单价不会超过您的上限。</p>{!quote.executable && <p role="alert" className="form-error">当前流动性不足以满足所选成交方式，请调整数量或价格。</p>}</>}<button className="btn btn-primary btn-wide" disabled={busy || (side === 'buy' && !quote?.executable)} onClick={() => void submit()}>{busy ? '提交中…' : side === 'buy' ? '确认买入并交割' : '确认挂单并锁定额度'}</button></div></Modal>}
  </>
}

function PriceChart({ trades, currency }: { trades: Tape[]; currency: string }) {
  if (!trades.length) return <Empty title="等待第一笔成交" text="价格走势仅使用当前碳批次的实际成交数据。" />
  const chronological = [...trades].reverse()
  const prices = chronological.map(t => Number(t.price))
  const min = Math.min(...prices), max = Math.max(...prices), spread = max - min || Math.max(max * .02, .01)
  const points = prices.map((p, i) => `${50 + i / Math.max(1, prices.length - 1) * 490},${170 - (p - min) / spread * 120}`)
  return <div className="dex-price-chart"><svg viewBox="0 0 580 230" role="img" aria-label={`最近 ${trades.length} 笔成交价格，最低 ${min}，最高 ${max} ${currency}`}>
    {[50, 110, 170].map(y => <line key={y} x1="50" x2="550" y1={y} y2={y} stroke="currentColor" opacity=".12" />)}
    <text x="4" y="54">{fmt(min + spread)}</text><text x="4" y="174">{fmt(min)}</text>
    <path d={`M ${points.join(' L ')} L 540,185 L 50,185 Z`} fill="currentColor" opacity=".06" />
    <polyline points={points.join(' ')} fill="none" stroke="currentColor" strokeWidth="2.5" />
    {chronological.map((t, i) => <circle key={t.id} cx={points[i].split(',')[0]} cy={points[i].split(',')[1]} r="3" fill="currentColor"><title>{date(t.time)} · {t.price} {currency} · {t.quantity} tCO₂e</title></circle>)}
    <text x="50" y="216">{date(chronological[0].time)}</text><text x="540" y="216" textAnchor="end">{date(chronological.at(-1)!.time)}</text>
  </svg><p className="dex-note">按成交顺序展示，悬停数据点查看详情。</p></div>
}
