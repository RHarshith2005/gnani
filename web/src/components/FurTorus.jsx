import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import './FurTorus.css'

const HAIR_COUNT = 9000
const LOOP_SECONDS = 6.7
const TILT = THREE.MathUtils.degToRad(15)

function webglAvailable() {
  try {
    const canvas = document.createElement('canvas')
    return Boolean(
      window.WebGLRenderingContext && (canvas.getContext('webgl2') || canvas.getContext('webgl')),
    )
  } catch {
    return false
  }
}

const VERT = /* glsl */ `
  uniform float uTime;
  uniform float uLevel;
  uniform float uStand;
  uniform float uSway;
  uniform float uPulse;

  attribute vec3 aNormal;
  attribute float aSide;
  attribute float aSeed;
  attribute float aLength;

  varying float vSide;
  varying float vSeed;
  varying float vLight;

  void main() {
    vSide = aSide;
    vSeed = aSeed;

    // Breathing pulse used while the agent speaks (driven by TTS RMS).
    float pulse = 1.0 + uPulse * (0.45 + 0.55 * sin(uTime * 7.0 + aSeed * 6.2831));
    float grow = (0.72 + 0.55 * aSeed) * pulse;
    float len = aLength * grow * (1.0 + uStand * (0.55 + 0.95 * uLevel));

    vec3 dir = normalize(aNormal);
    vec3 sway = vec3(
      sin(uTime * 1.9 + aSeed * 31.0),
      cos(uTime * 1.6 + aSeed * 17.0),
      sin(uTime * 2.4 + aSeed * 23.0)
    );

    vec3 p = position;
    if (aSide > 0.5) {
      p += dir * len + sway * len * (0.24 * uSway);
    } else {
      p += sway * 0.006 * uSway;
    }

    vLight = 0.42 + 0.58 * clamp(dot(dir, normalize(vec3(0.35, 0.75, 0.55))), 0.0, 1.0);
    gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
  }
`

const FRAG = /* glsl */ `
  uniform vec3 uRoot;
  uniform vec3 uTip;
  uniform vec3 uLift;
  uniform float uLiftAmount;

  varying float vSide;
  varying float vSeed;
  varying float vLight;

  void main() {
    vec3 fur = mix(uRoot, uTip, smoothstep(0.04, 0.96, vSide * 0.94 + vSeed * 0.16));
    fur *= 0.78 + 0.5 * vLight;
    fur = mix(fur, uLift, uLiftAmount * vSide);
    gl_FragColor = vec4(fur, 0.94);
  }
`

function haloTexture() {
  const size = 256
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')
  const gradient = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2)
  gradient.addColorStop(0, 'rgba(196,140,245,0.55)')
  gradient.addColorStop(0.42, 'rgba(150,80,210,0.22)')
  gradient.addColorStop(1, 'rgba(150,80,210,0)')
  ctx.fillStyle = gradient
  ctx.fillRect(0, 0, size, size)
  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  return texture
}

/** Build one fur strand pair per sample of the torus surface. */
function buildFur(source) {
  const positions = source.attributes.position
  const normals = source.attributes.normal
  const total = positions.count

  const picks = new Uint32Array(total)
  for (let i = 0; i < total; i++) picks[i] = i
  for (let i = 0; i < HAIR_COUNT; i++) {
    const j = i + Math.floor(Math.random() * (total - i))
    const tmp = picks[i]
    picks[i] = picks[j]
    picks[j] = tmp
  }

  const vertexCount = HAIR_COUNT * 2
  const position = new Float32Array(vertexCount * 3)
  const normal = new Float32Array(vertexCount * 3)
  const side = new Float32Array(vertexCount)
  const seed = new Float32Array(vertexCount)
  const length = new Float32Array(vertexCount)

  for (let h = 0; h < HAIR_COUNT; h++) {
    const idx = picks[h]
    const px = positions.getX(idx)
    const py = positions.getY(idx)
    const pz = positions.getZ(idx)
    const nx = normals.getX(idx)
    const ny = normals.getY(idx)
    const nz = normals.getZ(idx)
    const jitter = 0.28
    const jx = nx + (Math.random() - 0.5) * jitter
    const jy = ny + (Math.random() - 0.5) * jitter
    const jz = nz + (Math.random() - 0.5) * jitter
    const inv = 1 / Math.hypot(jx, jy, jz)
    const s = Math.random()
    const len = 0.06 + Math.random() * 0.08

    for (let k = 0; k < 2; k++) {
      const v = h * 2 + k
      position[v * 3] = px
      position[v * 3 + 1] = py
      position[v * 3 + 2] = pz
      normal[v * 3] = jx * inv
      normal[v * 3 + 1] = jy * inv
      normal[v * 3 + 2] = jz * inv
      side[v] = k
      seed[v] = s
      length[v] = len
    }
  }

  const geo = new THREE.BufferGeometry()
  geo.setAttribute('position', new THREE.BufferAttribute(position, 3))
  geo.setAttribute('aNormal', new THREE.BufferAttribute(normal, 3))
  geo.setAttribute('aSide', new THREE.BufferAttribute(side, 1))
  geo.setAttribute('aSeed', new THREE.BufferAttribute(seed, 1))
  geo.setAttribute('aLength', new THREE.BufferAttribute(length, 1))
  geo.computeBoundingSphere()
  return geo
}

