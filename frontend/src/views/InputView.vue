<!-- frontend/src/views/InputView.vue -->
<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'

const emit = defineEmits<{ submit: [description: string] }>()
const description = ref('')

function handleSubmit() {
  if (description.value.trim().length < 10) return
  emit('submit', description.value)
}

// A dim field of small background stars plus a handful of brighter
// "named" gold stars connected into a constellation -- generated once per
// page load (not per-render) so the field is stable for the whole visit
// but varies visit to visit, like actually looking up at the sky.
function randomStars(count: number, sizeRange: [number, number]) {
  return Array.from({ length: count }, () => ({
    top: Math.random() * 100,
    left: Math.random() * 100,
    size: sizeRange[0] + Math.random() * (sizeRange[1] - sizeRange[0]),
    duration: 4 + Math.random() * 6,
    delay: Math.random() * 6,
  }))
}

const backgroundStars = randomStars(55, [1, 2.2])
// The constellation: a handful of brighter stars, biased toward the outer
// thirds of the frame so they frame the input column rather than sit
// behind it, connected in sequence into one continuous line -- the same
// "chart a path between named stars" idea the result page's chart pays
// off for real.
const constellationStars = Array.from({ length: 8 }, (_, i) => {
  const edge = i % 2 === 0
  return {
    top: 8 + Math.random() * 84,
    left: edge ? Math.random() * 22 : 78 + Math.random() * 22,
    size: 2.6 + Math.random() * 2,
    duration: 3 + Math.random() * 3,
    delay: Math.random() * 4,
  }
})
const constellationPoints = constellationStars.map((s) => `${s.left},${s.top}`).join(' ')

// Subtle parallax: the constellation (closer) drifts a bit more than the
// dim background field (farther) as the cursor moves, for real depth
// rather than a flat sticker of dots. Skipped for reduced-motion.
const parallax = ref({ x: 0, y: 0 })
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

function handleMouseMove(e: MouseEvent) {
  parallax.value = {
    x: (e.clientX / window.innerWidth - 0.5) * 2,
    y: (e.clientY / window.innerHeight - 0.5) * 2,
  }
}

onMounted(() => {
  if (!prefersReducedMotion) window.addEventListener('mousemove', handleMouseMove)
})
onUnmounted(() => {
  window.removeEventListener('mousemove', handleMouseMove)
})
</script>

<template>
  <div class="input-view">
    <svg class="starfield" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      <g
        class="layer layer-far"
        :style="{ transform: `translate(${parallax.x * 0.6}px, ${parallax.y * 0.6}px)` }"
      >
        <circle
          v-for="(star, i) in backgroundStars"
          :key="'bg-' + i"
          :cx="star.left"
          :cy="star.top"
          :r="star.size * 0.12"
          fill="var(--ink-navy)"
          class="twinkle"
          :style="{ animationDuration: `${star.duration}s`, animationDelay: `${star.delay}s` }"
        />
      </g>
      <g
        class="layer layer-near"
        :style="{ transform: `translate(${parallax.x * 1.6}px, ${parallax.y * 1.6}px)` }"
      >
        <polyline
          :points="constellationPoints"
          fill="none"
          stroke="var(--ink-navy)"
          stroke-width="0.08"
          class="constellation-line"
        />
        <circle
          v-for="(star, i) in constellationStars"
          :key="'const-' + i"
          :cx="star.left"
          :cy="star.top"
          :r="star.size * 0.55"
          fill="var(--gold-leaf)"
          opacity="0.18"
          class="glow"
        />
        <circle
          v-for="(star, i) in constellationStars"
          :key="'core-' + i"
          :cx="star.left"
          :cy="star.top"
          :r="star.size * 0.16"
          fill="var(--gold-leaf)"
          class="twinkle-bright"
          :style="{ animationDuration: `${star.duration}s`, animationDelay: `${star.delay}s` }"
        />
      </g>
    </svg>
    <div class="vignette" aria-hidden="true" />
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
  position: fixed;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.layer {
  transition: transform 0.2s ease-out;
}
.twinkle {
  animation-name: twinkle;
  animation-timing-function: ease-in-out;
  animation-iteration-count: infinite;
}
.twinkle-bright {
  animation-name: twinkle-bright;
  animation-timing-function: ease-in-out;
  animation-iteration-count: infinite;
}
.constellation-line {
  opacity: 0.22;
}
.vignette {
  position: fixed;
  inset: 0;
  pointer-events: none;
  background: radial-gradient(ellipse 60% 55% at 50% 45%, var(--parchment) 45%, transparent 78%);
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
  background: rgba(255, 255, 255, 0.35);
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
@keyframes twinkle {
  0%, 100% { opacity: 0.15; }
  50% { opacity: 0.55; }
}
@keyframes twinkle-bright {
  0%, 100% { opacity: 0.55; }
  50% { opacity: 1; }
}
@media (prefers-reduced-motion: reduce) {
  .twinkle, .twinkle-bright {
    animation: none;
    opacity: 0.5;
  }
  .layer {
    transition: none;
  }
}
</style>
