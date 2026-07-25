import { useEffect, useState, type ReactNode } from 'react'
import { Link, NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Bot,
  Workflow,
  Settings,
  PanelLeftClose,
  PanelLeft,
  Sparkles,
  Building2,
  Plus,
  ChevronsUpDown,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { setTenantId, listAgents } from '@/lib/api'

interface NavItem {
  to: string
  label: string
  icon: typeof LayoutDashboard
  end?: boolean
  badge?: number
}

const TENANTS = ['default', 'acme', 'globex']

export default function AppShell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)
  const [tenant, setTenant] = useState('default')
  const [agentCount, setAgentCount] = useState<number | null>(null)

  useEffect(() => {
    void listAgents()
      .then((a) => setAgentCount(a.length))
      .catch(() => setAgentCount(null))
  }, [tenant])

  function onTenantChange(value: string) {
    setTenant(value)
    setTenantId(value)
  }

  const groups: { label: string; items: NavItem[] }[] = [
    { label: 'Overview', items: [{ to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true }] },
    {
      label: 'Build',
      items: [
        { to: '/agents', label: 'Agents', icon: Bot, badge: agentCount ?? undefined },
        { to: '/workflows', label: 'Workflows', icon: Workflow },
      ],
    },
    { label: 'Configure', items: [{ to: '/settings', label: 'Settings', icon: Settings }] },
  ]

  return (
    <div className="flex min-h-screen bg-background">
      <aside
        className={cn(
          'sticky top-0 flex h-screen flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground transition-[width] duration-200',
          collapsed ? 'w-[76px]' : 'w-64',
        )}
      >
        {/* Brand + collapse */}
        <div className={cn('flex h-16 items-center gap-2.5 px-4', collapsed && 'justify-center px-0')}>
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-sm">
            <Sparkles className="h-5 w-5" />
          </div>
          {!collapsed && (
            <div className="min-w-0 flex-1 leading-tight">
              <div className="truncate text-sm font-semibold tracking-tight">Agent Studio</div>
              <div className="truncate text-[11px] text-sidebar-muted">governed · MCP-native</div>
            </div>
          )}
          {!collapsed && (
            <button
              onClick={() => setCollapsed(true)}
              className="rounded-md p-1.5 text-sidebar-muted transition-colors hover:bg-white/5 hover:text-sidebar-foreground"
              title="Collapse sidebar"
            >
              <PanelLeftClose className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Primary action */}
        <div className={cn('px-3 pb-1', collapsed && 'px-0 flex justify-center')}>
          <Link
            to="/agents/new"
            title="New agent"
            className={cn(
              'flex items-center justify-center gap-2 rounded-lg bg-sidebar-accent text-sm font-medium text-white shadow-sm transition-colors hover:bg-indigo-500',
              collapsed ? 'h-9 w-9' : 'h-9 w-full',
            )}
          >
            <Plus className="h-4 w-4" />
            {!collapsed && <span>New agent</span>}
          </Link>
        </div>

        {/* Nav groups */}
        <nav className="flex-1 overflow-y-auto px-3 py-3">
          {groups.map((group, gi) => (
            <div key={group.label} className={cn(gi > 0 && 'mt-5')}>
              {!collapsed && (
                <div className="px-3 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-sidebar-muted/70">
                  {group.label}
                </div>
              )}
              <div className="space-y-0.5">
                {group.items.map(({ to, label, icon: Icon, end, badge }) => (
                  <NavLink
                    key={to}
                    to={to}
                    end={end}
                    title={collapsed ? label : undefined}
                    className={({ isActive }) =>
                      cn(
                        'group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                        collapsed && 'justify-center px-0',
                        isActive
                          ? 'bg-white/10 text-white'
                          : 'text-sidebar-muted hover:bg-white/5 hover:text-sidebar-foreground',
                      )
                    }
                  >
                    {({ isActive }) => (
                      <>
                        {isActive && (
                          <span className="absolute left-0 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-full bg-sidebar-accent" />
                        )}
                        <Icon
                          className={cn(
                            'h-[18px] w-[18px] shrink-0',
                            isActive ? 'text-white' : 'text-sidebar-muted group-hover:text-sidebar-foreground',
                          )}
                        />
                        {!collapsed && <span className="flex-1">{label}</span>}
                        {!collapsed && badge !== undefined && (
                          <span
                            className={cn(
                              'rounded-full px-1.5 py-0.5 text-[10px] font-semibold',
                              isActive ? 'bg-white/20 text-white' : 'bg-white/10 text-sidebar-muted',
                            )}
                          >
                            {badge}
                          </span>
                        )}
                      </>
                    )}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* Tenant + account */}
        <div className="space-y-2 border-t border-sidebar-border p-3">
          {!collapsed ? (
            <div className="relative">
              <Building2 className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-sidebar-muted" />
              <ChevronsUpDown className="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-sidebar-muted" />
              <select
                value={tenant}
                onChange={(e) => onTenantChange(e.target.value)}
                aria-label="Tenant"
                className="w-full appearance-none rounded-lg border border-sidebar-border bg-white/5 py-2 pl-8 pr-8 text-sm font-medium text-sidebar-foreground outline-none transition-colors hover:bg-white/10 focus:border-sidebar-accent"
              >
                {TENANTS.map((t) => (
                  <option key={t} value={t} className="text-foreground">
                    {t}
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <div
              className="mx-auto flex h-9 w-9 items-center justify-center rounded-lg border border-sidebar-border bg-white/5 text-sidebar-muted"
              title={`Tenant: ${tenant}`}
            >
              <Building2 className="h-4 w-4" />
            </div>
          )}

          <div className={cn('flex items-center gap-2.5 rounded-lg p-1.5', collapsed && 'justify-center')}>
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-slate-500 to-slate-700 text-xs font-semibold text-white">
              FT
            </div>
            {!collapsed && (
              <div className="min-w-0 flex-1 leading-tight">
                <div className="truncate text-sm font-medium text-sidebar-foreground">ftriboni</div>
                <div className="truncate text-[11px] text-sidebar-muted">Pro workspace</div>
              </div>
            )}
          </div>

          {collapsed && (
            <button
              onClick={() => setCollapsed(false)}
              className="mx-auto flex h-9 w-9 items-center justify-center rounded-lg text-sidebar-muted transition-colors hover:bg-white/5 hover:text-sidebar-foreground"
              title="Expand sidebar"
            >
              <PanelLeft className="h-4 w-4" />
            </button>
          )}
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
