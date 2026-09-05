<!-- frontend/src/components/HistoryPanel.vue -->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { loadHistory, type HistoryEntry } from '../history'

const emit = defineEmits<{ select: [entry: HistoryEntry] }>()

const open = ref(false)
const entries = ref<HistoryEntry[]>([])

function toggle() {
  if (!open.value) entries.value = loadHistory()
  open.value = !open.value
}
function close() {
  open.value = false
}
function pick(entry: HistoryEntry) {
  emit('select', entry)
  close()
}

// Newest first -- ordinal (assigned at save time) stays the stable identity
// even though display order is reversed.
const sortedEntries = computed(() => [...entries.value].reverse())

function formatDate(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
  })
}
</script>

<template>
  <button class="history-toggle" :class="{ open }" :aria-expanded="open" @click="toggle">
    History
  </button>
  <Teleport to="body">
    <div v-if="open" class="history-overlay" @click.self="close">
      <aside class="history-panel">
        <div class="history-header">
          <h2>Past Students</h2>
          <button class="history-close" aria-label="Close" @click="close">×</button>
        </div>
        <p v-if="sortedEntries.length === 0" class="history-empty">
          No students yet — generate a list and it'll show up here.
        </p>
        <ul v-else class="history-list">
          <li v-for="entry in sortedEntries" :key="entry.id">
            <button class="history-item" @click="pick(entry)">
              <span class="history-name">{{ entry.result.student_name || `Student ${entry.ordinal}` }}</span>
              <span v-if="entry.result.profile_headline" class="history-subtitle">{{ entry.result.profile_headline }}</span>
              <span class="history-date">{{ formatDate(entry.timestamp) }}</span>
            </button>
          </li>
        </ul>
      </aside>
    </div>
  </Teleport>
</template>

<style scoped>
.history-toggle {
  position: fixed;
  top: 24px;
  right: 24px;
  z-index: 25;
  padding: 0.5rem 1rem;
  border: 1px solid var(--ink-navy);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.35);
  color: var(--ink-navy);
  font-family: var(--font-data);
  font-size: 0.75rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  cursor: pointer;
}
.history-toggle.open {
  background: var(--ink-navy);
  color: var(--parchment);
}
.history-overlay {
  position: fixed;
  inset: 0;
  background: rgba(27, 42, 74, 0.35);
  z-index: 40;
  display: flex;
  justify-content: flex-end;
}
.history-panel {
  width: min(360px, 100%);
  height: 100%;
  background: var(--parchment);
  border-left: 1px solid var(--ink-navy);
  box-shadow: -4px 0 20px rgba(27, 42, 74, 0.25);
  padding: 1.25rem;
  overflow-y: auto;
  box-sizing: border-box;
}
.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--ink-navy);
  padding-bottom: 0.6rem;
  margin-bottom: 0.75rem;
}
.history-header h2 {
  font-family: var(--font-display);
  font-size: 1.2rem;
  font-weight: 700;
  margin: 0;
}
.history-close {
  border: none;
  background: none;
  font-size: 1.4rem;
  line-height: 1;
  cursor: pointer;
  color: var(--ink-navy);
}
.history-empty {
  font-family: var(--font-body);
  font-style: italic;
  font-size: 0.9rem;
  opacity: 0.75;
}
.history-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.history-item {
  width: 100%;
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  padding: 0.6rem 0.75rem;
  border: 1px solid var(--ink-navy);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.3);
  cursor: pointer;
  font-family: var(--font-body);
}
.history-item:hover {
  background: rgba(184, 134, 46, 0.12);
  border-color: var(--gold-leaf);
}
.history-name {
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 1rem;
}
.history-subtitle {
  font-family: var(--font-data);
  font-size: 0.75rem;
  opacity: 0.8;
}
.history-date {
  font-family: var(--font-data);
  font-size: 0.68rem;
  opacity: 0.6;
}
</style>