function createOrb(host, reducedMotion) {
  const scene = new THREE.Scene()
  const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100)
  camera.position.set(0, 0, 6.9)

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setClearAlpha(0)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
  renderer.outputColorSpace = THREE.SRGBColorSpace
  const canvas = renderer.domElement
  canvas.setAttribute('aria-hidden', 'true')
  host.appendChild(canvas)

  const geometry = new THREE.TorusGeometry(1, 0.5, 64, 160)
  const baseMaterial = new THREE.MeshStandardMaterial({
    color: 0x7d32a0,
    roughness: 0.62,
    metalness: 0.06,
  })
  const baseMesh = new THREE.Mesh(geometry, baseMaterial)

  const furGeometry = buildFur(geometry)
  const furMaterial = new THREE.ShaderMaterial({
    vertexShader: VERT,
    fragmentShader: FRAG,
    transparent: true,
    depthWrite: true,
    uniforms: {
      uTime: { value: 0 },
      uLevel: { value: 0 },
      uStand: { value: 0 },
      uSway: { value: 0.9 },
      uPulse: { value: 0 },
      uRoot: { value: new THREE.Color(0x5a1f94) },
      uTip: { value: new THREE.Color(0xb27fd8) },
      uLift: { value: new THREE.Color(0xe6ccff) },
      uLiftAmount: { value: 0 },
    },
  })
  const fur = new THREE.LineSegments(furGeometry, furMaterial)

  const halo = new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: haloTexture(),
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      opacity: 0.75,
    }),
  )
  halo.scale.setScalar(3.5)
  halo.position.z = -1.4

  scene.add(halo, baseMesh, fur)
  scene.add(new THREE.AmbientLight(0xffffff, 0.55))
  const key = new THREE.DirectionalLight(0xffeaff, 1.5)
  key.position.set(2.4, 3.2, 4)
  scene.add(key)
  const fill = new THREE.PointLight(0x9b5ce0, 8, 12)
  fill.position.set(-2.6, -1.4, 2.2)
  scene.add(fill)
  const rim = new THREE.PointLight(0xb27fd8, 10, 14)
  rim.position.set(0.4, 0.8, -3)
  scene.add(rim)

  const group = new THREE.Group()
  group.add(...scene.children.filter((c) => c.isMesh || c.isLineSegments || c.isSprite))
  scene.add(group)

  group.rotation.x = TILT

  const stateRef = { value: 'idle' }
  const levelRef = { value: 0 }
  let level = 0
  let spin = 1
  let stand = 0
  let lift = 0
  let phase = 0
  let pulse = 0
  let time = 0
  let disposed = false
  let raf = 0

  const resize = () => {
    const width = host.clientWidth || 1
    const height = host.clientHeight || 1
    renderer.setSize(width, height, false)
    camera.aspect = width / height
    camera.updateProjectionMatrix()
  }
  const observer = new ResizeObserver(resize)
  observer.observe(host)
  resize()

  const renderFrame = (dt) => {
    const state = stateRef.value
    const targetLevel = Math.max(0, Math.min(1, levelRef.value))
    level += (targetLevel - level) * Math.min(1, dt * 9)

    const target =
      state === 'thinking'
        ? { spin: 2.5, stand: 0.5, lift: 0.6 }
        : state === 'listening'
          ? { spin: 0, stand: 1, lift: 0.1 }
          : state === 'speaking'
            ? { spin: 0.6, stand: 1, lift: 0.14 }
            : { spin: 1, stand: 0, lift: 0 }

    spin += (target.spin - spin) * Math.min(1, dt * 3.2)
    stand += (target.stand - stand) * Math.min(1, dt * 3.4)
    lift += (target.lift - lift) * Math.min(1, dt * 3)

    if (state === 'listening') {
      // Turn face-on and hold: snap to the nearest 180° multiple.
      const snap = Math.round(phase / Math.PI) * Math.PI
      phase += (snap - phase) * Math.min(1, dt * 2.4)
    } else {
      phase += dt * (Math.PI / LOOP_SECONDS) * spin
    }

    group.rotation.y = phase + 0.09 * Math.sin(phase * 2)
    group.rotation.x = TILT + 0.05 * Math.sin(time * 0.7)
    group.rotation.z = 0.03 * Math.sin(time * 0.45)

    const scale = 1 + level * 0.03 * (state === 'speaking' ? 1 : 0.35)
    group.scale.setScalar(scale)

    pulse += ((state === 'speaking' ? level : 0) - pulse) * Math.min(1, dt * 8)

    furMaterial.uniforms.uTime.value = time
    furMaterial.uniforms.uLevel.value = level
    furMaterial.uniforms.uStand.value = stand
    furMaterial.uniforms.uSway.value = 0.55 + stand * 0.75
    furMaterial.uniforms.uPulse.value = pulse
    furMaterial.uniforms.uLiftAmount.value = lift
    halo.material.opacity = 0.62 + level * 0.18

    renderer.render(scene, camera)
  }

  if (reducedMotion) {
    // Single static, face-on frame; state changes still re-render once.
    const still = () => {
      group.rotation.y = 0
      renderer.render(scene, camera)
    }
    still()
    const stillObserver = new ResizeObserver(still)
    stillObserver.observe(host)
    return {
      setState(next) {
        stateRef.value = next
        still()
      },
      setLevel(next) {
        levelRef.value = next
      },
      dispose() {
        disposed = true
        stillObserver.disconnect()
        disposeScene()
      },
    }
  }

  let last = performance.now()
  const loop = (now) => {
    if (disposed) return
    const dt = Math.min((now - last) / 1000, 0.05)
    last = now
    time += dt
    renderFrame(dt)
    raf = requestAnimationFrame(loop)
  }
  raf = requestAnimationFrame(loop)

  function disposeScene() {
    cancelAnimationFrame(raf)
    observer.disconnect()
    geometry.dispose()
    baseMaterial.dispose()
    furGeometry.dispose()
    furMaterial.dispose()
    halo.material.map?.dispose()
    halo.material.dispose()
    renderer.dispose()
    if (canvas.parentNode === host) host.removeChild(canvas)
  }

  return {
    setState(next) {
      stateRef.value = next
    },
    setLevel(next) {
      levelRef.value = next
    },
    dispose() {
      disposed = true
      disposeScene()
    },
  }
}

export default function FurTorus({ state = 'idle', level = 0, className = '' }) {
  const hostRef = useRef(null)
  const controlRef = useRef(null)
  const initial = useRef({ state, level })
  const [fallback, setFallback] = useState(false)

  useEffect(() => {
    controlRef.current?.setState(state)
  }, [state])

  useEffect(() => {
    controlRef.current?.setLevel(level)
  }, [level])

  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    const reducedMotion =
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches

    if (!webglAvailable() && !reducedMotion) {
      setFallback(true)
      return
    }

    let control
    try {
      control = createOrb(host, reducedMotion)
    } catch (err) {
      console.warn('FurTorus: WebGL init failed, using CSS fallback', err)
      setFallback(true)
      return
    }
    controlRef.current = control
    control.setState(initial.current.state)
    control.setLevel(initial.current.level)
    return () => {
      control.dispose()
      controlRef.current = null
    }
  }, [])

  return (
    <div className={`fur-torus ${fallback ? 'is-fallback' : ''} ${className}`} data-state={state}>
      <div ref={hostRef} className="fur-torus__canvas" />
      {fallback ? (
        <div className="fur-torus__ring" role="presentation">
          <span />
        </div>
      ) : null}
    </div>
  )
}
