<script setup lang="ts">
import { computed } from 'vue'
import { computeStarPositions, RING_RADII, type CollegeForChart } from '../chart/geometry'

const props = defineProps<{
  colleges: CollegeForChart[]
  studentName: string
}>()

const emit = defineEmits<{ select: [unitId: number] }>()

const positions = computed(() => computeStarPositions(props.colleges))
const bucketColor: Record<string, string> = {
  Reach: 'var(--reach-ember)',
  Target: 'var(--target-sage)',
  Likely: 'var(--likely-teal)',
}
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
      v-for="r in RING_RADII"
      :key="r"
      :cx="center"
      :cy="center"
      :r="r"
      fill="none"
      stroke="var(--ink-navy)"
      stroke-width="0.5"
      opacity="0.4"
    />
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
    <g v-for="p in positions" :key="p.unitId" class="star-point" @click="emit('select', p.unitId)">
      <circle :cx="center + p.x" :cy="center + p.y" r="5" :fill="bucketColor[p.bucket]" />
      <text :x="center + p.x" :y="center + p.y - 8" text-anchor="middle" class="school-label">
        {{ p.name }}
      </text>
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
.school-label {
  font-family: var(--font-data);
  font-size: 9px;
  fill: var(--ink-navy);
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
