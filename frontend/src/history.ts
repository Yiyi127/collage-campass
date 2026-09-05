// frontend/src/history.ts
import type { GenerateListResponse } from './api'

export interface HistoryEntry {
  id: string
  // Assigned once at save time and never renumbered, so "Student 3" keeps
  // meaning the third-ever generated list even after older entries roll off.
  ordinal: number
  timestamp: string
  description: string
  result: GenerateListResponse
}

const STORAGE_KEY = 'college-compass-history'
// Bounds localStorage growth (each entry holds a full college list) well
// under the ~5MB per-origin quota most browsers enforce.
const MAX_ENTRIES = 20

export function loadHistory(): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function saveHistoryEntry(description: string, result: GenerateListResponse): void {
  const existing = loadHistory()
  const entry: HistoryEntry = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    ordinal: existing.length + 1,
    timestamp: new Date().toISOString(),
    description,
    result,
  }
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...existing, entry].slice(-MAX_ENTRIES)))
  } catch {
    // Quota exceeded or storage disabled (e.g. private browsing) -- history
    // is a convenience, not the request path, so a write failure is silent.
  }
}
