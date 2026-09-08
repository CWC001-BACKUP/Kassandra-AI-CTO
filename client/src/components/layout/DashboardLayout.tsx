import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { Logo } from '../ui/Logo'
import { useAuth } from '../../context/AuthProvider'
import { Button } from '../ui/Button'
import { dashboardNavItems } from './dashboardNav'
import { MobileBottomNav } from './MobileBottomNav'

export function DashboardLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  const initials = user?.full_name
    ? user.full_name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .slice(0, 2)
        .toUpperCase()
    : 'U'

  return (
    <div className="flex min-h-screen min-h-[100dvh] bg-[var(--color-bg)] text-[var(--color-text)]">
      {/* Desktop sidebar */}
      <aside className="glass-sidebar fixed inset-y-0 left-0 z-40 hidden w-64 flex-col lg:flex">
        <div className="border-b border-[var(--color-border-subtle)] px-5 py-5">
          <Logo size="sm" linkTo="/dashboard" />
        </div>

        <nav className="flex-1 space-y-1.5 overflow-y-auto px-3 py-4">
          {dashboardNavItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `glass-sidebar-nav ${isActive ? 'glass-sidebar-nav-active' : ''}`
              }
            >
              {item.icon}
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="space-y-3 border-t border-[var(--color-border-subtle)] p-4">
          <Link to="/" className="block">
            <Button variant="outline" size="sm" fullWidth>
              Back to site
            </Button>
          </Link>
          <div className="glass-panel flex items-center gap-3 p-3">
            {user?.avatar_url ? (
              <img src={user.avatar_url} alt="" className="h-9 w-9 object-cover" />
            ) : (
              <div className="glass-icon-tile flex h-9 w-9 items-center justify-center bg-gradient-to-br from-[var(--color-cyan)] to-[var(--color-purple)] text-xs font-bold text-white">
                {initials}
              </div>
            )}
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{user?.full_name || 'User'}</p>
              <p className="truncate text-xs text-[var(--color-text-dim)]">{user?.email}</p>
            </div>
          </div>
          <Button variant="ghost" size="sm" fullWidth onClick={() => void handleLogout()}>
            Sign out
          </Button>
        </div>
      </aside>

      <main className="dashboard-main min-w-0 flex-1 lg:ml-64">
        <div className="min-h-screen min-h-[100dvh] overflow-x-hidden bg-[var(--color-bg)]">
          <Outlet />
        </div>
      </main>

      <MobileBottomNav />
    </div>
  )
}
