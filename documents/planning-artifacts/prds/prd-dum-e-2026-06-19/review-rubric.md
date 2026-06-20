# PRD Quality Review — Dum-E — Autonomous Robotic Videographer

## Overall verdict

This is a strong lean prototype PRD. It has a real thesis ("deterministic now, designed for learning"), 14 FRs that almost all carry testable consequences, a stable Glossary that the FRs/UJ/SMs actually use consistently, and honest scope boundaries with a well-populated Assumptions Index. It is safe to hand to architecture/epics. The one genuine tension worth surfacing before build: FR-13 (training-grade Shot Log) and the ROCm check (Open Q6) are declared v1 exit criteria for a v2 that is one week out, yet the v2 training *approach* is "undecided-by-design" — so the schema must satisfy an unspecified consumer. That is acknowledged in-line and accepted, but it is the single place where downstream work could thrash, so it deserves the most attention.

## Decision-readiness — strong

Decisions are stated as decisions, not smuggled in. The architectural bet ("deterministic now, designed for learning," §1) is explicit and the PRD repeatedly commits to it (Non-Goals §5: "Not a trained-policy system in v1"). Trade-offs name what was given up: FR-4's approval gate is justified ("auto-proceed is a later convenience"); Open Q7 explicitly accepts "slightly heavier to build" to preserve optionality on the v2 training approach. The `[NOTE FOR PM]` callouts land at real tensions — the v2 timeline (§6.2), the e-stop gap (§ Safety) — not at safe checkpoints. Open Questions are genuinely open (camera choice, control stack, frame-delivery mechanism) rather than rhetorical.

One item to flag: Open Q7 is labeled "DECIDED: undecided-by-design," which is a legitimate move (defer by over-instrumenting) but it pushes a real, unresolved design risk onto FR-13 — see Done-ness and Mechanical notes.

### Findings
- **[low]** Open Q6 (ROCm viability) is both an Open Question *and* a declared v1 exit criterion (§6.2). It is correctly flagged urgent, but as a hard gate it is more of a v1 acceptance item than an open question. *Fix:* optionally promote the ROCm validation to an explicit v1 exit-criterion line in §6.1 so it is not lost in the Open Questions list.

## Substance over theater — strong

No persona theater (correct for a solo hobby project — one named protagonist, Kamal). No innovation theater: the novelty claim ("the agent and the vision brain are Claude itself — no separate model") is concrete and load-bearing, not template furniture. The Vision statement could not swap into another PRD — it is specific to SO-101 arms, maker demos, and the Shot Log learning loop. NFR-style content (smoothness, centering) is given product-specific bounds or honestly marked as eyeballed (FR-7 assumption). This dimension is clean.

## Strategic coherence — strong

There is a clear thesis and the features serve it. The arc is: intake → survey → plan → frame → move → capture → stitch → log, and every feature group (§4.1–4.10) maps onto that arc with no orphan capabilities. Prioritization follows the thesis rather than ease: FR-13 (Shot Log) is explicitly on the critical path *because* of the v2 bet, not deferred because it is hard. Success Metrics validate the thesis rather than measuring activity — SM-3 (reuse across ≥2 projects) directly tests the "drop-in for any project" claim, and counter-metrics SM-C1/SM-C2 honestly guard against the prototype's most likely failure mode (over-polishing). This is the opposite of a backlog with headings.

## Done-ness clarity — adequate (with two soft spots)

Most FRs carry at least one verifiable consequence, and the PRD does well at bounding things that are easy to leave vague: FR-6 defines "centered" (~central 20%), FR-6/FR-12 require the loop to terminate within bounded steps, FR-10 requires a single playable file in plan order. The "graceful/reasonable/user-friendly" anti-patterns are largely absent.

Two consequences lean on adjectives the rubric tells me to flag:
- FR-7: "smooth enough to be watchable at the prototype bar (no large jerks that ruin the clip)" — explicitly eyeballed (assumption acknowledges no jerk metric). Acceptable at hobby stakes, but it is not engineer-testable as written.
- SM-1 / SM-2 success conditions ("Kamal judges good enough," "most shoots need no mid-shoot manual correction") are subjective. Fine for a solo metric; an epic author cannot derive an automated check from them.

FR-13 is the most important done-ness item and it is genuinely strong (enumerates state/action/outcome/reward/target/timestamps, requires schema versioning, validation, quarantine-on-failure, non-blocking logging, and a trainability check). The gap is upstream, not in the FR text: because the v2 training approach is undecided (Open Q7), "sufficient to train a v2 policy" cannot be fully verified now. The FR mitigates this by capturing the full RL tuple, which is the right hedge.

