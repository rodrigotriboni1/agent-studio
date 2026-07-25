import { useState, type ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Bot,
  Workflow,
  Settings,
  PanelLeftClose,
  PanelLeft,
  Sparkles,
  Building2,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { setTenantId } from '@/lib/api'

interface NavItem {
  to: string
  label: string
  icon: typeof LayoutDashboard
  end?: boolean
}

const NAV: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/agents', label: 'Agents', icon: Bot },
  { to: '/workflows', label: 'Workflows', icon: Workflow },
  { to: '/settings', label: 'Settings', icon: Settings },
]

const TENANTS = ['default', 'acme', 'globex']

export default function AppShell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)
  const [tenant, setTenant] = useState('default')

  function onTenantChange(value: string) {
    setTenant(value)
    setTenantId(value)
  }

  return (
    <div className="flex min-h-screen bg-background">
      {/* Sidebar */}
      <aside
        className={cn(
          'sticky top-0 flex h-screen flex-col bg-sidebar text-sidebar-foreground transition-[width] duration-200',
          collapsed ? 'w-[68px]' : 'w-64',
        )}
      >
        {/* Brand */}
        <div className="flex h-16 items-center gap-2.5 px-4">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-sidebar-accent text-white">
            <Sparkles className="h-5 w-5" />
          </div>
          {!collapsed && (
            <div className="leading-tight">
              <div className="text-sm font-semibold tracking-tight">Agent Studio</div>
              <div className="text-[11px] text-sidebar-muted">governed · MCP-native</div>
            </div>
          )}
        </div>

        {/* Nav */}
        <nav className="flex-1 space-y-1 px-3 py-4">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              title={collapsed ? label : undefined}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                  collapsed && 'justify-center px-0',
                  isActive
                    ? 'bg-sidebar-accent text-white shadow-sm'
                    : 'text-sidebar-muted hover:bg-white/5 hover:text-sidebar-foreground',
                )
              }
            >
              <Icon className="h-[18px] w-[18px] shrink-0" />
              {!collapsed && <span>{label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* Tenant + collapse */}
        <div className="space-y-3 border-t border-sidebar-border p-3">
          {!collapsed && (
            <label className="block">
              <span className="mb-1 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-sidebar-muted">
                <Building2 className="h-3 w-3" /> Tenant
              </span>
              <select
                value={tenant}
                onChange={(e) => onTenantChange(e.target.value)}
                className="w-full rounded-md border border-sidebar-border bg-white/5 px-2 py-1.5 text-sm text-sidebar-foreground outline-none focus:border-sidebar-accent"
              >
                {TENANTS.map((t) => (
                  <option key={t} value={t} className="text-foreground">
                    {t}
                  </option>
                ))}
              </select>
            </label>
          )}
          <button
            onClick={() => setCollapsed((c) => !c)}
            className={cn(
              'flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-sidebar-muted transition-colors hover:bg-white/5 hover:text-sidebar-foreground',
              collapsed && 'justify-center px-0',
            )}
            title={collapsed ? 'Expand' : 'Collapse'}
          >
            {collapsed ? <PanelLeft className="h-[18px] w-[18px]" /> : <PanelLeftClose className="h-[18px] w-[18px]" />}
            {!collapsed && <span>Collapse</span>}
          </button>
        </div>
      </aside>

      {/* Content */}
      <div className="flex min-w-0 flex-1 flex-col">
        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-6xl px-6 py-8 lg:px-10">{children}</div>
        </main>
      </div>
    </div>
  )
}
