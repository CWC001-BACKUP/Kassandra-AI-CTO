import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import type * as THREE from 'three'

export function NotFoundScene() {
  const group = useRef<THREE.Group>(null)
  const mesh = useRef<THREE.Mesh>(null)
  const elapsed = useRef(0)

  useFrame((_, delta) => {
    if (!group.current) return
    elapsed.current += delta
    const t = elapsed.current
    group.current.rotation.y = t * 0.2
    if (mesh.current) {
      mesh.current.position.y = Math.sin(t * 2) * 0.08
    }
  })

  return (
    <group ref={group}>
      <ambientLight intensity={0.4} />
      <pointLight position={[2, 2, 2]} intensity={1} color="#00D2FF" />
      <pointLight position={[-2, -1, 1]} intensity={0.6} color="#A020F0" />
      <mesh ref={mesh}>
        <icosahedronGeometry args={[1.2, 1]} />
        <meshStandardMaterial
          color="#111827"
          emissive="#0072FF"
          emissiveIntensity={0.3}
          metalness={0.9}
          roughness={0.1}
          wireframe
        />
      </mesh>
      <mesh position={[0, 0, 0]} scale={2.5}>
        <torusGeometry args={[1.5, 0.02, 8, 64]} />
        <meshBasicMaterial color="#00D2FF" transparent opacity={0.4} />
      </mesh>
    </group>
  )
}
