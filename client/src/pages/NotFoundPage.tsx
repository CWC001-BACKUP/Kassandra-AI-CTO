import { Link } from 'react-router-dom'
import { Button } from '../components/ui/Button'
import { GradientText } from '../components/ui/GradientText'
import { Logo } from '../components/ui/Logo'
import { LazyScene } from '../components/three/LazyScene'
import { NotFoundScene } from '../components/three/NotFoundScene'

export function NotFoundPage() {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-[var(--color-bg)] px-6 text-center">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0" style={{ background: 'var(--gradient-hero)' }} />
        <LazyScene
          className="absolute inset-0 opacity-70"
          camera={{ position: [0, 0, 4], fov: 50 }}
        >
          <NotFoundScene />
        </LazyScene>
      </div>

      <div className="relative z-10">
        <Logo size="xl" showText={false} className="mx-auto mb-8 justify-center opacity-60" />

        <p className="font-display text-8xl font-bold">
          <GradientText>404</GradientText>
        </p>
        <h1 className="mt-4 font-display text-2xl font-semibold">Page not found</h1>
        <p className="mt-2 max-w-md text-[var(--color-text-muted)]">
          The page you&apos;re looking for doesn&apos;t exist or has been moved.
          Even Kassandra can&apos;t remember this one.
        </p>

        <div className="mt-8 flex justify-center gap-4">
          <Link to="/">
            <Button>Go Home</Button>
          </Link>
          <Link to="/dashboard">
            <Button variant="outline">Dashboard</Button>
          </Link>
        </div>
      </div>
    </div>
  )
}
