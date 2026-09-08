import { Outlet, useNavigate } from 'react-router-dom'
import { Logo } from '../ui/Logo'
import { Button } from '../ui/Button'
import { LazyScene } from '../three/LazyScene'
import { AuthParticles } from '../three/AuthParticles'

export function AuthLayout() {
  const navigate = useNavigate()

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[var(--color-bg)] px-4 py-12">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0" style={{ background: 'var(--gradient-hero)' }} />
        <LazyScene className="absolute inset-0 opacity-50" disableOnMobile>
          <ambientLight intensity={0.2} />
          <AuthParticles />
        </LazyScene>
        <div className="absolute inset-0 dot-pattern opacity-20" />
      </div>

      <div className="pointer-events-none absolute -left-32 -top-32 h-96 w-96 rounded-full bg-[var(--color-cyan)]/8 blur-[120px]" />
      <div className="pointer-events-none absolute -bottom-32 -right-32 h-96 w-96 rounded-full bg-[var(--color-purple)]/8 blur-[120px]" />

      <div className="relative z-10 w-full max-w-md">
        <div className="mb-8 flex justify-center animate-fade-up">
          <Logo size="lg" linkTo="/" />
        </div>
        <div className="animate-fade-up stagger-1">
          <Outlet />
        </div>
        <div className="mt-6 flex justify-center animate-fade-up stagger-2">
          <Button variant="ghost" size="sm" type="button" onClick={() => navigate('/')}>
            ← Back to Homepage
          </Button>
        </div>
      </div>
    </div>
  )
}
