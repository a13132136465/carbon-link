import type { ReactNode } from 'react'

export function Icon({ name, size = 20 }: { name:string; size?:number }) {
  const paths: Record<string, ReactNode> = {
    dashboard: <><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/></>,
    project: <><path d="M4 21V8l8-5 8 5v13"/><path d="M9 21v-8h6v8M3 21h18"/></>,
    wallet: <><path d="M3 7h16a2 2 0 0 1 2 2v10H5a2 2 0 0 1-2-2V7Z"/><path d="M3 7a3 3 0 0 1 3-3h11v3M16 12h5v4h-5a2 2 0 0 1 0-4Z"/></>,
    market: <><path d="M4 19V9M10 19V5M16 19v-7M22 19H2"/><path d="m3 8 6-4 6 6 6-5"/></>,
    retire: <><path d="M12 22c5-3 8-7 8-12V5l-8-3-8 3v5c0 5 3 9 8 12Z"/><path d="m9 12 2 2 4-5"/></>,
    chain: <><path d="M10 13a5 5 0 0 0 7.5.5l2-2a5 5 0 0 0-7-7l-1.1 1"/><path d="M14 11a5 5 0 0 0-7.5-.5l-2 2a5 5 0 0 0 7 7l1.1-1"/></>,
    audit: <><path d="M9 5H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4"/><path d="M9 15h3l8-8a2.1 2.1 0 0 0-3-3l-8 8v3ZM16 5l3 3"/></>,
    logout: <><path d="M10 17l5-5-5-5M15 12H3"/><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/></>,
    plus: <path d="M12 5v14M5 12h14"/>, search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>,
    arrow: <path d="m9 18 6-6-6-6"/>, close: <path d="M18 6 6 18M6 6l12 12"/>,
    leaf: <><path d="M20 4C10 4 4 10 4 20c6 0 12-2 16-16Z"/><path d="M4 20c3-5 7-8 12-11"/></>,
    copy: <><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></>,
    upload: <><path d="M12 16V4m0 0-4 4m4-4 4 4"/><path d="M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4"/></>,
    file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6M8 13h8M8 17h6"/></>,
    spark: <><path d="m12 3 1.2 4.1L17 9l-3.8 1.9L12 15l-1.2-4.1L7 9l3.8-1.9L12 3Z"/><path d="m5 15 .7 2.3L8 18.5l-2.3 1.2L5 22l-.7-2.3L2 18.5l2.3-1.2L5 15ZM19 2l.5 1.5L21 4l-1.5.5L19 6l-.5-1.5L17 4l1.5-.5L19 2Z"/></>,
    send: <><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></>,
    menu: <path d="M4 6h16M4 12h16M4 18h16"/>, check: <path d="m5 12 4 4L19 6"/>,
  }
  return <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>
}

export function Status({ value }: { value:string }) {
  const labels:Record<string,string> = {draft:'草稿',pending:'待审核',approved:'已通过',rejected:'已驳回',open:'交易中',filled:'已成交',cancelled:'已撤销',confirmed:'已确认',prepared:'已签名',submitted:'已广播',failed:'失败'}
  return <span className={`status status-${value}`}>{labels[value] || value}</span>
}

export function Empty({ title='暂无数据', text='当前还没有可显示的记录。' }: {title?:string;text?:string}) {
  return <div className="empty"><div className="empty-mark"><Icon name="leaf" size={28}/></div><strong>{title}</strong><p>{text}</p></div>
}

export function Modal({ title, children, onClose }: {title:string;children:ReactNode;onClose:()=>void}) {
  return <div className="modal-backdrop" onMouseDown={e => e.target === e.currentTarget && onClose()}><section className="modal"><header><div><span className="eyebrow">CARBONLINK</span><h2>{title}</h2></div><button className="icon-btn" onClick={onClose}><Icon name="close"/></button></header>{children}</section></div>
}

export function Pagination({page,total,pageSize,onChange}:{page:number;total:number;pageSize:number;onChange:(page:number)=>void}) {
  const pages=Math.max(1,Math.ceil(total/pageSize))
  if(total<=pageSize)return null
  return <div className="pagination"><button disabled={page===0} onClick={()=>onChange(page-1)}>上一页</button><span>第 {page+1} / {pages} 页 · 共 {total} 条</span><button disabled={page+1>=pages} onClick={()=>onChange(page+1)}>下一页</button></div>
}

export const fmt = (value:string|number, digits=2) => Number(value).toLocaleString('zh-CN',{minimumFractionDigits:digits,maximumFractionDigits:digits})
export const date = (value:string) => new Intl.DateTimeFormat('zh-CN',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}).format(new Date(value))
export const short = (value:string, head=8) => value ? `${value.slice(0,head)}…${value.slice(-4)}` : '—'
