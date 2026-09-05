import { describe, it, expect } from 'vitest'
import { computeStarPositions } from './geometry'

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
