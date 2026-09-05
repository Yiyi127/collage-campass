// frontend/src/api.ts
export interface CollegeEntry {
  name: string
  state: string
  bucket: 'Reach' | 'Target' | 'Likely'
  confidence: string
  admission_rate: number | null
  sat_p25: number | null
  sat_p75: number | null
  program_match_type: string | null
  net_price: number | null
  affordability_basis: string | null
  is_dream_school: boolean
  rationale: string
}

export interface GenerateListResponse {
  student_summary: string
  colleges: CollegeEntry[]
  dream_school_exceptions: { name: string; reason: string }[]
  relaxation_notes: string[]
  generated_at: string
  scoring_version: string
  scorecard_data_year: string
}

export async function generateList(description: string): Promise<GenerateListResponse> {
  const res = await fetch('/api/generate-list', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ description }),
  })
  if (!res.ok) throw new Error(`Failed to generate list (${res.status})`)
  return res.json()
}

export async function downloadPdf(result: GenerateListResponse): Promise<void> {
  const res = await fetch('/api/generate-pdf', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(result),
  })
  if (!res.ok) throw new Error(`Failed to generate PDF (${res.status})`)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'college-compass-list.pdf'
  a.click()
  URL.revokeObjectURL(url)
}
