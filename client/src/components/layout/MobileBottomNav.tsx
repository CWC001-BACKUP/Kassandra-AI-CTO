import { useState } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { Button } from '../ui/Button'
import { useAuth } from '../../context/AuthProvider'
import { mobileBottomNavItems, mobileMoreNavItems } from './dashboardNav'

export function MobileBottomNav({ gapCount = 0 }: { gapCount?: number }) {
  const [moreOpen, setMoreOpen] = useState(false)
  const { logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const moreActive = mobileMoreNavItems.some((item) =>
    location.pathname.startsWith(item.to),
  )

  const handleLogout = async () => {
    setMoreOpen(false)
    await logout()
    navigate('/login')
  }

  return (
    <>
      {moreOpen && (
        <button
          type="button"
          aria-label="Close menu"
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-[2px] lg:hidden"
          onClick={() => setMoreOpen(false)}
        />
      )}

      <div
        className={`glass-bottom-nav fixed inset-x-0 bottom-0 z-50 border-t border-[var(--color-border-subtle)] lg:hidden ${
          moreOpen ? 'translate-y-0' : ''
        }`}
        style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
      >
        {moreOpen && (
          <div className="border-b border-[var(--color-border-subtle)] p-3">
            <p className="mb-2 px-1 text-xs font-semibold uppercase tracking-wider text-[var(--color-text-dim)]">
              More
            </p>
            <div className="space-y-1">
              {mobileMoreNavItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={() => setMoreOpen(false)}
                  className={({ isActive }) =>
                    `glass-sidebar-nav ${isActive ? 'glass-sidebar-nav-active' : ''}`
                  }
                >
                  {item.icon}
                  <span className="flex min-w-0 flex-1 items-center justify-between gap-2">
                    <span className="truncate">{item.label}</span>
                    {item.to === '/dashboard/teach' && gapCount > 0 && (
                      <span className="inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-[var(--color-warning)]/20 px-1.5 text-[10px] font-semibold text-[var(--color-warning)]">
                        {gapCount > 99 ? '99+' : gapCount}
                      </span>
                    )}
                  </span>
                </NavLink>
              ))}
              <Link to="/" onClick={() => setMoreOpen(false)} className="block pt-1">
                <Button variant="outline" size="sm" fullWidth>
                  Back to site
                </Button>
              </Link>
              <Button variant="ghost" size="sm" fullWidth onClick={() => void handleLogout()}>
                Sign out
              </Button>
            </div>
          </div>
        )}

        <nav
          className="grid grid-cols-5 gap-0"
          aria-label="Dashboard navigation"
        >
          {mobileBottomNavItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex min-h-[3.5rem] flex-col items-center justify-center gap-1 px-1 py-2 text-[10px] font-medium transition-colors sm:text-xs ${
                  isActive
                    ? 'text-[var(--color-cyan)]'
                    : 'text-[var(--color-text-dim)] hover:text-[var(--color-text)]'
                }`
              }
            >
              {item.icon}
              <span className="truncate">{item.shortLabel ?? item.label}</span>
            </NavLink>
          ))}
          <button
            type="button"
            onClick={() => setMoreOpen((open) => !open)}
            className={`relative flex min-h-[3.5rem] flex-col items-center justify-center gap-1 px-1 py-2 text-[10px] font-medium transition-colors sm:text-xs ${
              moreOpen || moreActive
                ? 'text-[var(--color-cyan)]'
                : 'text-[var(--color-text-dim)] hover:text-[var(--color-text)]'
            }`}
            aria-expanded={moreOpen}
            aria-label="More options"
          >
            <span className="relative">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 12a.75.75 0 11-1.5 0 .75.75 0 011.5 0zM12.75 12a.75.75 0 11-1.5 0 .75.75 0 011.5 0zM18.75 12a.75.75 0 11-1.5 0 .75.75 0 011.5 0z" />
              </svg>
              {gapCount > 0 && (
                <span className="absolute -right-2 -top-1 h-2 w-2 rounded-full bg-[var(--color-warning)]" />
              )}
            </span>
            <span>More</span>
          </button>
        </nav>
      </div>
    </>
  )
}
