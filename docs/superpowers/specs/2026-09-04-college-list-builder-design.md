# College List Builder — Design v2.3 (frozen)

## Core Thesis

The LLM's job is limited to two things: **understanding the counselor's free-form
text** (extraction) and **writing grounded explanations** (narrative). Every
factual claim, eligibility decision, admissions-risk classification, and
ranking decision is produced by deterministic code operating on real,
versioned College Scorecard data. The LLM never invents a school, a
statistic, or an admissions probability, and never controls ranking order.

This separation is the answer to the central engineering question a reviewer
will ask: *"If I submit the same student description twice, do I get a
substantially different list?"* — No. Given the same extracted
`StudentProfile`, the same `scorecard.sqlite` snapshot, and the same scoring
code version, candidate eligibility, bucketing, and ranking are exactly
reproducible. The LLM's only remaining discretion is prose wording in the
final explanation step, which cannot alter facts, buckets, or which schools
appear.

## Goals

- Free-form text in → downloadable, print-ready PDF college list out.
- Every school-level fact shown to the student is real, sourced from College
  Scorecard, not LLM-generated.
- Every ranking/eligibility decision is explainable as a specific formula
  applied to specific real fields, not a black-box score.
- Runs entirely on free-tier infrastructure; no spend required.

## Non-Goals (explicit scope exclusions)

- No vector database, embeddings, or RAG. All matching that appears
  "semantic" (major fit, geographic fit, affordability fit) is solved with
  structured Scorecard fields and closed-form formulas — see rationale in
  the "Program Fit" and "Why not embeddings" sections below.
- No multi-agent framework, no LangChain-style orchestration. Two direct
  Anthropic API calls, called from plain application code.
- No user authentication, no database of past requests, no persistence of
  student data beyond a single request/response cycle. The app is
  stateless; nothing about a student is stored after their PDF is
  generated.
- No live third-party ranking data (US News, Niche) — no free legal API
  exists for these, and scraping is fragile and against ToS. College
  Scorecard outcome metrics (admission rate, program-level earnings, debt)
  are used as the objective "how does this school/program actually
  perform" signal instead.

## Data Strategy: build-time refresh, runtime local-only

```
make refresh-data   (run at development time and again at each deploy)
        │
        ▼
CLI script calls the live College Scorecard API:
  - paginates through the full universe of currently-operating,
    bachelor's-degree-granting institutions (institution-level fields:
    admissions, cost, size, location, CIP-2digit degree share)
  - paginates through the Field of Study endpoint for CIP-level
    (program × credential × institution) data: exact/related CIP
    availability, graduate counts, program-level median earnings/debt
        │
        ▼
Writes a versioned scorecard.sqlite file, including a `meta` table:
  { fetched_at, scorecard_data_year, schema_version }
        │
        ▼
scorecard.sqlite ships with the deployed app.
Runtime (app startup + every user request) reads ONLY this local file.
Zero external API calls during a live user request.
```

**Why this shape**: it keeps every fact traceable to a real, official
government dataset acquired via the actual public API (not fabricated),
while removing all runtime dependency on that API's uptime, latency, or
rate limits — critical for a live interview demo. It also makes the
determinism claim exact rather than hedged: given the same `scorecard.sqlite`
version, results are bit-for-bit reproducible.

The only live external API calls at runtime are the two Anthropic Claude
calls described below.

## StudentProfile (LLM Call #1 output schema)

Extracted via Claude with structured/tool-use output (JSON schema-constrained,
not free-text parsing) so downstream code can trust the shape. Malformed
output is retried once against the schema before failing the request.

```json
{
  "academics": {
    "gpa": 3.5,
    "sat": 1230,
    "act": null,
    "ap_scores": [{"subject": "Calculus BC", "score": 4}]
  },
  "interests": {
    "raw_text": "loves programming",
    "cip_2digit": "11",
    "cip_4digit_candidates": ["11.0701"],
    "importance": "preferred"
  },
  "location": {
    "home_state": "PA",
    "geo": {"stated": true, "direction": "near", "importance": "preferred"},
    "climate": {"stated": false, "preference": null, "importance": "not_mentioned"}
  },
  "financial": {
    "needs_aid": false,
    "stated_budget": null,
    "family_income": null,
    "importance": "not_mentioned"
  },
  "campus_size": {
    "stated": false, "preference": null, "importance": "not_mentioned"
  },
  "dream_schools": [],
  "narrative_context": "Wants practical, hands-on programs; not too far from home."
}
```

`academics` (GPA/AP) is retained **only as narrative context** for LLM Call
#2. It is never converted into a numeric admissions-fit score, because
College Scorecard does not publish a comparable per-school GPA distribution
of admitted students — inventing one would manufacture false precision.

