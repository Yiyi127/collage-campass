<!-- frontend/src/views/InputView.vue -->
<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'

const emit = defineEmits<{ submit: [description: string] }>()
const description = ref('')

function handleSubmit() {
  if (description.value.trim().length < 10) return
  emit('submit', description.value)
}

// Stars are plain HTML circles (fixed px width/height + border-radius:50%),
// not SVG shapes in a stretched viewBox -- a non-uniformly scaled SVG
// circle renders as an ellipse ("egg"), which is exactly the bug in the
// previous pass. A CSS circle stays a circle at any viewport size.
function randomStars(count: number, sizeRange: [number, number]) {
  return Array.from({ length: count }, () => ({
    top: Math.random() * 100,
    left: Math.random() * 100,
    size: sizeRange[0] + Math.random() * (sizeRange[1] - sizeRange[0]),
    duration: 4 + Math.random() * 6,
    delay: Math.random() * 6,
  }))
}

const backgroundStars = randomStars(70, [1.5, 3])

// The constellation: one graceful, hand-wobbled arc of bright gold stars
// strung across the top of the frame -- like a belt in the sky above the
// title, not scattered debris with rays crossing the whole page (the
// previous version zigzagged between the left/right edges, which read as
// noise rather than a shape). Points are monotonic in x, so the connecting
// line can only ever curve, never cross itself.
const CONSTELLATION_X = [7, 20, 33, 47, 61, 75, 88]
const constellationStars = CONSTELLATION_X.map((left, i) => ({
  left,
  top: 6 + Math.sin(i * 1.7) * 5 + Math.random() * 3,
  size: 3 + Math.random() * 2,
  duration: 3 + Math.random() * 3,
  delay: Math.random() * 4,
}))
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
    <div class="starfield" aria-hidden="true">
      <div
        class="layer layer-far"
        :style="{ transform: `translate(${parallax.x * 5}px, ${parallax.y * 5}px)` }"
      >
        <span
          v-for="(star, i) in backgroundStars"
          :key="'bg-' + i"
          class="dot dim"
          :style="{
            top: `${star.top}%`,
            left: `${star.left}%`,
            width: `${star.size}px`,
            height: `${star.size}px`,
            animationDuration: `${star.duration}s`,
            animationDelay: `${star.delay}s`,
          }"
        />
      </div>
      <svg class="lines" viewBox="0 0 100 100" preserveAspectRatio="none">
        <polyline
          :points="constellationPoints"
          fill="none"
          stroke="var(--ink-navy)"
          stroke-width="0.12"
          vector-effect="non-scaling-stroke"
          class="constellation-line"
          :style="{ transform: `translate(${parallax.x * 14}px, ${parallax.y * 14}px)` }"
        />
      </svg>
      <div
        class="layer layer-near"
        :style="{ transform: `translate(${parallax.x * 14}px, ${parallax.y * 14}px)` }"
      >
        <span
          v-for="(star, i) in constellationStars"
          :key="'const-' + i"
          class="dot bright"
          :style="{
            top: `${star.top}%`,
            left: `${star.left}%`,
            width: `${star.size}px`,
            height: `${star.size}px`,
            animationDuration: `${star.duration}s`,
            animationDelay: `${star.delay}s`,
          }"
        />
      </div>
    </div>
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
  pointer-events: none;
}
.layer {
  position: absolute;
  inset: 0;
  transition: transform 0.2s ease-out;
}
.lines {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}
.dot {
  position: absolute;
  border-radius: 50%;
  transform: translate(-50%, -50%);
}
.dot.dim {
  background: var(--ink-navy);
  animation-name: twinkle;
  animation-timing-function: ease-in-out;
  animation-iteration-count: infinite;
}
.dot.bright {
  background: var(--gold-leaf);
  box-shadow: 0 0 6px 2px rgba(184, 134, 46, 0.55);
  animation-name: twinkle-bright;
  animation-timing-function: ease-in-out;
  animation-iteration-count: infinite;
}
.constellation-line {
  opacity: 0.35;
  transition: transform 0.2s ease-out;
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
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}
@media (prefers-reduced-motion: reduce) {
  .dot {
    animation: none;
    opacity: 0.4;
  }
  .layer, .constellation-line {
    transition: none;
  }
}
</style>
