<!-- frontend/src/views/InputView.vue -->
<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{ submit: [description: string] }>()
const description = ref('')

function handleSubmit() {
  if (description.value.trim().length < 10) return
  emit('submit', description.value)
}

// A fixed, hand-placed field of drifting background stars -- varied size,
// position, drift distance and timing so it reads as organic rather than a
// tiled pattern, without any per-render randomness that could cause layout
// shift.
const stars = [
  { top: '8%', left: '12%', size: 3, duration: 9, delay: 0 },
  { top: '15%', left: '82%', size: 2, duration: 11, delay: 1.2 },
  { top: '22%', left: '48%', size: 2, duration: 8, delay: 2.4 },
  { top: '30%', left: '6%', size: 4, duration: 13, delay: 0.6 },
  { top: '12%', left: '65%', size: 2, duration: 10, delay: 3.1 },
  { top: '40%', left: '90%', size: 3, duration: 9.5, delay: 1.8 },
  { top: '48%', left: '20%', size: 2, duration: 12, delay: 0.3 },
  { top: '60%', left: '75%', size: 3, duration: 8.5, delay: 2.9 },
  { top: '68%', left: '10%', size: 2, duration: 10.5, delay: 1.5 },
  { top: '78%', left: '55%', size: 4, duration: 11.5, delay: 0.9 },
  { top: '85%', left: '30%', size: 2, duration: 9, delay: 2.2 },
  { top: '5%', left: '35%', size: 2, duration: 13.5, delay: 3.6 },
]
</script>

<template>
  <div class="input-view">
    <div class="starfield" aria-hidden="true">
      <span
        v-for="(star, i) in stars"
        :key="i"
        class="drift-star"
        :style="{
          top: star.top,
          left: star.left,
          width: `${star.size}px`,
          height: `${star.size}px`,
          animationDuration: `${star.duration}s`,
          animationDelay: `${star.delay}s`,
        }"
      />
    </div>
    <div class="content">
      <h1 class="title">College Compass</h1>
      <p class="tagline">
        Every student is a star, shining in their own way. Somewhere in this
        galaxy of colleges is the one that fits them — we help find it.
      </p>
      <p class="subtitle">Chart the stars for your student.</p>
      <textarea
        v-model="description"
        rows="8"
        placeholder="Describe the student in your own words — interests, scores, what they're looking for..."
      />
      <button class="chart-button" :disabled="description.trim().length < 10" @click="handleSubmit">
        Chart the Sky
      </button>
    </div>
  </div>
</template>

<style scoped>
.input-view {
  position: relative;
  min-height: 100vh;
  overflow: hidden;
}
.starfield {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}
.drift-star {
  position: absolute;
  border-radius: 50%;
  background: var(--gold-leaf);
  opacity: 0.35;
  animation-name: drift-twinkle;
  animation-timing-function: ease-in-out;
  animation-iteration-count: infinite;
}
.content {
  position: relative;
  max-width: 640px;
  margin: 0 auto;
  padding: 9.5rem 2rem 3rem;
  text-align: center;
}
.title {
  font-family: var(--font-display);
  font-size: 2.2rem;
  font-weight: 700;
  margin-bottom: 0.5rem;
}
.tagline {
  font-family: var(--font-body);
  font-size: 1rem;
  max-width: 480px;
  margin: 0 auto 1.25rem;
  opacity: 0.9;
}
.subtitle {
  font-family: var(--font-display);
  font-style: italic;
  font-size: 1.1rem;
  margin-bottom: 2rem;
}
textarea {
  width: 100%;
  font-family: var(--font-body);
  font-size: 1rem;
  padding: 1rem;
  border: 1px solid var(--ink-navy);
  background: rgba(255, 255, 255, 0.3);
  border-radius: 4px;
  resize: vertical;
  box-sizing: border-box;
}
.chart-button {
  margin-top: 1.5rem;
  padding: 0.75rem 2rem;
  border-radius: 999px;
  border: 2px solid var(--gold-leaf);
  background: var(--gold-leaf);
  color: var(--parchment);
  font-family: var(--font-display);
  font-size: 1.1rem;
  cursor: pointer;
}
.chart-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
@keyframes drift-twinkle {
  0% { transform: translateY(0); opacity: 0.2; }
  50% { transform: translateY(-14px); opacity: 0.55; }
  100% { transform: translateY(0); opacity: 0.2; }
}
@media (prefers-reduced-motion: reduce) {
  .drift-star {
    animation: none;
    opacity: 0.3;
  }
}
</style>
