<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'

const props = defineProps<{ description: string }>()

// Phase text tracks the real pipeline stages (extraction -> eligibility +
// scoring -> bucketing/ranking -> grounded explanation) -- it's a fixed,
// hardcoded sequence rather than a true progress stream from the backend,
// but it's not decorative filler either: each line names a step that is
// actually happening, in the actual order it happens. Phase 1 echoes the
// counselor's own words back so the very first thing shown is "we're
// working on what you actually typed," not a generic placeholder.
const snippet = computed(() => {
  const text = props.description.trim()
  return text.length > 70 ? `${text.slice(0, 70)}…` : text
})

const phases = computed(() => [
  `Reading: "${snippet.value}"`,
  'Loading real College Scorecard data...',
  'Calculating match scores across academics, location, and cost...',
  'Sorting schools into Reach, Target, and Likely...',
  'Writing personalized notes for each school...',
])

const phaseIndex = ref(0)
const progress = ref(4)
let phaseTimer: ReturnType<typeof setInterval> | undefined
let progressTimer: ReturnType<typeof setInterval> | undefined

onMounted(() => {
  phaseTimer = setInterval(() => {
    phaseIndex.value = (phaseIndex.value + 1) % phases.value.length
  }, 2200)
  // Decelerating fake progress: closes most of the gap to 92% but never
  // reaches (or claims) completion on its own -- the view is swapped out
  // for the real results the moment the actual request resolves.
  progressTimer = setInterval(() => {
    progress.value += (92 - progress.value) * 0.06
  }, 200)
})

onUnmounted(() => {
  clearInterval(phaseTimer)
  clearInterval(progressTimer)
})
</script>

<template>
  <div class="loading-status">
    <p class="phase">{{ phases[phaseIndex] }}</p>
    <div class="progress-track">
      <div class="progress-fill" :style="{ width: `${progress}%` }" />
    </div>
  </div>
</template>

<style scoped>
.loading-status {
  max-width: 460px;
  margin: 4.5rem auto 0;
  padding: 0 1.5rem;
  text-align: center;
}
.phase {
  font-family: var(--font-display);
  font-style: italic;
  color: var(--ink-navy);
  min-height: 2.4em;
}
.progress-track {
  height: 6px;
  border-radius: 999px;
  background: rgba(27, 42, 74, 0.15);
  overflow: hidden;
  margin-top: 0.75rem;
}
.progress-fill {
  height: 100%;
  background: var(--gold-leaf);
  transition: width 0.2s linear;
}
</style>
