import { FormEvent, useEffect, useState } from 'react'
import { NavLink, Navigate, Route, Routes, useLocation, useSearchParams } from 'react-router-dom'
import { json, request } from './api'
import type { User } from './types'
import { Icon } from './ui'
import { AuditPage, BlockchainPage, DashboardPage, MarketPage, ProjectsPage, RetirementsPage, WalletPage } from './pages'
import { AccountPage, UsersPage } from './account'
import { EnterpriseModule } from './enterprise'
import type { Retirement } from './types'
import { date, fmt } from './ui'

type Notice = { id:number; message:string; type:'success'|'error' }

function Login({ onLogin }: { onLogin:(token:string)=>Promise<void> }) {
  const [mode,setMode]=useState<'login'|'register'|'forgot'|'reset'>('login'),[email,setEmail]=useState('admin@example.com'), [password,setPassword]=useState(''),[name,setName]=useState(''),[token,setToken]=useState('')
  const [loading,setLoading]=useState(false), [error,setError]=useState('')
  const submit=async(e:FormEvent)=>{e.preventDefault();setLoading(true);setError('');try{
    if(mode==='register'){await request('/auth/register',json({email,password,display_name:name}));const data=await request<{access_token:string}>('/auth/login',json({email,password}));await onLogin(data.access_token)}
    else if(mode==='forgot'){await request('/auth/password/forgot',json({email}));setError('若账号存在，重置邮件已发送，请检查邮箱。')}
    else if(mode==='reset'){await request('/auth/password/reset',json({token,new_password:password}));setMode('login');setPassword('');setError('密码已重置，请使用新密码登录。')}
    else {const data=await request<{access_token:string}>('/auth/login',json({email,password}));await onLogin(data.access_token)}
  }catch(e){setError(e instanceof Error?e.message:'操作失败')}finally{setLoading(false)}}
  const titles={login:'欢迎回来',register:'创建企业账号',forgot:'找回密码',reset:'设置新密码'}
  return <main className="login-shell">
    <section className="login-visual">
      <div className="brand brand-light"><span className="brand-mark"><Icon name="leaf" size={23}/></span><span>CarbonLink</span></div>
      <div className="visual-copy"><span className="eyebrow light">可信 · 可溯源 · 可持续</span><h1>让每一吨减排，<br/>都清晰可见。</h1><p>从碳项目核证、资产签发到市场交易与注销，构建可信赖的数字碳资产基础设施。</p></div>
      <div className="visual-stats"><div><b>全生命周期</b><span>数字化碳资产管理</span></div><div><b>链上存证</b><span>关键操作透明可追溯</span></div></div>
      <div className="orb orb-one"/><div className="orb orb-two"/><div className="grid-lines"/>
    </section>
    <section className="login-panel"><form className="login-card" onSubmit={submit}>
      <div className="mobile-brand"><span className="brand-mark"><Icon name="leaf"/></span>CarbonLink</div>
      <span className="eyebrow">管理控制台</span><h2>{titles[mode]}</h2><p className="muted">{mode==='login'?'登录以管理您的碳资产与交易。':mode==='register'?'注册后将获得企业用户权限。':mode==='forgot'?'输入账号邮箱以获取重置指引。':'输入重置令牌并设置新密码。'}</p>
      {mode==='register'&&<label>显示名称<input value={name} onChange={e=>setName(e.target.value)} minLength={2} required autoFocus/></label>}
      {mode!=='reset'&&<label>邮箱地址<input type="email" value={email} onChange={e=>setEmail(e.target.value)} placeholder="name@company.com" required autoFocus={mode!=='register'}/></label>}
      {mode==='reset'&&<label>重置令牌<input value={token} onChange={e=>setToken(e.target.value)} required/></label>}
      {(mode==='login'||mode==='register'||mode==='reset')&&<label>{mode==='reset'?'新密码':'密码'}<input type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="至少 10 个字符" minLength={10} required/></label>}
      {error&&<div className="form-error">{error}</div>}
      <button className="btn btn-primary btn-wide" disabled={loading}>{loading?'正在处理…':mode==='login'?'登录控制台':mode==='register'?'注册并登录':mode==='forgot'?'发送重置指引':'确认重置'}<Icon name="arrow" size={18}/></button>
      <div className="auth-links">{mode==='login'?<><button type="button" onClick={()=>setMode('register')}>注册账号</button><button type="button" onClick={()=>setMode('forgot')}>忘记密码</button></>:<button type="button" onClick={()=>{setMode('login');setError('')}}>返回登录</button>}<a href="/verify">验证注销证书</a></div>
    </form></section>
  </main>
}

