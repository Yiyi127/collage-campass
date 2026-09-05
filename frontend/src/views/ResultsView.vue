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
    <p class="original-label">Original request</p>
    <p class="original-description">“{{ result.original_description }}”</p>
    <StarChart :colleges="chartColleges" :student-name="studentName" />
    <p class="summary">{{ result.student_summary }}</p>
    <section class="legend">
      <p class="legend-title">What Reach / Target / Likely mean</p>
      <p class="legend-item"><span class="legend-dot reach"></span><strong>Reach</strong> — a competitive school; admission is not guaranteed based on this profile.</p>
      <p class="legend-item"><span class="legend-dot target"></span><strong>Target</strong> — a strong, realistic match for this profile.</p>
      <p class="legend-item"><span class="legend-dot likely"></span><strong>Likely</strong> — a high probability of admission based on this profile (no school is ever guaranteed).</p>
    </section>
    <div class="cards">
      <SchoolCard
        v-for="(college, i) in result.colleges"
        :key="college.name"
        :college="college"
        :index="i + 1"
      />
    </div>
    <section v-if="result.dream_school_exceptions.length" class="exceptions">
      <h2 class="exceptions-title">Dream Schools — Noted Exceptions</h2>
      <div
        v-for="exception in result.dream_school_exceptions"
        :key="exception.name + exception.reason"
        class="exception"
      >
        <p class="exception-name">{{ exception.name }}</p>
        <p class="exception-reason">{{ exception.reason }}</p>
      </div>
    </section>
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
.original-label {
  font-family: var(--font-data);
  font-size: 0.7rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  text-align: center;
  opacity: 0.7;
  margin: 0 0 0.25rem;
}
.original-description {
  font-family: var(--font-body);
  font-style: italic;
  font-size: 0.9rem;
  text-align: center;
  max-width: 560px;
  margin: 0 auto 1.5rem;
  opacity: 0.85;
}
.summary {
  font-family: var(--font-body);
  font-style: italic;
  text-align: center;
  margin: 1rem 0 2rem;
}
.legend {
  margin: 0 0 1.5rem;
  padding: 0.9rem 1.1rem;
  border: 1px solid var(--ink-navy);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.2);
}
.legend-title {
  font-family: var(--font-display);
  font-weight: 700;
  margin: 0 0 0.5rem;
}
.legend-item {
  font-family: var(--font-body);
  font-size: 0.85rem;
  margin: 0.3rem 0;
}
.legend-dot {
  display: inline-block;
  width: 0.6rem;
  height: 0.6rem;
  border-radius: 50%;
  margin-right: 0.4rem;
}
.legend-dot.reach { background: var(--reach-ember); }
.legend-dot.target { background: var(--target-sage); }
.legend-dot.likely { background: var(--likely-teal); }
.exceptions {
  margin: 2rem 0 0;
  padding: 1rem 1.25rem;
  border: 1px solid var(--gold-leaf);
  border-radius: 6px;
  background: rgba(184, 134, 46, 0.07);
}
.exceptions-title {
  font-family: var(--font-display);
  font-size: 1.15rem;
  font-weight: 700;
  margin: 0 0 0.75rem;
  color: var(--ink-navy);
}
.exception + .exception {
  margin-top: 0.9rem;
  padding-top: 0.9rem;
  border-top: 1px solid rgba(27, 42, 74, 0.2);
}
.exception-name {
  font-family: var(--font-display);
  font-size: 1.05rem;
  font-weight: 700;
  margin: 0;
}
.exception-reason {
  font-family: var(--font-body);
  font-size: 0.9rem;
  margin: 0.25rem 0 0;
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
