import { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

const COUNT = 800

export function AuthParticles() {
  const ref = useRef<THREE.Points>(null)
  const elapsed = useRef(0)

  const positions = useMemo(() => {
    const pos = new Float32Array(COUNT * 3)
    for (let i = 0; i < COUNT; i++) {
      const i3 = i * 3
      pos[i3] = (Math.random() - 0.5) * 20
      pos[i3 + 1] = (Math.random() - 0.5) * 20
      pos[i3 + 2] = (Math.random() - 0.5) * 10 - 5
    }
    return pos
  }, [])

  useFrame((_, delta) => {
    if (!ref.current) return
    elapsed.current += delta
    ref.current.rotation.y = elapsed.current * 0.03
    const pos = ref.current.geometry.attributes.position.array as Float32Array
    for (let i = 0; i < COUNT; i++) {
      pos[i * 3 + 1] -= 0.008
      if (pos[i * 3 + 1] < -10) pos[i * 3 + 1] = 10
    }
    ref.current.geometry.attributes.position.needsUpdate = true
  })

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
          count={COUNT}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.04}
        color="#00D2FF"
        transparent
        opacity={0.5}
        sizeAttenuation
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  )
}
