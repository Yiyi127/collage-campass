<!-- frontend/src/App.vue -->
<script setup lang="ts">
import { ref } from 'vue'
import InputView from './views/InputView.vue'
import ResultsView from './views/ResultsView.vue'
import StarLogo from './components/StarLogo.vue'
import LoadingStatus from './components/LoadingStatus.vue'
import { generateList, type GenerateListResponse } from './api'

const result = ref<GenerateListResponse | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const submittedDescription = ref('')

async function handleSubmit(description: string) {
  submittedDescription.value = description
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
    <!-- Always mounted: this is the SAME element that idles as the logo on
         the input view and grows/moves to center to become the loading
         indicator, driven purely by the `active` prop, not a v-if swap. -->
    <StarLogo :active="loading" :corner="!!result" />
    <InputView v-if="!result && !loading" @submit="handleSubmit" />
    <LoadingStatus v-if="loading" :description="submittedDescription" />
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
