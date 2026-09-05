<!-- frontend/src/views/ResultsView.vue -->
<script setup lang="ts">
import { ref } from 'vue'
import StarChart from '../components/StarChart.vue'
import SchoolCard from '../components/SchoolCard.vue'
import { downloadPdf, type GenerateListResponse } from '../api'

const props = defineProps<{ result: GenerateListResponse; studentName: string }>()

const chartColleges = props.result.colleges.map((c, i) => ({
  unitId: i,
  name: c.name,
  bucket: c.bucket,
}))

const downloadError = ref<string | null>(null)

async function handleDownload() {
  downloadError.value = null
  try {
    await downloadPdf(props.result)
  } catch (e) {
    downloadError.value = e instanceof Error ? e.message : 'Failed to download PDF. Please try again.'
  }
}
</script>

<template>
  <div class="results-view">
    <StarChart :colleges="chartColleges" :student-name="studentName" />
    <p class="summary">{{ result.student_summary }}</p>
    <div class="cards">
      <SchoolCard v-for="college in result.colleges" :key="college.name" :college="college" />
    </div>
    <p v-for="note in result.relaxation_notes" :key="note" class="note">{{ note }}</p>
    <button class="seal-button" @click="handleDownload">Download PDF</button>
    <p v-if="downloadError" class="status error">{{ downloadError }}</p>
  </div>
</template>

<style scoped>
.results-view {
  max-width: 720px;
  margin: 2rem auto;
  padding: 1rem;
}
.summary {
  font-family: var(--font-body);
  font-style: italic;
  text-align: center;
  margin: 1rem 0 2rem;
}
.note {
  font-family: var(--font-data);
  font-size: 0.8rem;
  color: var(--reach-ember);
}
.seal-button {
  display: block;
  margin: 2rem auto 0;
  border-radius: 50%;
  width: 90px;
  height: 90px;
  border: 2px solid var(--gold-leaf);
  background: var(--gold-leaf);
  color: var(--parchment);
  font-family: var(--font-display);
  cursor: pointer;
}
.status {
  text-align: center;
  font-family: var(--font-display);
  font-style: italic;
  margin-top: 1rem;
}
.status.error {
  color: var(--reach-ember);
}
</style>
