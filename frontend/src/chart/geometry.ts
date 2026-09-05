export type Bucket = 'Reach' | 'Target' | 'Likely'

export interface CollegeForChart {
  unitId: number
  name: string
  bucket: Bucket
}

export interface StarPosition {
  unitId: number
  name: string
  bucket: Bucket
  x: number
  y: number
}

const RING_RADIUS: Record<Bucket, number> = { Reach: 200, Target: 130, Likely: 65 }

export function computeStarPositions(colleges: CollegeForChart[]): StarPosition[] {
  const byBucket: Record<Bucket, CollegeForChart[]> = { Reach: [], Target: [], Likely: [] }
  for (const c of colleges) byBucket[c.bucket].push(c)

  const positions: StarPosition[] = []
  ;(Object.keys(byBucket) as Bucket[]).forEach((bucket) => {
    const items = byBucket[bucket]
    const radius = RING_RADIUS[bucket]
    items.forEach((c, i) => {
      const angle = items.length ? (2 * Math.PI * i) / items.length : 0
      positions.push({
        unitId: c.unitId,
        name: c.name,
        bucket,
        x: radius * Math.cos(angle),
        y: radius * Math.sin(angle),
      })
    })
  })
  return positions
}
