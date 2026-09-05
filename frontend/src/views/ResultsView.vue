<!-- frontend/src/views/ResultsView.vue -->
<script setup lang="ts">
import StarChart from '../components/StarChart.vue'
import SchoolCard from '../components/SchoolCard.vue'
import { downloadPdf, type GenerateListResponse } from '../api'

const props = defineProps<{ result: GenerateListResponse; studentName: string }>()

const chartColleges = props.result.colleges.map((c, i) => ({
  unitId: i,
  name: c.name,
  bucket: c.bucket,
}))

function handleDownload() {
  downloadPdf(props.result)
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
</style>
