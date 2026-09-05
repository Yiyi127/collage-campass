<!-- frontend/src/views/InputView.vue -->
<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{ submit: [description: string] }>()
const description = ref('')

function handleSubmit() {
  if (description.value.trim().length < 10) return
  emit('submit', description.value)
}
</script>

<template>
  <div class="input-view">
    <h1 class="title">College Compass</h1>
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
</template>

<style scoped>
.input-view {
  max-width: 640px;
  margin: 4rem auto;
  padding: 2rem;
  text-align: center;
}
.title {
  font-family: var(--font-display);
  font-size: 3rem;
  font-weight: 700;
  margin-bottom: 0.25rem;
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
</style>
