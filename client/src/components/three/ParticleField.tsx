import { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

const COUNT = 2000

export function ParticleField() {
  const ref = useRef<THREE.Points>(null)
  const elapsed = useRef(0)

  const [positions, colors] = useMemo(() => {
    const pos = new Float32Array(COUNT * 3)
    const col = new Float32Array(COUNT * 3)

    for (let i = 0; i < COUNT; i++) {
      const i3 = i * 3
      const radius = 4 + Math.random() * 12
      const theta = Math.random() * Math.PI * 2
      const phi = Math.acos(2 * Math.random() - 1)

      pos[i3] = radius * Math.sin(phi) * Math.cos(theta)
      pos[i3 + 1] = radius * Math.sin(phi) * Math.sin(theta)
      pos[i3 + 2] = radius * Math.cos(phi) - 4

      const t = Math.random()
      col[i3] = 0 + t * 0.63
      col[i3 + 1] = 0.82 + t * 0.1
      col[i3 + 2] = 1
    }

    return [pos, col]
  }, [])

  useFrame((_, delta) => {
    if (!ref.current) return
    elapsed.current += delta
    ref.current.rotation.y = elapsed.current * 0.02
    ref.current.rotation.x = Math.sin(elapsed.current * 0.01) * 0.1
  })

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
          count={COUNT}
        />
        <bufferAttribute
          attach="attributes-color"
          args={[colors, 3]}
          count={COUNT}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.025}
        vertexColors
        transparent
        opacity={0.7}
        sizeAttenuation
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  )
}
