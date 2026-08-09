import { useEffect, useRef } from 'react'

const CONFIG = {
  polygonCount: 24,
  speed: 0.18,
  minSize: 80,
  maxSize: 280,
  minOpacity: 0.025,
  maxOpacity: 0.1,
  minSides: 3,
  maxSides: 7,
  colors: [
    [45, 125, 210],
    [70, 160, 230],
    [100, 190, 240],
    [35, 90, 160],
    [80, 120, 200],
  ],
}

const random = (min, max) => Math.random() * (max - min) + min

const randomInt = (min, max) => Math.floor(random(min, max + 1))

const choose = (array) => array[Math.floor(Math.random() * array.length)]

function createPolygon(width, height, speedFactor) {
  const sides = randomInt(CONFIG.minSides, CONFIG.maxSides)
  const size = random(CONFIG.minSize, CONFIG.maxSize)
  const color = choose(CONFIG.colors)

  const vertices = []
  for (let i = 0; i < sides; i++) {
    vertices.push({
      angle: (Math.PI * 2 * i) / sides,
      radius: size * random(0.65, 1.15),
    })
  }

  return {
    x: random(-size, width + size),
    y: random(-size, height + size),
    size,
    vertices,
    rotation: random(0, Math.PI * 2),
    rotationSpeed: random(-0.0014, 0.0014),
    vx: random(-2.5, 2.5) * CONFIG.speed * speedFactor,
    vy: random(-1.75, 1.75) * CONFIG.speed * speedFactor,
    opacity: random(CONFIG.minOpacity, CONFIG.maxOpacity),
    color,
    phase: random(0, Math.PI * 2),
    pulseSpeed: random(0.0005, 0.0015),
  }
}

export default function PolygonBackground() {
  const containerRef = useRef(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)')
    const speedFactor = reducedMotion.matches ? 0 : 1

    const canvas = document.createElement('canvas')
    canvas.className = 'polygon-background__canvas'
    canvas.setAttribute('aria-hidden', 'true')
    container.appendChild(canvas)

    const ctx = canvas.getContext('2d')

    let width = 0
    let height = 0
    let dpr = 1
    let polygons = []
    let animationFrame

    function createPolygons() {
      polygons = []
      for (let i = 0; i < CONFIG.polygonCount; i++) {
        polygons.push(createPolygon(width, height, speedFactor))
      }
    }

    function resize() {
      const rect = container.getBoundingClientRect()

      width = Math.max(rect.width, 1)
      height = Math.max(rect.height, 1)

      dpr = Math.min(window.devicePixelRatio || 1, 2)

      canvas.width = width * dpr
      canvas.height = height * dpr

      canvas.style.width = `${width}px`
      canvas.style.height = `${height}px`

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

      createPolygons()
    }

    function drawPolygon(polygon, time) {
      const { x, y, vertices, rotation, color } = polygon

      const pulse = 1 + Math.sin(time * polygon.pulseSpeed + polygon.phase) * 0.035

      ctx.save()
      ctx.translate(x, y)
      ctx.rotate(rotation)
      ctx.scale(pulse, pulse)

      ctx.beginPath()
      vertices.forEach((vertex, index) => {
        const px = Math.cos(vertex.angle) * vertex.radius
        const py = Math.sin(vertex.angle) * vertex.radius

        if (index === 0) {
          ctx.moveTo(px, py)
        } else {
          ctx.lineTo(px, py)
        }
      })
      ctx.closePath()

      const [r, g, b] = color

      ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${polygon.opacity})`
      ctx.fill()

      ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${polygon.opacity * 0.45})`
      ctx.lineWidth = 1
      ctx.stroke()

      ctx.restore()
    }

    function updatePolygon(polygon) {
      polygon.x += polygon.vx
      polygon.y += polygon.vy
      polygon.rotation += polygon.rotationSpeed

      const margin = polygon.size * 1.5

      if (polygon.x < -margin) polygon.x = width + margin
      if (polygon.x > width + margin) polygon.x = -margin
      if (polygon.y < -margin) polygon.y = height + margin
      if (polygon.y > height + margin) polygon.y = -margin
    }

    function animate(time) {
      ctx.clearRect(0, 0, width, height)

      for (const polygon of polygons) {
        updatePolygon(polygon)
        drawPolygon(polygon, time)
      }

      animationFrame = requestAnimationFrame(animate)
    }

    function onVisibilityChange() {
      if (document.hidden) {
        cancelAnimationFrame(animationFrame)
      } else {
        animationFrame = requestAnimationFrame(animate)
      }
    }

    window.addEventListener('resize', resize, { passive: true })
    document.addEventListener('visibilitychange', onVisibilityChange)

    resize()
    animationFrame = requestAnimationFrame(animate)

    return () => {
      cancelAnimationFrame(animationFrame)
      window.removeEventListener('resize', resize)
      document.removeEventListener('visibilitychange', onVisibilityChange)
      canvas.remove()
    }
  }, [])

  return (
    <div
      ref={containerRef}
      id="polygon-background"
      className="polygon-background"
      aria-hidden="true"
    />
  )
}