`importance` values are a closed enum: `not_mentioned` / `default` /
`preferred` / `required`. This is a bounded classification task for the LLM
(low hallucination risk, same category as picking a CIP code or a US state),
not a numeric judgment — the actual weight numbers are owned entirely by
code (see Weighting below).

## Full Pipeline

```
[0] Counselor free-form text
        │
        ▼
[1] LLM Call #1 — Profile extraction → StudentProfile (schema above)
        │
        ▼
[2] Candidate Universe — query scorecard.sqlite
    Hard eligibility (exclude only):
      - not currently operating / doesn't award bachelor's degrees
      - interest specified AND no bachelor's-level graduates on record
        for that CIP (checked at cip_4digit first, falls back to cip_2digit
        family if no 4-digit-level data exists for that school)
      - any dimension with importance == "required" AND objectively
        filterable (e.g. "must stay in-state", "budget hard-capped at $25k")
        is applied here as a hard filter, not a ranking weight
    Result: the FULL set of eligible schools (not a fixed 30-50 cap) —
    typically a few hundred to low thousands of rows from local SQLite,
    fast enough to score in full.
        │
        ▼
[3] Dream School Resolution
    Fuzzy-match each dream_schools[i].name against scorecard.sqlite
    institution names.
      not found / closed / no bachelor's degrees → excluded,
        surfaced as a validation warning in the response
      found, violates a "required" hard constraint → NOT merged into the
        main pool; placed in a separate "Dream School — Noted Exception"
        section with an explicit explanation of the conflict
      found, satisfies all hard constraints → merged into the candidate
        pool from [2], tagged is_dream_school=true, goes through normal
        bucketing/scoring, but is force-included in the final shortlist
        regardless of its preference-ranking score
        │
        ▼
[4] Bucket assignment: Reach / Target / Likely (deterministic)
    confidence = "high" if both admission_rate and SAT/ACT percentile data
      exist for the school; "medium" if only one exists; "low" if neither
      (falls back to a coarse heuristic, flagged for review)

    When both signals exist:
      admission_rate < 20%        → Reach (regardless of test scores)
      20% <= rate < 40%           → Reach if student_sat < p25 else Target
                                     (never Likely in this band)
      40% <= rate < 60%           → Target if student_sat < p75 else Likely
      rate >= 60%                 → Target if student_sat < p25 else Likely

    Test-score data unavailable (test-blind/optional), admission_rate only:
      < 20% Reach / 20-50% Target / > 50% Likely   (confidence = medium)

    Neither signal available: default Target, confidence = low, flagged
    in the response for manual review.
        │
        ▼
[5] Within-bucket preference scoring (deterministic, absolute formulas —
    never normalized relative to whichever other candidates happen to be
    in this request's pool, so a school's score cannot shift just because
    the candidate set changed)

    5a. Program Fit — from Field of Study data
        match_multiplier = 1.0 if exact cip_4digit match found,
                            0.6 if only the cip_2digit family matched
        prominence = (this school's annual graduate count in this CIP)
                     / (national median graduate count for this CIP),
                     capped at 1.0; falls back to this school's CIP-2digit
                     degree-share percentage if program-level graduate
                     counts are unavailable (small-program data suppression)
        outcomes   = (this school+program's median earnings)
                     / (national median earnings for this CIP + credential
                     level), capped at 1.0; falls back to this school's
                     overall (institution-wide) median earnings if
                     program-level earnings are unavailable — and is
                     labeled as school-wide (not program-specific) in the
                     output when this fallback is used
        program_score = match_multiplier * (0.5*prominence + 0.5*outcomes)
        No major stated at all → dimension inactive (see weighting)

    5b. Geographic Fit — Haversine distance between fixed state-centroid
        coordinates (static 50-state lookup table, no external calls)
        distance <= 100mi   → 1.0
        100-300mi           → linear 1.0 → 0.7
        300-600mi           → linear 0.7 → 0.4
        600-1000mi          → linear 0.4 → 0.15
        > 1000mi            → linear toward 0
        (direction == "far" → score = 1 - above)
        climate_score = 1.0 if school_state in WARM_STATES else 0.0
          (COASTAL_STATES used instead of WARM_STATES when the stated
          major/interest is ocean/marine-related)
        If both distance and climate preferences stated → average them.
        If only one stated → use that one. If neither → dimension inactive.

    5c. Affordability Fit — anchored to a real external reference, not to
        the candidate pool
        stated_budget given:
          price <= budget           → 1.0
          budget < price <= 1.2x    → linear 1.0 → 0.5
          price > 1.2x budget       → linear 0.5 → 0
        family_income given (no stated_budget):
          use Scorecard's income-bracket-specific net price for that
          bracket, compared against the national median net price for
          that same bracket (published reference figure)
        neither given:
          use Scorecard's overall average net price, compared against the
          national median overall net price (published reference figure)
        No financial info stated at all → dimension inactive

    5d. Campus Size Fit — absolute band, not distance-from-midpoint
        preference ranges: small < 5,000 / medium 5,000-15,000 /
                            large > 15,000 (enrollment)
        inside the stated band              → 1.0
        outside                             → 1 - (overshoot / band width),
                                               floored at 0
        No size preference stated → dimension inactive

    Weighting:
      Only dimensions the student actually mentioned (importance ==
      "default" or "preferred") participate. Dimensions with
      importance == "not_mentioned" get weight 0 and are excluded
      entirely — they do NOT default to a "perfect score," since that
      would misleadingly imply a match that was never evaluated.
      ("required" dimensions were already resolved as hard filters in
      step [2] and typically do not need a ranking weight at all.)

      Active dimensions start at an equal base weight (the least-biased
      default in the absence of any evidence about which the student
      cares about more — Laplace's principle of indifference), then
      "preferred" dimensions get a 1.4x multiplier, "default" stays 1.0x,
      and the set is renormalized to sum to 100.

      total_preference_score = Σ (weight_i * score_i), used ONLY to rank
      schools within their own Reach/Target/Likely bucket — never across
      buckets.
        │
        ▼
[6] Final shortlist assembly (deterministic)
    Within each bucket, sort by total_preference_score descending.
    Target composition: ~2-3 Reach / 3-4 Target / 2-3 Likely (8-10 total).
    Dream schools are handled per their [3] resolution (merged normally,
    placed in the exception section, or excluded with a warning) —
    never silently dropped, never silently smuggled past a violated
    required constraint.
    If a bucket has fewer real candidates than the target count, include
    however many exist and record this in `relaxation_notes` — never
    fabricate a school to fill a quota.
        │
        ▼
[7] LLM Call #2 — grounded explanation only (no reordering power)
    Input: the shortlist from [6] with every fact, bucket label, and
    confidence value locked, plus the full StudentProfile including
    narrative_context.
    Allowed: write a 2-3 sentence rationale per school and a 2-3 sentence
    overall summary, citing only the real fields supplied. Personal
    descriptors from narrative_context (e.g. "quiet kid") may be used to
    frame why a school could suit the student personally, but must never
    be turned into an unverified claim about the school itself (e.g.
    "this school has a quiet culture" is hallucination — Scorecard has no
    such field).
    Not allowed: changing a bucket label, altering or inventing any
    numeric fact, moving a school between buckets, or dropping a dream
    school.
    Output is validated against the locked input; if it contradicts a
    locked field, it is rejected and retried once, then falls back to a
    templated (non-LLM) rationale for that school.
        │
        ▼
[8] Response assembly
    Adds: generated_at (timestamp), scoring_version, and the
    scorecard.sqlite meta (fetched_at, scorecard_data_year) so every
    response is traceable to an exact, versioned data snapshot.
        │
   ┌────┴────┐
   ▼         ▼
[9a] Frontend renders result, grouped by Reach/Target/Likely,
     "Download PDF" button
[9b] PDF generation (ReportLab) from the same JSON payload — web and PDF
     can never disagree, since both render one shared result object
```

