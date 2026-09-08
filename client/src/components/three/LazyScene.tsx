import { lazy, Suspense, useEffect, useState, type ReactNode } from 'react'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'

const SceneCanvas = lazy(() =>
  import('./SceneCanvas').then((m) => ({ default: m.SceneCanvas })),
)

interface LazySceneProps {
  children: ReactNode
  className?: string
  camera?: { position: [number, number, number]; fov?: number }
  /** Skip WebGL on narrow viewports to avoid mobile GPU/context issues */
  disableOnMobile?: boolean
}

function useIsNarrowViewport() {
  const [narrow, setNarrow] = useState(() =>
    typeof window !== 'undefined'
      ? window.matchMedia('(max-width: 768px)').matches
      : false,
  )

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 768px)')
    const handler = (e: MediaQueryListEvent) => setNarrow(e.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  return narrow
}

export function LazyScene({
  children,
  className,
  camera,
  disableOnMobile = false,
}: LazySceneProps) {
  const reducedMotion = usePrefersReducedMotion()
  const narrow = useIsNarrowViewport()

  if (reducedMotion || (disableOnMobile && narrow)) return null

  return (
    <Suspense fallback={null}>
      <SceneCanvas className={className} camera={camera}>
        {children}
      </SceneCanvas>
    </Suspense>
  )
}
