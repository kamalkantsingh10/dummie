# Input Reconciliation — Brainstorm vs PRD

**Source input:** `documents/brainstorming/brainstorming-session-2026-06-19-1434.md`
**Drafted PRD:** `documents/planning-artifacts/prds/prd-dum-e-2026-06-19/prd.md`
**Date:** 2026-06-19

Comparing the locked brainstorm decisions against the drafted PRD. Each gap is tagged
**(a)** genuinely missing, **(b)** intentionally deferred and the PRD says so, or
**(c)** a contradiction needing resolution.

---

## Gap 1 — Interface flipped from MCP to Claude Code Skill — **(c) contradiction**

The brainstorm locks the interface as **MCP** in three separate places, not as a casual aside
but as part of the committed concept and the locked configuration table:

- One-liner: "shipped as a drop-in **MCP** + agent package." (§COMMITTED CONCEPT)
- "**Horizontal** — reusable across every hardware project, **via MCP**." (Why it's sharp)
- "Locked architecture: … **MCP interface** …" (§COMMITTED CONCEPT)
- Morphological table row 7: "Interface | **MCP tools** called by Claude in chat." (LOCKED CONFIGURATION)

The PRD silently replaces this everywhere with "**Claude Code Skill**" (Vision §1, Glossary §3,
FR-1, Non-Goals §5: "*Not* a standalone app… it is a Claude Code Skill") and even argues a
rationale the brainstorm never made — that as a Skill "the vision brain is **Claude itself** —
no separate model, no API integration to build" (§1).

This is a genuine architectural contradiction, not a rewording. MCP and a Skill are different
packaging/distribution models, and the brainstorm's "MCP" choice was tied to the **horizontal /
reusable-across-projects** thesis (see Gap 2). The PRD does not acknowledge the switch or justify
deviating from a locked decision. **Needs explicit resolution:** either confirm the pivot to Skill
(and update the concept's "drop-in MCP package" identity) or restore MCP.

---

## Gap 2 — "Reusable drop-in package for any project" demoted from core identity to deferred — **(c) contradiction / weakened**

This was bedrock in the brainstorm — one of the four reasons "it's sharp":

- "**Horizontal** — reusable across every hardware project, via MCP." (Why it's sharp)
- Morphological table row 6: "Deliverable form | **Reusable drop-in package** for any hardware project."
- Session topic line: "A **reusable** MCP server + agent + arm-control code…"

The PRD keeps reuse only as a *secondary success metric* (SM-3: demos for ≥2 different projects)
but in §6.2 explicitly **defers the packaging**: "Packaging as a reusable MCP/server for
distribution → later; v1 is a local Skill for the builder." The Vision §1 reframes the product as
"explicitly **for me, the builder**, first."

Deferring the *packaging work* for a v1 prototype is reasonable. But the brainstorm treated
"reusable / horizontal" as a defining property of the concept itself, not a later feature. The PRD
narrows the identity to a single-operator personal tool. This is partly defensible (b)-style
deferral, but because it collides with the locked "horizontal" identity and the abandoned MCP
interface, flag as **(c)** — confirm whether "horizontal/reusable" remains the north star or has
been intentionally descoped to a personal tool.

---

## Gap 3 — Invented hard v2 deadline "week of 2026-06-26" — **(c) contradiction (added, not dropped)**

The brainstorm never dates v2. Its roadmap is purely ordinal: "v1 = … v2 = … v3 = …" and the
learning loop is described as the thing v1 *architects for*, with no schedule
("learned policy drops in later", "for v2's RL-from-VLM-reward learning loop").

The PRD introduces a concrete, load-bearing deadline in multiple places:
- FR-13 §4.9: "**v2 … is targeted for the week of 2026-06-26**, so the v1 log schema is on the
  critical path…"
- §6.2: "Learned cinematography policy … → **v2, targeted week of 2026-06-26**" and "v2 is ~1 week
  out — the FR-13 schema and ROCm check are effectively v1 exit criteria."
- Open Q6/Q7: ROCm validation and the training-approach decision both pinned to that week.

This is content **added** that has no basis in the source and materially reshapes priorities
(it makes FR-13 schema design and ROCm validation v1 exit criteria). It is not tagged as an
`[ASSUMPTION]`. If this date is a real external constraint Kamal added after the brainstorm, it
should be stated as a known input; if it was inferred, it is an unsupported invention that should
be marked as an assumption or removed. **Needs confirmation of provenance.**

---

## Gap 4 — Two camera arms reframed from "locked config" to v2-only — **(b) deferred, but the framing is weakened**

The brainstorm's morphological table row 1 is unambiguous: "Arm config | **TWO camera arms**
(uses both leader+follower) → two simultaneous angles, agent cuts between A/B." The two-arm,
cut-between-angles capability is presented as *the* locked configuration; single-arm is only the
MVP "first light" starting point ("prove the loop on one, clone to two later").

The PRD handles this correctly in substance — §6.2 defers the second arm to v2 and even flags it:
"this is the **headline v2 feature** and the reason both SO-101 arms were chosen; revisit early."
So this is a clean **(b)** intentional deferral that the PRD states.

The minor weakening: the brainstorm framed two-arms as the locked end-state and one-arm as the
temporary MVP; the PRD's Vision §1 describes the product itself as a single-arm tool ("a
camera-equipped SO-101 arm"), which subtly recenters the product identity on the MVP rather than
the locked target. Low severity — noted for tone consistency, not a blocker.

---

## Gap 5 — "Endearingly imperfect" naming rationale / emotional tone partially lost — **(a) genuinely missing (qualitative)**

The brainstorm's name choice carries explicit emotional intent: Dum-E after Tony Stark's "clumsy
robotic-arm workshop assistant… **endearingly imperfect** — which directly embodies the 'it's a
prototype, minor imperfection is acceptable' constraint." This personality/tone is a deliberate
through-line tying the *name* to the *prototype bar*.

The PRD preserves the functional half — "minor imperfection is acceptable by design" appears in
§2.2, §5, SM-C1 — but drops the **endearing/clumsy-helper character** entirely. The name origin,
the Iron Man reference, and the "personality as feature" framing do not survive into the PRD.

This is the classic qualitative loss a FR structure causes: the *rationale and feel* ("imperfection
is charming, on-brand, part of the identity") is flattened into a dry tolerance statement
("imperfection is acceptable"). Genuinely missing **(a)**. Likely harmless for engineering, but if
the product ever has user-facing copy, voice, or branding, the lost "lovable clumsy assistant"
intent is the kind of thing worth re-capturing in a brand/tone note.

---

## Gap 6 — Perception "classical CV *or* VLM" optionality narrowed to "Claude's vision only" — **(b)/(c) borderline**

The brainstorm left perception as an explicit either/or with rationale:
"Perception layer = classical object detection **or** a vision/VLM model (VLM lets you target by
free-text description… with no pre-trained classes)." Truth 5. The morphological table then
*locks* "Perception | **VLM** (text-targeted)" — so the brainstorm itself converged on VLM.

The PRD goes one step further and binds perception specifically to **Claude's native vision**
(Glossary, FR-2, FR-5: "using Claude's native vision"). This is consistent with the brainstorm's
locked VLM choice and with the Skill pivot, so it is mostly a defensible tightening **(b)**.

The borderline concern **(c)**: the brainstorm's VLM choice was generic ("a VLM"), and Open Q3 in
the PRD itself flags an unresolved latency question about how Claude even *gets* live frames inside
a Skill run. Hard-binding perception to in-Skill Claude vision before that latency question is
answered couples a locked decision to an open risk. Worth confirming that "Claude's vision"
(vs. any VLM) is a deliberate commitment and not an artifact of the unexamined Skill pivot
(Gap 1).

---

## Summary table

| # | Gap | Tag |
|---|-----|-----|
| 1 | MCP interface silently replaced by Claude Code Skill | (c) contradiction |
| 2 | "Reusable/horizontal for any project" demoted to deferred personal tool | (c) contradiction / weakened |
| 3 | Hard v2 deadline "week of 2026-06-26" invented, not in source | (c) added content, confirm provenance |
| 4 | Two-arm "locked config" reframed as v2-only | (b) deferred, minor identity drift |
| 5 | "Endearingly imperfect" clumsy-helper tone/rationale lost | (a) genuinely missing (qualitative) |
| 6 | Perception narrowed from "any VLM" to "Claude's vision" amid open latency Q | (b)/(c) borderline |

**Highest-priority resolutions:** Gaps 1, 2, 3 (the MCP→Skill pivot + reuse demotion are a single
coupled architectural deviation from locked decisions; the v2 deadline is added content with no
source basis).
