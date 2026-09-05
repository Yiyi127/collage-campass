<script setup lang="ts">
withDefaults(defineProps<{ label?: string }>(), { label: 'Charting the sky...' })
</script>

<template>
  <div class="loading-chart" role="status" :aria-label="label">
    <svg viewBox="0 0 120 120" class="orbit">
      <circle cx="60" cy="60" r="7" fill="var(--gold-leaf)" class="center-star" />
      <g class="ring">
        <circle cx="60" cy="16" r="4" fill="var(--reach-ember)" />
      </g>
      <g class="ring ring-reverse">
        <circle cx="60" cy="30" r="3.5" fill="var(--target-sage)" />
      </g>
      <g class="ring">
        <circle cx="60" cy="44" r="3" fill="var(--likely-teal)" />
      </g>
    </svg>
    <p class="label">{{ label }}</p>
  </div>
</template>

<style scoped>
.loading-chart {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-top: 4rem;
}
.orbit {
  width: 96px;
  height: 96px;
}
.center-star {
  animation: twinkle 1.6s ease-in-out infinite;
  transform-origin: 60px 60px;
}
.ring {
  transform-origin: 60px 60px;
  animation: spin 2.4s linear infinite;
}
.ring-reverse {
  animation-direction: reverse;
  animation-duration: 1.7s;
}
.label {
  margin-top: 1rem;
  font-family: var(--font-display);
  font-style: italic;
  color: var(--ink-navy);
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
@keyframes twinkle {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
@media (prefers-reduced-motion: reduce) {
  .ring, .center-star {
    animation: none;
  }
}
</style>
