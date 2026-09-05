<!-- frontend/src/App.vue -->
<script setup lang="ts">
import { ref } from 'vue'
import InputView from './views/InputView.vue'
import ResultsView from './views/ResultsView.vue'
import LoadingChart from './components/LoadingChart.vue'
import { generateList, type GenerateListResponse } from './api'

const result = ref<GenerateListResponse | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

async function handleSubmit(description: string) {
  loading.value = true
  error.value = null
  try {
    result.value = await generateList(description)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Something went wrong. Please try again.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main>
    <InputView v-if="!result && !loading" @submit="handleSubmit" />
    <LoadingChart v-if="loading" />
    <p v-if="error" class="status error">{{ error }}</p>
    <ResultsView v-if="result" :result="result" student-name="Your Student" />
  </main>
</template>

<style scoped>
.status {
  text-align: center;
  font-family: var(--font-display);
  font-style: italic;
  margin-top: 4rem;
}
.error {
  color: var(--reach-ember);
}
</style>