const nav=[
  ['/', 'dashboard','总览'],['/projects','project','申报管理'],['/wallet','wallet','资产台账'],['/market','market','交易管理'],['/retirements','retire','注销管理'],
] as const

function ManagementLayout({user,onLogout,notify}:{user:User;onLogout:()=>void;notify:(m:string,t?:'success'|'error')=>void}) {
  const [open,setOpen]=useState(false), location=useLocation()
  const admin=user.role==='admin'
  const title:Record<string,string>={'/':'运营总览','/projects':'申报管理','/wallet':'资产台账','/market':'交易管理','/retirements':'注销管理','/blockchain':'链上存证','/audit':'审计日志','/users':'用户管理','/account':'账号设置'}
  const items=[...nav,...(admin?[['/users','audit','用户管理'],['/blockchain','chain','链上存证'],['/audit','audit','审计日志']] as const:[]),['/account','wallet','账号设置'] as const]
  return <div className="app-shell">
    {open&&<div className="mobile-overlay" onClick={()=>setOpen(false)}/>}<aside className={`sidebar ${open?'open':''}`}>
      <div className="brand"><span className="brand-mark"><Icon name="leaf" size={22}/></span><span>CarbonLink</span></div>
      <nav>{items.map(([to,icon,label])=><NavLink key={to} to={to} end={to==='/'} onClick={()=>setOpen(false)}><Icon name={icon}/><span>{label}</span></NavLink>)}</nav>
      <div className="sidebar-foot"><div className="user-mini"><div className="avatar">{user.display_name.slice(0,1).toUpperCase()}</div><div><strong>{user.display_name}</strong><span>{user.role==='admin'?'系统管理员':user.role==='verifier'?'核证机构':'企业用户'}</span></div></div><button className="icon-btn" title="退出登录" onClick={onLogout}><Icon name="logout"/></button></div>
    </aside>
    <main className="workspace"><header className="topbar"><button className="menu-btn" onClick={()=>setOpen(true)}><Icon name="menu"/></button><div><span className="breadcrumb">CarbonLink / 管理控制台</span><h1>{title[location.pathname]||'管理控制台'}</h1></div><div className="top-actions"><span className="network"><i/>服务在线</span><div className="avatar small">{user.display_name.slice(0,1).toUpperCase()}</div></div></header>
      <div className="page"><Routes>
        <Route path="/" element={<DashboardPage user={user}/>}/><Route path="/projects" element={<ProjectsPage user={user} notify={notify}/>}/><Route path="/wallet" element={<WalletPage notify={notify}/>}/><Route path="/market" element={<MarketPage user={user} notify={notify}/>}/><Route path="/retirements" element={<RetirementsPage user={user} notify={notify}/>}/>
        <Route path="/users" element={admin?<UsersPage current={user} notify={notify}/>:<Navigate to="/"/>}/><Route path="/blockchain" element={admin?<BlockchainPage/>:<Navigate to="/"/>}/><Route path="/audit" element={admin?<AuditPage/>:<Navigate to="/"/>}/><Route path="/account" element={<AccountPage user={user} notify={notify}/>}/><Route path="*" element={<Navigate to="/"/>}/>
      </Routes></div>
    </main>
  </div>
}

