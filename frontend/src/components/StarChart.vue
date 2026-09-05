<script setup lang="ts">
import { computed, ref } from 'vue'
import { computeStarPositions, RING_RADIUS, type CollegeForChart, type Bucket } from '../chart/geometry'

export interface ChartPointDetail {
  name: string
  bucket: Bucket
  matchScore: number
  admissionRate: number | null
  netPrice: number | null
  distanceMiles: number | null
}

const props = defineProps<{
  colleges: CollegeForChart[]
  details: Record<number, ChartPointDetail>
  studentName: string
}>()

const emit = defineEmits<{ select: [unitId: number] }>()

const positions = computed(() => computeStarPositions(props.colleges))
const bucketColor: Record<Bucket, string> = {
  Reach: 'var(--reach-ember)',
  Target: 'var(--target-sage)',
  Likely: 'var(--likely-teal)',
}
const bucketLightColor: Record<Bucket, string> = {
  Reach: 'var(--reach-ember-light)',
  Target: 'var(--target-sage-light)',
  Likely: 'var(--likely-teal-light)',
}
// Largest radius first so each smaller, later circle paints over the outer
// one -- three concentric filled bands instead of three plain outlines.
const bandsLargestFirst = (Object.entries(RING_RADIUS) as [Bucket, number][])
  .sort((a, b) => b[1] - a[1])
const center = 220

const hoveredId = ref<number | null>(null)
const hoveredPos = computed(() => positions.value.find((p) => p.unitId === hoveredId.value) ?? null)
const hoveredDetail = computed(() => (hoveredId.value !== null ? props.details[hoveredId.value] : null))
// Percentage position within the chart's own box, for placing the HTML
// hover card over the right point regardless of how the SVG is scaled.
const hoverStyle = computed(() => {
  if (!hoveredPos.value) return {}
  return {
    left: `${((center + hoveredPos.value.x) / (center * 2)) * 100}%`,
    top: `${((center + hoveredPos.value.y) / (center * 2)) * 100}%`,
  }
})

function admitRateText(rate: number | null) {
  return rate === null ? null : `${Math.round(rate * 100)}% admit rate`
}
function netPriceText(price: number | null) {
  return price === null ? null : `$${Math.round(price).toLocaleString()}/yr`
}
function distanceText(miles: number | null) {
  return miles === null ? null : `${miles.toLocaleString()} mi from home`
}
</script>

<template>
  <div class="chart-wrapper">
    <svg
      :viewBox="`0 0 ${center * 2} ${center * 2}`"
      class="star-chart"
      role="img"
      :aria-label="`Star chart for ${studentName}`"
    >
      <circle
        v-for="[bucket, r] in bandsLargestFirst"
        :key="'band-' + bucket"
        :cx="center"
        :cy="center"
        :r="r"
        :fill="bucketLightColor[bucket]"
      />
      <circle
        v-for="[bucket, r] in bandsLargestFirst"
        :key="'ring-' + bucket"
        :cx="center"
        :cy="center"
        :r="r"
        fill="none"
        stroke="var(--ink-navy)"
        stroke-width="0.5"
        opacity="0.5"
      />
      <text
        v-for="[bucket, r] in bandsLargestFirst"
        :key="'ring-label-' + bucket"
        :x="center"
        :y="center - r - 6"
        text-anchor="middle"
        class="ring-label"
        :fill="bucketColor[bucket]"
      >
        {{ bucket }}
      </text>
      <line
        v-for="p in positions"
        :key="'line-' + p.unitId"
        :x1="center"
        :y1="center"
        :x2="center + p.x"
        :y2="center + p.y"
        stroke="var(--ink-navy)"
        stroke-width="0.5"
        opacity="0.5"
      />
      <circle :cx="center" :cy="center" r="7" fill="var(--gold-leaf)" class="student-star" />
      <text :x="center" :y="center - 12" text-anchor="middle" class="student-label">{{ studentName }}</text>
      <g
        v-for="p in positions"
        :key="p.unitId"
        class="star-point"
        @click="emit('select', p.unitId)"
        @mouseenter="hoveredId = p.unitId"
        @mouseleave="hoveredId = null"
      >
        <!-- Larger transparent hit-area so click/hover doesn't require
             landing exactly on the small visible ring (fill="transparent",
             not "none" -- "none" would opt this circle out of hit-testing
             entirely). -->
        <circle :cx="center + p.x" :cy="center + p.y" r="18" fill="transparent" />
        <circle :cx="center + p.x" :cy="center + p.y" r="9" fill="var(--parchment)" :stroke="bucketColor[p.bucket]" stroke-width="1.5" />
        <text :x="center + p.x" :y="center + p.y + 3" text-anchor="middle" class="point-number" :fill="bucketColor[p.bucket]">
          {{ p.unitId }}
        </text>
      </g>
    </svg>

    <div v-if="hoveredDetail" class="hover-card" :style="hoverStyle">
      <p class="hover-name">{{ hoveredDetail.name }}</p>
      <p class="hover-line">
        <span class="hover-badge" :class="hoveredDetail.bucket.toLowerCase()">{{ hoveredDetail.bucket }}</span>
        · Match {{ hoveredDetail.matchScore }}/100
      </p>
      <p v-if="admitRateText(hoveredDetail.admissionRate) || netPriceText(hoveredDetail.netPrice)" class="hover-line">
        {{ [admitRateText(hoveredDetail.admissionRate), netPriceText(hoveredDetail.netPrice)].filter(Boolean).join(' · ') }}
      </p>
      <p v-if="distanceText(hoveredDetail.distanceMiles)" class="hover-line">
        {{ distanceText(hoveredDetail.distanceMiles) }}
      </p>
      <p class="hover-hint">Click to jump to details</p>
    </div>
  </div>
</template>

<style scoped>
.chart-wrapper {
  position: relative;
  width: 100%;
  max-width: 480px;
  margin: 0 auto;
}
.star-chart {
  width: 100%;
  display: block;
}
.star-point {
  cursor: pointer;
}
.student-star {
  animation: twinkle 3s ease-in-out infinite;
}
.student-label {
  font-family: var(--font-display);
  font-style: italic;
  font-size: 14px;
  fill: var(--ink-navy);
}
.ring-label {
  font-family: var(--font-data);
  font-style: italic;
  font-size: 10px;
}
.point-number {
  font-family: var(--font-data);
  font-weight: 700;
  font-size: 10px;
}
.hover-card {
  position: absolute;
  transform: translate(-50%, -115%);
  min-width: 160px;
  padding: 0.5rem 0.7rem;
  background: var(--parchment);
  border: 1px solid var(--ink-navy);
  border-radius: 6px;
  box-shadow: 0 2px 8px rgba(27, 42, 74, 0.25);
  pointer-events: none;
  z-index: 30;
}
.hover-name {
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 0.95rem;
  margin: 0 0 0.2rem;
}
.hover-line {
  font-family: var(--font-data);
  font-size: 0.7rem;
  margin: 0.1rem 0;
}
.hover-badge {
  padding: 0.05rem 0.4rem;
  border-radius: 999px;
  color: white;
}
.hover-badge.reach { background: var(--reach-ember); }
.hover-badge.target { background: var(--target-sage); }
.hover-badge.likely { background: var(--likely-teal); }
.hover-hint {
  font-family: var(--font-body);
  font-style: italic;
  font-size: 0.68rem;
  opacity: 0.7;
  margin: 0.3rem 0 0;
}
@keyframes twinkle {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}
@media (prefers-reduced-motion: reduce) {
  .student-star {
    animation: none;
  }
}
</style>
