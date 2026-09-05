import { describe, it, expect } from 'vitest'
import { computeStarPositions, RING_RADII, RING_RADIUS } from './geometry'

describe('computeStarPositions', () => {
  it('places Reach schools farther from center than Likely', () => {
    const positions = computeStarPositions([
      { unitId: 1, name: 'A', bucket: 'Reach' },
      { unitId: 2, name: 'B', bucket: 'Target' },
      { unitId: 3, name: 'C', bucket: 'Likely' },
    ])
    const dist = (p: { x: number; y: number }) => Math.hypot(p.x, p.y)
    const byBucket = Object.fromEntries(positions.map((p) => [p.bucket, p]))
    expect(dist(byBucket.Reach)).toBeGreaterThan(dist(byBucket.Target))
    expect(dist(byBucket.Target)).toBeGreaterThan(dist(byBucket.Likely))
  })

  it('gives every college a position', () => {
    const positions = computeStarPositions([
      { unitId: 1, name: 'A', bucket: 'Reach' },
      { unitId: 2, name: 'B', bucket: 'Target' },
    ])
    expect(positions.map((p) => p.unitId).sort()).toEqual([1, 2])
  })
})

describe('RING_RADII', () => {
  it('exposes the same radii the positions are plotted against, innermost first', () => {
    // StarChart.vue draws its ring circles from this list instead of hardcoding
    // [65, 130, 200], so the rings and the star points cannot drift apart.
    expect(RING_RADII).toEqual([65, 130, 200])
    expect([...RING_RADII].sort((a, b) => a - b)).toEqual(
      Object.values(RING_RADIUS).sort((a, b) => a - b),
    )
  })

  it('matches the radius each bucket is actually plotted at', () => {
    const positions = computeStarPositions([
      { unitId: 1, name: 'A', bucket: 'Reach' },
      { unitId: 2, name: 'B', bucket: 'Target' },
      { unitId: 3, name: 'C', bucket: 'Likely' },
    ])
    for (const p of positions) {
      expect(Math.hypot(p.x, p.y)).toBeCloseTo(RING_RADIUS[p.bucket])
      expect(RING_RADII).toContain(RING_RADIUS[p.bucket])
    }
  })
})