function CertificateVerify(){const [query,setQuery]=useState(''),[record,setRecord]=useState<Retirement|null>(null),[error,setError]=useState('');const verify=(e:FormEvent)=>{e.preventDefault();setError('');request<Retirement>(`/retirements/${encodeURIComponent(query)}`).then(setRecord).catch(e=>{setRecord(null);setError(e.message)})};return <main className="public-shell"><div className="public-card"><span className="eyebrow">PUBLIC VERIFICATION</span><h1>注销证书公开核验</h1><p className="muted">无需登录，输入完整证书编号即可核验 CarbonLink 注销记录。</p><form className="search-box" onSubmit={verify}><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="CLR-YYYYMMDD-..." required/><button>立即核验</button></form>{error&&<div className="form-error">{error}</div>}{record&&<article className="certificate"><header><span className="cert-seal"><Icon name="check"/></span><span>VERIFIED RETIREMENT</span></header><h3>{fmt(record.quantity)} <small>tCO₂e</small></h3><p>已代表 <b>{record.beneficiary}</b> 永久注销</p><p>{record.reason}</p><div className="cert-line"/><footer><div><span>证书编号</span><b>{record.certificate_no}</b></div><div><span>注销时间</span><b>{date(record.retired_at)}</b></div></footer></article>}<div className="auth-links"><a href="/">返回管理控制台</a></div></div></main>}

function ResetPassword(){const [params]=useSearchParams(),[token,setToken]=useState(params.get('token')||''),[password,setPassword]=useState(''),[message,setMessage]=useState(''),[error,setError]=useState('');const submit=(e:FormEvent)=>{e.preventDefault();setError('');request('/auth/password/reset',json({token,new_password:password})).then(()=>setMessage('密码已重置，现在可以返回登录。')).catch(e=>setError(e.message))};return <main className="public-shell"><form className="public-card" onSubmit={submit}><span className="eyebrow">ACCOUNT RECOVERY</span><h1>重置登录密码</h1><label>重置令牌<input value={token} onChange={e=>setToken(e.target.value)} required/></label><label>新密码<input type="password" minLength={10} value={password} onChange={e=>setPassword(e.target.value)} required/></label>{error&&<div className="form-error">{error}</div>}{message&&<div className="verified-banner"><div><b>{message}</b></div></div>}<button className="btn btn-primary btn-wide">确认重置</button><div className="auth-links"><a href="/">返回登录</a></div></form></main>}

export default function App(){
  const [user,setUser]=useState<User|null>(null),[loading,setLoading]=useState(true),[notices,setNotices]=useState<Notice[]>([])
  const load=async()=>{try{setUser(await request<User>('/users/me'))}catch{setUser(null)}finally{setLoading(false)}}
  useEffect(()=>{if(localStorage.getItem('carbonlink_token'))load();else setLoading(false);const unauthorized=()=>setUser(null);window.addEventListener('carbonlink:unauthorized',unauthorized);return()=>window.removeEventListener('carbonlink:unauthorized',unauthorized)},[])
  const login=async(token:string)=>{localStorage.setItem('carbonlink_token',token);await load()}
  const logout=()=>{localStorage.removeItem('carbonlink_token');setUser(null)}
  const notify=(message:string,type:'success'|'error'='success')=>{const id=Date.now();setNotices(n=>[...n,{id,message,type}]);setTimeout(()=>setNotices(n=>n.filter(x=>x.id!==id)),3500)}
  if(loading)return <div className="splash"><span className="brand-mark"><Icon name="leaf"/></span><span>CarbonLink</span></div>
  return <><Routes><Route path="/verify" element={<CertificateVerify/>}/><Route path="/reset-password" element={<ResetPassword/>}/><Route path="*" element={user?(user.role==='member'?<EnterpriseModule user={user} onLogout={logout} notify={notify}/>:<ManagementLayout user={user} onLogout={logout} notify={notify}/>):<Login onLogin={login}/>}/></Routes><div className="toast-stack">{notices.map(n=><div className={`toast ${n.type}`} key={n.id}><Icon name={n.type==='success'?'check':'close'} size={18}/>{n.message}</div>)}</div></>
}
