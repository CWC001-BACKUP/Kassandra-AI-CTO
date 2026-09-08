import { Suspense, useEffect, useState, type ReactNode } from 'react'
import { Canvas } from '@react-three/fiber'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'

interface SceneCanvasProps {
  children: ReactNode
  className?: string
  camera?: { position: [number, number, number]; fov?: number }
  dpr?: [number, number]
}

function useAdaptiveCanvasSettings() {
  const [settings, setSettings] = useState({
    dpr: [1, 1.5] as [number, number],
    antialias: true,
  })

  useEffect(() => {
    const narrow = window.matchMedia('(max-width: 768px)')
    const tablet = window.matchMedia('(max-width: 1024px)')

    const update = () => {
      if (narrow.matches) {
        setSettings({ dpr: [1, 1], antialias: false })
      } else if (tablet.matches) {
        setSettings({ dpr: [1, 1.25], antialias: true })
      } else {
        setSettings({ dpr: [1, 1.5], antialias: true })
      }
    }

    update()
    narrow.addEventListener('change', update)
    tablet.addEventListener('change', update)
    return () => {
      narrow.removeEventListener('change', update)
      tablet.removeEventListener('change', update)
    }
  }, [])

  return settings
}

export function SceneCanvas({
  children,
  className = 'scene-canvas',
  camera = { position: [0, 0, 6], fov: 50 },
  dpr,
}: SceneCanvasProps) {
  const reducedMotion = usePrefersReducedMotion()
  const adaptive = useAdaptiveCanvasSettings()

  if (reducedMotion) return null

  return (
    <div className={className}>
      <Canvas
        camera={camera}
        dpr={dpr ?? adaptive.dpr}
        gl={{
          antialias: adaptive.antialias,
          alpha: true,
          powerPreference: 'high-performance',
          failIfMajorPerformanceCaveat: false,
        }}
        style={{ background: 'transparent' }}
        onCreated={({ gl }) => {
          const canvas = gl.domElement
          canvas.addEventListener('webglcontextlost', (event) => {
            event.preventDefault()
          })
        }}
      >
        <Suspense fallback={null}>{children}</Suspense>
      </Canvas>
    </div>
  )
}
