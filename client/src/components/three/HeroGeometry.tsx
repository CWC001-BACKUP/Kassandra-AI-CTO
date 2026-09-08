import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import type * as THREE from 'three'

function TorusKnot() {
  const ref = useRef<THREE.Mesh>(null)
  const elapsed = useRef(0)

  useFrame((_, delta) => {
    if (!ref.current) return
    elapsed.current += delta
    const t = elapsed.current
    ref.current.rotation.x = t * 0.15
    ref.current.rotation.y = t * 0.25
    ref.current.position.y = Math.sin(t * 1.5) * 0.12
  })

  return (
    <mesh ref={ref}>
      <torusKnotGeometry args={[1.1, 0.32, 128, 32]} />
      <meshStandardMaterial
        color="#00D2FF"
        emissive="#0072FF"
        emissiveIntensity={0.4}
        metalness={0.8}
        roughness={0.2}
        transparent
        opacity={0.9}
      />
    </mesh>
  )
}

function OrbitingCubes() {
  const group = useRef<THREE.Group>(null)
  const elapsed = useRef(0)

  useFrame((_, delta) => {
    if (!group.current) return
    elapsed.current += delta
    group.current.rotation.y = elapsed.current * 0.3
  })

  const cubes = Array.from({ length: 6 }, (_, i) => {
    const angle = (i / 6) * Math.PI * 2
    return { x: Math.cos(angle) * 2.2, z: Math.sin(angle) * 2.2, y: Math.sin(i) * 0.5 }
  })

  return (
    <group ref={group}>
      {cubes.map((pos, i) => (
        <mesh key={i} position={[pos.x, pos.y, pos.z]} scale={0.15}>
          <boxGeometry />
          <meshStandardMaterial
            color={i % 2 === 0 ? '#A020F0' : '#00E5FF'}
            emissive={i % 2 === 0 ? '#7D26CD' : '#0072FF'}
            emissiveIntensity={0.5}
            metalness={0.9}
            roughness={0.1}
            wireframe={i % 3 === 0}
          />
        </mesh>
      ))}
    </group>
  )
}

export function HeroGeometry() {
  return (
    <>
      <ambientLight intensity={0.3} />
      <directionalLight position={[5, 5, 5]} intensity={1.2} color="#00D2FF" />
      <pointLight position={[-3, 2, 2]} intensity={0.8} color="#A020F0" />
      <pointLight position={[3, -2, -2]} intensity={0.5} color="#0072FF" />
      <TorusKnot />
      <OrbitingCubes />
    </>
  )
}
