import { Outlet } from 'react-router-dom'
import { Navbar } from './Navbar'
import { Footer } from './Footer'
import { LazyScene } from '../three/LazyScene'
import { ParticleField } from '../three/ParticleField'

export function LandingLayout() {
  return (
    <div className="relative flex min-h-screen flex-col bg-[var(--color-bg)] text-[var(--color-text)]">
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute inset-0" style={{ background: 'var(--gradient-hero)' }} />
        <LazyScene className="fixed inset-0 opacity-60" disableOnMobile>
          <ParticleField />
        </LazyScene>
        <div className="absolute inset-0 grid-pattern opacity-20" />
      </div>

      <div className="relative z-10 flex min-h-screen flex-col">
        <Navbar />
        <main className="flex-1">
          <Outlet />
        </main>
        <Footer />
      </div>
    </div>
  )
}
