<script setup lang="ts">
import { computed } from 'vue'
import { computeStarPositions, RING_RADIUS, type CollegeForChart, type Bucket } from '../chart/geometry'

const props = defineProps<{
  colleges: CollegeForChart[]
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
</script>

<template>
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
    <g v-for="(p, i) in positions" :key="p.unitId" class="star-point" @click="emit('select', p.unitId)">
      <circle :cx="center + p.x" :cy="center + p.y" r="9" fill="var(--parchment)" :stroke="bucketColor[p.bucket]" stroke-width="1.5" />
      <text :x="center + p.x" :y="center + p.y + 3" text-anchor="middle" class="point-number" :fill="bucketColor[p.bucket]">
        {{ i + 1 }}
      </text>
      <title>{{ p.name }}</title>
    </g>
  </svg>
</template>

<style scoped>
.star-chart {
  width: 100%;
  max-width: 480px;
  display: block;
  margin: 0 auto;
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
