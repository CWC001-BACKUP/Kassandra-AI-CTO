import { Link } from 'react-router-dom'
import { Logo } from '../ui/Logo'
import { Button } from '../ui/Button'
import { useAuth } from '../../context/AuthProvider'

const navLinks = [
  { href: '#features', label: 'Features' },
  { href: '#how-it-works', label: 'How It Works' },
  { href: '#pricing', label: 'Pricing' },
]

export function Navbar() {
  const auth = useAuth()
  const signedIn = Boolean(auth.user)
  const authReady = !auth.isLoading

  return (
    <header className="sticky top-0 z-50 border-b border-[var(--color-border-subtle)] glass-strong">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-3 sm:px-6 sm:py-3.5">
        <Logo size="md" linkTo="/" />
        <nav className="hidden items-center gap-1 md:flex">
          {navLinks.map((link) => (
            <a key={link.href} href={link.href} className="btn-glass btn-glass-nav">
              {link.label}
            </a>
          ))}
        </nav>
        <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
          {!authReady ? (
            <span className="px-2 text-xs text-[var(--color-text-dim)] sm:px-3">…</span>
          ) : signedIn ? (
            <>
              <Link to="/dashboard">
                <Button variant="outline" size="sm">
                  Dashboard
                </Button>
              </Link>
              <Link to="/dashboard/chat">
                <Button size="sm">Chat</Button>
              </Link>
            </>
          ) : (
            <>
              <Link to="/login">
                <Button variant="ghost" size="sm">
                  Log in
                </Button>
              </Link>
              <Link to="/signup">
                <Button size="sm">Get Started</Button>
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  )
}
