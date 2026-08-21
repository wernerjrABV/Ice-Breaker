import { Snowflake } from 'lucide-react'
import './Header.css'

function Header() {
  return (
    <header className="header">
      <span className="header-avatar" aria-hidden="true"><Snowflake size={22} /></span>
      <span className="header-brand">
        <strong className="header-title">CoolCare</strong>
        <span className="header-subtitle">Assistente de manutenção</span>
      </span>
      <span className="header-presence"><i aria-hidden="true" /> Online</span>
    </header>
  )
}

export default Header