### Findings
- **[medium]** FR-13 "done" is defined against an undecided consumer (§4.9 + Open Q7). The FR is well-specified, but "trainable for v2" is unverifiable until the v2 approach is chosen, and v2 is only one week out. *Fix:* before building, pin a minimal concrete schema (field list + types) in the addendum and run the FR-13 "is the log trainable?" check against a hand-written sample so the schema is validated against *something* before training week, not just self-described.
- **[low]** FR-7 smoothness criterion is an adjective ("no large jerks"). *Fix:* acceptable as-is for v1; if cheap, add a coarse threshold (e.g. no single-frame subject displacement > X% of frame) so the consequence is mechanically checkable.

## Scope honesty — strong

Omissions are explicit, not inferred. §5 Non-Goals does real work (no voice, no teleop, no lighting, no general editor, no broadcast quality, no standalone app). Per-FR `Out of Scope` lines appear exactly where a reader might assume more (FR-7 orbit, FR-10 intelligent editing). The Assumptions Index (§9) round-trips well against the inline `[ASSUMPTION]` tags. Open-items density (7 Open Questions + ~11 assumptions + 3 PM notes) is high in absolute terms but entirely appropriate for a hobby PRD where the user is also the builder — none of these block a green light because the decision-maker and implementer are the same person. De-scoping (the second arm, multi-angle, learned policy) is proposed openly with rationale.

## Downstream usability — strong

This PRD feeds architecture and epics, so the dimension matters. Glossary (§3) is present and the domain nouns (Operator, Intent, Camera Arm, Scene Survey, Subject, Target, Shot Plan, Shot, Primitive, Visual servo, Critic, Clip, Final Video, Shot Log) are used identically across FRs, the UJ, and SM definitions — no synonym drift. FR IDs are contiguous and unique (FR-1…FR-14, no gaps or dupes); SM IDs (SM-1/2/3, SM-C1/2) and the single UJ-1 are clean. Cross-references resolve: FR-6→FR-14, FR-12→FR-13, FR-11→FR-14, FR-13←FR-12 all point to real targets, and MVP §6.1 enumerates the full FR set. Each FR section is self-contained via Glossary terms rather than "see above." The one named protagonist (Kamal) carries the UJ.

### Findings
- **[low]** SM-1 cites "Validates FR-1…FR-10" and SM-2 "Validates FR-3…FR-12" as ranges. Ranges are readable but FR-9 (photo) and FR-11 (calibration) and FR-14 (safety) are not obviously exercised by SM-1's video path. *Fix:* optional — confirm the ranges are intended as "the FRs this metric touches" rather than "all FRs are individually validated," or list the exact IDs.

## Shape fit — strong

The PRD is correctly shaped as a single-operator capability spec with one load-bearing UJ. It has *not* been over-formalized: no invented personas, no UJ-per-feature padding, rigor kept light. It is also not under-formalized — the one UJ (fruit-basket demo) is concrete and threads through every feature's "Realizes UJ-1" tag, which is the right amount of journey for a solo tool. The Adapt-In Hardware Constraints and Safety sections are appropriate additions for a PRD that drives a physically moving arm. Shape matches product.

## Mechanical notes

- **Glossary drift:** None found. Capitalized domain terms are used consistently; "hold-center" / "push-in" appear both as Glossary entries and inline Primitives without conflicting definitions.
- **ID continuity:** FR-1…FR-14 contiguous, unique, no gaps. SM-1/2/3 + SM-C1/2 clean. UJ-1 single. Open Q1–Q7 contiguous.
- **Cross-refs:** All internal references resolve (FR-14, FR-13, FR-11, Open Q6, UJ-1 edge case, §9 index). External ref to the brainstorming session file is cited by path (not verified here).
- **Assumptions Index roundtrip:** Inline `[ASSUMPTION]` tags in FR-2, FR-3, FR-4, FR-6, FR-7, FR-8, FR-10, FR-11, FR-12, FR-13, FR-14, plus the camera `[ASSUMPTION: USB webcam]` in Hardware Constraints and the LeRobot/Feetech one in Open Q2. The §9 index covers all of these except the inline USB-webcam assumption in Hardware Constraints — minor. The §9 "Global" entry (control transport = Bash scripts) has no single inline anchor; it is sourced from the addendum, which is acceptable.
- **UJ protagonist:** UJ-1 has a named protagonist (Kamal) carrying context inline. Good.
- **Required sections:** All present for the stakes — Vision, Target User/JTBD, Glossary, Features/FRs, Non-Goals, MVP Scope, Success Metrics, Open Questions, Assumptions Index, plus Adapt-In Hardware + Safety.

### Mechanical findings
- **[low]** The `[ASSUMPTION: USB webcam]` in Hardware Constraints is not reflected in the §9 Assumptions Index. *Fix:* add a one-line index entry for completeness.