## Why not embeddings / a vector DB

The four preference dimensions being scored (major, geography, cost, size)
all have exact, structured Scorecard fields available. Embedding-based
similarity would replace an exact number (e.g. "35% of degrees are in
CIP-26") with an approximate one, and Scorecard does not provide the kind of
free-text descriptive corpus (school "vibe" copy) that would make semantic
search useful — building that corpus would mean scraping college websites,
reintroducing the same ToS/fragility problem already ruled out for
rankings. A cosine-similarity number is also strictly less explainable to a
counselor than the closed-form formulas above, which directly contradicts
the project's central design thesis. Genuinely non-structurable descriptors
(the "great story," "quiet kid" character notes) are handled by LLM Call
#2's narrative step instead, not by any numeric scoring path.

## Dream schools vs. algorithmic ranking

A counselor-named dream school is a statement of student intent that the
ranking algorithm must not silently override — but it also must not be used
to bypass a constraint the student stated as required (e.g., inserting an
out-of-state dream school for a student who said they must stay in-state).
The three-way resolution in step [3] is the mechanism that keeps both of
these true at once.

## Tech stack & deployment

- Backend: Python + FastAPI. Frontend: Vue 3 + TypeScript.
- Single Render free-tier web service serves both: FastAPI serves the
  built Vue static assets at `/` and the API at `/api/*` — one deployment,
  one domain, no CORS configuration needed.
- PDF generation: ReportLab (pure Python, no system-library dependency,
  reliable in a plain container — unlike WeasyPrint, which needs
  pango/cairo present on the host).
- LLM: Anthropic Claude API, called with structured/tool-use output for
  Call #1 (schema-constrained) and a plain completion for Call #2
  (explanation text). Usage per request is two short calls — trial credit
  comfortably covers demo-level usage.
- Data: `scorecard.sqlite`, built by `make refresh-data` against the live
  College Scorecard API (institution-level + Field of Study endpoints),
  committed/deployed alongside the app. No Scorecard API key is needed at
  runtime, only at build/refresh time.

## API contract

- `POST /api/generate-list` — body `{ "description": string }` → returns
  `{ student_summary, colleges: [...], dream_school_exceptions: [...],
  relaxation_notes: [...], generated_at, scoring_version,
  scorecard_data_year }`. Each college entry includes: name, bucket,
  confidence, location, admission_rate, sat/act range, program fit
  sub-signals (match type, prominence, outcomes), net price basis used,
  distance, is_dream_school, rationale.
- `POST /api/generate-pdf` — same shape as the above response, re-sent by
  the frontend (stateless; no server-side session) → returns the PDF file
  as an attachment download.

## Frontend: "College Compass" celestial-atlas visual identity

**Direction**: an antique celestial atlas / star chart, not a sci-fi/dark
"space app." The name "Compass" points at a navigation instrument, not a
starship HUD — and a parchment-and-ink palette is inherently print-safe,
so the web result and the PDF can share one visual language instead of
needing a dark-to-light translation for print.

**Signature element**: the result page renders one circular star chart —
the student plotted as a named star at the center, three concentric rings
labeled Reach / Target / Likely (with wayfinding subtitles, e.g. "Reach —
distant stars, worth the sightline" / "Likely — stars close at hand"),
and each recommended school plotted as a star point on its ring, joined to
the center by a thin line. Distance from center is not decoration — it's
the same Reach/Target/Likely classification from stage [4], made visible.
Built as plain SVG with polar-coordinate placement (angle = index within
its ring, radius = fixed per bucket); no 3D/WebGL library. Clicking a star
opens a detail card (real stats + LLM rationale) styled as a margin note.

**Tokens**:
- Color: `--parchment #EDE3C8` (aged paper), `--ink-navy #1B2A4A` (iron-gall
  ink, used for line work and body text instead of pure black),
  `--gold-leaf #B8862E` (the student's star and key accents),
  `--reach-ember #9B3B26`, `--target-sage #5C6E4A`, `--likely-teal #2E5C55`
  (the three ring/bucket colors, muted rather than stoplight-saturated to
  keep the engraved-ink feel).
- Type: `Cormorant` for display (atlas title, student name, school names),
  `Spectral` for body/rationale text, `Space Mono` for data readouts
  (SAT range, distance, net price) styled like instrument coordinates.
  All three loaded from fonts.googleapis.com.
- Motion: a slow ambient twinkle on star points and a single orchestrated
  fade/draw-in of the rings and connecting lines on load; no scattered
  hover effects beyond a subtle glow on the active star. Respect
  `prefers-reduced-motion`.

**Pages**: (1) input — a manuscript-styled textarea ("Chart the stars for
[student]") with a wax-seal-styled submit button ("Chart the Sky"); (2)
results — the star chart plus a "Download PDF" button styled as a wax
seal.

**PDF continuity**: the same chart is redrawn as native ReportLab vector
graphics (circles, lines, points — not a screenshot) in the same
parchment/ink-navy/gold palette, so the printed document a student is
handed matches the on-screen chart and stays ink-efficient (light
background, line art, no heavy fills).

## Testing & validation (lightweight, matched to a 2-hour build)

- Schema test: LLM Call #1 output must validate against the
  `StudentProfile` JSON schema; invalid output triggers one retry.
- Invariant tests (pure functions, no mocking needed):
  - a closed/non-degree-granting school never appears in the final list
  - no recommended school violates a `required` hard constraint (outside
    the explicit Dream School Exception section)
  - LLM Call #2 output cannot alter a locked bucket/score/fact —
    validated, rejected+retried, or replaced with a template if it tries
  - a stated dream school always appears somewhere in the response
    (normal list, exception section, or an explicit exclusion warning) —
    never silently dropped
- Scoring unit tests: geographic score is monotonically decreasing with
  distance when direction="near"; any school inside a stated campus-size
  band scores the band's max value; lower net price scores >= higher net
  price when affordability is active.
- Golden end-to-end cases: the two example prompts from the assignment
  itself (the CS-focused PA student; the marine-biology student needing
  aid) run through the full pipeline and are manually checked for
  sensible, defensible output — since these are effectively the
  assignment's own acceptance criteria.
- Failure handling: malformed LLM JSON → one retry then a clear error;
  ambiguous/unmatched dream-school name → warning, not a guess; missing
  Scorecard fields for a given school → that school is skipped for the
  affected sub-signal rather than the whole request failing.
