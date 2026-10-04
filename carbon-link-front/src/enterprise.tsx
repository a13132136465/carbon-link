import { useState } from 'react'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import type { User } from './types'
import { Icon } from './ui'
import { WalletPage, MarketPage, RetirementsPage } from './pages'
import { AccountPage } from './account'
import { ApplicationPage } from './application'

const enterpriseNav = [
  ['/', 'spark', '申报中心'],
  ['/wallet', 'wallet', '碳资产'],
  ['/market', 'market', '交易市场'],
  ['/retirements', 'retire', '注销凭证'],
] as const

export function EnterpriseModule({user,onLogout,notify}:{user:User;onLogout:()=>void;notify:(message:string,type?:'success'|'error')=>void}) {
  const [menuOpen,setMenuOpen]=useState(false)
  return <div className="enterprise-shell">
    <div className="enterprise-atmosphere" aria-hidden="true"><i/><i/></div>
    <header className="enterprise-header">
      <NavLink className="enterprise-brand" to="/" onClick={()=>setMenuOpen(false)}><span className="brand-mark"><Icon name="leaf" size={21}/></span><span><b>CarbonLink</b><small>企业碳管理平台</small></span></NavLink>
      <button className="enterprise-menu" aria-label="打开导航" onClick={()=>setMenuOpen(value=>!value)}><Icon name={menuOpen?'close':'menu'}/></button>
      <nav className={menuOpen?'open':''}>{enterpriseNav.map(([to,icon,label])=><NavLink key={to} to={to} end={to==='/'} onClick={()=>setMenuOpen(false)}><Icon name={icon} size={17}/>{label}</NavLink>)}</nav>
      <div className="enterprise-user"><span className="enterprise-online"><i/>服务在线</span><NavLink to="/account" className="enterprise-profile"><span className="avatar small">{user.display_name.slice(0,1).toUpperCase()}</span><span><b>{user.display_name}</b><small>企业账户</small></span></NavLink><button title="退出登录" onClick={onLogout}><Icon name="logout" size={18}/></button></div>
    </header>
    {menuOpen&&<button className="enterprise-overlay" aria-label="关闭导航" onClick={()=>setMenuOpen(false)}/>} 
    <main className="enterprise-content"><Routes>
      <Route path="/" element={<ApplicationPage user={user} notify={notify}/>}/>
      <Route path="/wallet" element={<div className="enterprise-page"><WalletPage notify={notify}/></div>}/>
      <Route path="/market" element={<div className="enterprise-page"><MarketPage user={user} notify={notify}/></div>}/>
      <Route path="/retirements" element={<div className="enterprise-page"><RetirementsPage user={user} notify={notify}/></div>}/>
      <Route path="/account" element={<div className="enterprise-page"><AccountPage user={user} notify={notify}/></div>}/>
      <Route path="*" element={<Navigate to="/"/>}/>
    </Routes></main>
  </div>
}
