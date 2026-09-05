<!-- frontend/src/components/SchoolCard.vue -->
<script setup lang="ts">
import type { CollegeEntry } from '../api'
defineProps<{ college: CollegeEntry }>()
</script>

<template>
  <div class="school-card">
    <div class="header">
      <span class="name">{{ college.name }}</span>
      <span class="badge" :class="college.bucket.toLowerCase()">{{ college.bucket }}</span>
    </div>
    <p class="stats">
      {{ college.state }}
      <span v-if="college.admission_rate !== null">
        · {{ Math.round(college.admission_rate * 100) }}% admit rate
      </span>
      <span v-if="college.net_price !== null">
        · ${{ Math.round(college.net_price).toLocaleString() }}/yr net price
      </span>
    </p>
    <p class="rationale">{{ college.rationale }}</p>
  </div>
</template>

<style scoped>
.school-card {
  border: 1px solid var(--ink-navy);
  border-radius: 6px;
  padding: 1rem;
  margin-bottom: 0.75rem;
  background: rgba(255, 255, 255, 0.25);
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.name {
  font-family: var(--font-display);
  font-size: 1.25rem;
  font-weight: 700;
}
.badge {
  font-family: var(--font-data);
  font-size: 0.7rem;
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
  color: white;
}
.badge.reach { background: var(--reach-ember); }
.badge.target { background: var(--target-sage); }
.badge.likely { background: var(--likely-teal); }
.stats {
  font-family: var(--font-data);
  font-size: 0.85rem;
  margin: 0.4rem 0;
}
.rationale {
  font-family: var(--font-body);
  font-size: 0.95rem;
}
</style>
