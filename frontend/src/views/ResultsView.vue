<!-- frontend/src/views/ResultsView.vue -->
<script setup lang="ts">
import { computed, ref } from 'vue'
import StarChart from '../components/StarChart.vue'
import SchoolCard from '../components/SchoolCard.vue'
import { downloadPdf, type CollegeEntry, type GenerateListResponse } from '../api'

const props = defineProps<{ result: GenerateListResponse; studentName: string }>()

// The chart and each card's number badge are keyed to this ORIGINAL order
// (Reach block, then Target, then Likely -- the order the API returns) and
// never change, even when a section is re-sorted for display below -- the
// number is an identifier, not a rank.
const numbered = props.result.colleges.map((college, i) => ({ college, index: i + 1 }))

const chartColleges = numbered.map(({ college, index }) => ({
  unitId: index,
  name: college.name,
  bucket: college.bucket,
}))
const chartDetails = Object.fromEntries(
  numbered.map(({ college, index }) => [
    index,
    {
      name: college.name,
      bucket: college.bucket,
      matchScore: college.match_score,
      admissionRate: college.admission_rate,
      netPrice: college.net_price,
      distanceMiles: college.distance_miles,
    },
  ]),
)

const highlightedIndex = ref<number | null>(null)
let highlightTimeout: ReturnType<typeof setTimeout> | undefined

function scrollToSchool(index: number) {
  document.getElementById(`school-${index}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  highlightedIndex.value = index
  clearTimeout(highlightTimeout)
  highlightTimeout = setTimeout(() => {
    highlightedIndex.value = null
  }, 1600)
}

type SortKey = 'match_score' | 'net_price' | 'distance_miles' | 'admission_rate'
const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: 'match_score', label: 'Best match' },
  { value: 'net_price', label: 'Lowest tuition' },
  { value: 'distance_miles', label: 'Closest to home' },
  { value: 'admission_rate', label: 'Highest admit rate' },
]
// Higher-is-better fields sort descending; lower-is-better sort ascending.
// A school missing that particular data point always sorts to the end,
// regardless of direction -- "unknown" is neither best nor worst.
const DESCENDING: Record<SortKey, boolean> = {
  match_score: true, admission_rate: true, net_price: false, distance_miles: false,
}

const BUCKETS = ['Reach', 'Target', 'Likely'] as const
const sortKeys = ref<Record<(typeof BUCKETS)[number], SortKey>>({
  Reach: 'match_score', Target: 'match_score', Likely: 'match_score',
})

function sortedSection(bucket: (typeof BUCKETS)[number]) {
  const key = sortKeys.value[bucket]
  const items = numbered.filter(({ college }) => college.bucket === bucket)
  const withValue = (c: CollegeEntry) => (key === 'admission_rate' ? c.admission_rate : c[key])
  return [...items].sort((a, b) => {
    const av = withValue(a.college)
    const bv = withValue(b.college)
    if (av === null && bv === null) return 0
    if (av === null) return 1
    if (bv === null) return -1
    return DESCENDING[key] ? bv - av : av - bv
  })
}

const sections = computed(() => BUCKETS.map((bucket) => ({ bucket, items: sortedSection(bucket) })))

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
    <StarChart
      :colleges="chartColleges"
      :details="chartDetails"
      :student-name="studentName"
      @select="scrollToSchool"
    />
    <p class="summary">{{ result.student_summary }}</p>
    <section class="legend">
      <p class="legend-title">What Reach / Target / Likely mean</p>
      <p class="legend-item"><span class="legend-dot reach"></span><strong>Reach</strong> — a competitive school; admission is not guaranteed based on this profile.</p>
      <p class="legend-item"><span class="legend-dot target"></span><strong>Target</strong> — a strong, realistic match for this profile.</p>
      <p class="legend-item"><span class="legend-dot likely"></span><strong>Likely</strong> — a high probability of admission based on this profile (no school is ever guaranteed).</p>
    </section>
    <section v-for="section in sections" :key="section.bucket" class="bucket-section">
      <div v-if="section.items.length" class="bucket-header">
        <h2 class="bucket-title" :class="section.bucket.toLowerCase()">{{ section.bucket }}</h2>
        <label class="sort-control">
          Sort by
          <select v-model="sortKeys[section.bucket]">
            <option v-for="opt in SORT_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
          </select>
        </label>
      </div>
      <div class="cards">
        <SchoolCard
          v-for="{ college, index } in section.items"
          :id="`school-${index}`"
          :key="college.name"
          :college="college"
          :index="index"
          :highlighted="highlightedIndex === index"
        />
      </div>
    </section>
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
.bucket-section {
  margin-bottom: 1.5rem;
}
.bucket-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  border-bottom: 1px solid var(--ink-navy);
  padding-bottom: 0.3rem;
  margin-bottom: 0.75rem;
}
.bucket-title {
  font-family: var(--font-display);
  font-size: 1.4rem;
  font-weight: 700;
  margin: 0;
}
.bucket-title.reach { color: var(--reach-ember); }
.bucket-title.target { color: var(--target-sage); }
.bucket-title.likely { color: var(--likely-teal); }
.sort-control {
  font-family: var(--font-data);
  font-size: 0.75rem;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}
.sort-control select {
  font-family: var(--font-data);
  font-size: 0.75rem;
  background: var(--parchment);
  color: var(--ink-navy);
  border: 1px solid var(--ink-navy);
  border-radius: 4px;
  padding: 0.15rem 0.4rem;
}
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
