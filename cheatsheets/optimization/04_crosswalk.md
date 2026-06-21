# Layer 04 — Crosswalk (Intermediate Consolidation) Optimization
> dbt model: `int_drug_crosswalk.sql` — reconciles ATC (Alpha seed) ↔ pharm_class/generic_name
> (Beta NDC). This is the conformance heart of the pipeline (ADR-003). Coverage is a DQD KPI,
> deliberately **not** 100%. See [00_INDEX.md](00_INDEX.md) for card format.

---

### XWK-01 — `ephemeral` materialization for an intermediate step  [✅ DONE]
- **Junior mistake:** Materialize the intermediate crosswalk as a `table` (or `view`) "so I can inspect it".
- **Why it bites:** Creates a persisted artifact nobody queries directly, adds storage + an extra object to the catalog, and invites someone to join to it as if it were a source of truth.
- **Optimized (this repo):** `materialized='ephemeral'` → dbt inlines it as a CTE into the consumers (`dim_drug`), no physical object, no clutter. `dbt/models/intermediate/int_drug_crosswalk.sql:19`
- **Business one-liner:** "Internal plumbing stays internal — no stray tables for people to misuse or pay to store."
- **Soundbite:** *"Ephemeral says 'this is a step, not a deliverable.'"*

### XWK-02 ★ — Exclude combination products from fuzzy matching  [✅ DONE]
- **Junior mistake:** Fuzzy-match every free-text drug name to one ATC code — including 2-ingredient combination products — to push the coverage % up.
- **Why it bites:** A combination product tagged with **one** ingredient's ATC code is a *confident wrong answer* — "worse than unmatched" (Phase-4 review verdict). It silently corrupts the coverage KPI: a wrong match counts as covered.
- **Optimized (this repo):** combos are detected (`generic_name` contains `" and "` / `" with "` / `"/"`) and routed to `combination_unverified`, **never** `fuzzy`. `int_drug_crosswalk.sql:7-11,26-27,51-54`
- **Business one-liner:** "We'd rather report 'unknown' than a confident lie. Coverage that includes wrong matches isn't coverage — it's hidden risk."
- **Soundbite:** *"A confident wrong answer is the most expensive output a pipeline can produce."*
- **Related:** XWK-06, GLD-07, DQ-02 (honest-coverage thread)

### XWK-03 ★ — Word-boundary regex, not naive `LIKE` substring  [✅ DONE]
- **Junior mistake:** Match generic names with `pharm_class LIKE '%' || hint || '%'` style substring containment for the fuzzy tier.
- **Why it bites:** A short seed token false-positives *inside* an unrelated longer word, producing wrong matches that look plausible.
- **Optimized (this repo):** the fuzzy tier uses `regexp_matches(..., '\b' || ... || '\b')` — anchored on word boundaries. `int_drug_crosswalk.sql:12-13,49`
- **Business one-liner:** "Name matching respects word boundaries, so we don't accidentally link unrelated drugs that merely share letters."
- **Soundbite:** *"`LIKE '%x%'` is how 'cat' matches 'category'. Word boundaries are how you stop it."*

### XWK-04 ★ — Tiered match with a deterministic tie-break  [✅ DONE]
- **Junior mistake:** Take "a" match per product with no defined precedence and no tie-break.
- **Why it bites:** Two seed rows hitting the same tier for one product produce a row that changes between runs — the crosswalk (and every fact built on it) becomes non-reproducible.
- **Optimized (this repo):** `row_number()` ranks by tier (`exact > normalized > fuzzy > combination_unverified`) with a **secondary `order by atc_code`** tie-break; keep `rn = 1`. Same input → same output, every run. `int_drug_crosswalk.sql:60-78`
- **Business one-liner:** "Re-running the pipeline gives byte-identical results — auditors and downstream models can trust it's stable."
- **Soundbite:** *"If a tie can change your output between runs, you don't have a pipeline, you have a coin flip."*

### XWK-05 — Length guard against promiscuous short-name matches  [✅ DONE]
- **Junior mistake:** Allow fuzzy matching on seed generics of any length.
- **Why it bites:** A very short generic name matches almost everything, inflating coverage with noise.
- **Optimized (this repo):** fuzzy + combination tiers require `length(example_generic) >= 5` — documents and enforces the safe boundary (no current seed triggers it, but it fences future additions). `int_drug_crosswalk.sql:14-16,48,52`
- **Business one-liner:** "A guardrail stops a future short code from quietly matching everything — the rule is safe to extend."
- **Soundbite:** *"Guard the boundary today so tomorrow's seed row can't blow up the match rate."*

### XWK-06 ★ — Coverage is a KPI, not a target to force to 100%  [✅ DONE]
- **Junior mistake:** Treat unmatched products as failures and fabricate links until "100% matched".
- **Why it bites:** Forced matches are wrong matches (see XWK-02) — you trade an honest gap for silent corruption, and lose the ability to *measure* match quality.
- **Optimized (this repo):** unmatched stays `'unmatched'` (`coalesce(..., 'unmatched')`), surfaced as a tracked DQD coverage KPI rather than hidden. `int_drug_crosswalk.sql:4,86`
- **Business one-liner:** "Match coverage is a number we report and improve — not a vanity metric we fake to look complete."
- **Soundbite:** *"100% coverage on dirty source data is a confession, not an achievement."*
- **Related:** XWK-02, GLD-07, DQ-02 (honest-coverage thread)

### XWK-07 — Best-match LEFT JOIN keeps every product  [✅ DONE]
- **Junior mistake:** `INNER JOIN` the ranked matches back, so only matched products survive.
- **Why it bites:** Unmatched NDC products silently vanish from the dimension — the coverage denominator is now wrong and the gap is invisible.
- **Optimized (this repo):** `left join ranked on product_ndc and ranked.rn = 1` — every NDC row is retained, matched or not. `int_drug_crosswalk.sql:87-88`
- **Business one-liner:** "No product silently disappears because we couldn't classify it — the gap stays visible and counted."
- **Soundbite:** *"An inner join is a quiet delete. Keep the rows; null the link you couldn't make."*
