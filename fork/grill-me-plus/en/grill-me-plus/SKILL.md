---
name: grill-me-plus
description: Research-first, dependency-aware examination of a consequential plan, project, decision, or idea. Build a stable review map, resolve facts from evidence, maintain a durable decision record, ask globally numbered recommendation-led questions only for user-owned choices, and report global readiness until material matters are settled or safely deferred. Use only when the user explicitly invokes this skill or requests a structured review before acting.
---

# Grill Me Plus

Build enough shared understanding to act. Examine the relevant dimensions of the subject, surface decisions, evidence, assumptions, risks, and unresolved disagreements, and keep agreement distinct from understanding.

Treat the review as a collaborative examination. Do not turn it into an adversarial exercise, an attempt to find as many flaws as possible, or a requirement that the user accept your recommendation.

## Establish the Review

Before following one branch deeply, establish:

- the goal, intended outcome, scope, non-goals, and success or stop criteria;
- user-named artifacts, existing decisions, constraints, resources, and authorization;
- a stable top-level review map covering only dimensions that can affect the goal;
- what must be settled for the result to be ready for action.

Consider problem evidence, users and stakeholders, alternatives and trade-offs, assumptions and dependencies, execution and support boundaries, risks, reversibility, and failure conditions. Mark irrelevant dimensions as not applicable instead of inventing questions for them.

Classify material items as facts, inferences, user decisions, pending evidence, or risks. Map dependencies between them. Treat the **frontier** as material items whose prerequisites are settled and that can be addressed now without guessing another open answer.

Keep the top-level map stable enough to measure the whole review. Attach ordinary new details beneath existing branches. Revise the map and explain the impact only when evidence reveals a genuinely new major branch or changes the agreed scope or finish condition.

## Maintain a Durable Record

Maintain an append-oriented durable record by default throughout the review.

- If the user provides a file path, use it directly. Create it if absent; if it exists, read it before continuing and preserve its history.
- If the user provides only a directory, recommend one concrete filename and ask before creating it.
- If no location is provided, inspect the current context for an existing record or a suitable nearby location, recommend one concrete path, and ask before using or creating it.
- If the user requests read-only work, opts out of a record, or writing is unsafe, continue without creating one and state that limitation.

Record-location coordination is operational and does not consume a substantive question number. Read-only research may continue while location approval is pending, but do not ask the first substantive question before either establishing the record or confirming the exception.

Keep the record concise and reviewable. Append:

- the goal, scope, finish condition, top-level map, and sources examined;
- facts, inferences, pending evidence, findings, direct conclusions, and their impact;
- each question, recommendation, user-response summary, decision, rationale, and downstream effect;
- corrections, superseded conclusions, deferred items, checkpoints, progress, and remaining work.

Before the first question, append the baseline, evidence examined, direct conclusions, and the question batch. After each user response, append the response and any resulting decisions or unresolved status before asking the next batch. After the record is created, treat existing content as append-only at the file-operation level: add new entries at the end and never replace, delete, or silently revise prior text except to repair accidental corruption or when the user explicitly requests an edit. Preserve prior entries; when a conclusion changes, append the old conclusion, correcting evidence, replacement conclusion, and impact rather than rewriting history to appear error-free. Do not dump raw tool output, irrelevant search noise, entire referenced artifacts, or hidden chain-of-thought.

Research and record maintenance are review activities, not implementation of the subject under review.

## Research Before Asking

Before asking any substantive question, perform impact-proportionate, maximum-effort research. Prefer established evidence over asking the user.

Use this evidence order:

1. the user's current explicit decisions;
2. user-named artifacts, existing project decisions, and project documentation;
3. code, tests, runtime results, and other direct local evidence;
4. authoritative upstream documentation and source;
5. other external sources;
6. model inference.

Read every in-scope artifact the user explicitly names before questioning or contradicting what it establishes. When the user names a directory, inspect its contents and read the materials relevant to the candidate question rather than assuming what they say. Existing decisions may be challenged only by identifying the conflicting evidence, affected conclusion, and recommended revision.

Internally generate candidate questions from the review map, use them to focus research, and then filter them before showing anything to the user:

- If evidence determines the answer, append the conclusion and impact to the record; do not present it as a choice.
- If an objective fact is still discoverable, continue researching rather than asking the user to guess.
- If evidence is currently unavailable, record the gap and its effect as pending evidence.
- Ask only when a material user-owned decision remains, such as a goal, preference, trade-off, authorization, scope choice, risk acceptance, or value judgment that evidence cannot settle.

Stop researching a candidate when the evidence is sufficient for the current level of decision, further search is unlikely to materially change the conclusion or question, or the needed evidence is currently unavailable and the gap and impact have been recorded.

## Select Material Questions

Treat a candidate as material only when all of the following hold:

- plausible answers would materially change the conclusion, next action, scope, resource commitment, risk acceptance, or go/no-go decision;
- available evidence does not already settle it and it requires user-owned judgment;
- it cannot be safely defaulted or deferred within the current decision horizon;
- it is not already answered and does not depend on another open question in the same round.

If a candidate fails this test, resolve it from evidence, record a safe default, defer it, or omit it. Never ask merely because a detail is interesting, might matter someday, or can be framed as a risk.

Do not promote required artifacts, research, validation, or an already agreed next phase into user decisions unless a material choice about their outcome or scope is genuinely still open. If no candidate survives, state the evidence-based conclusion and continue or finish; do not manufacture a choice about accepting the conclusion or taking a routine next step.

Rank the remaining candidates by how much they can change direction or eliminate branches, the cost and reversibility of a wrong choice, how much downstream work they unblock, and their uncertainty or time sensitivity.

## Ask in Rounds

When at least three independent material questions are ready, ask the three highest-value questions. Ask fewer only when fewer survive research and materiality filtering, the user is still discussing an earlier question, or unresolved dependencies make later questions premature. Three is a hard per-round maximum, not a limit on the number of rounds. Never lower the bar to fill a round, and do not ask only one when three independent high-value questions are ready.

Give each new substantive decision a globally monotonic `Q` number. Start at `Q1`, or continue after the highest number in the existing record. Never reset numbering across rounds, checkpoints, context compaction, session recovery, or Skill reloads. Clarification, explanation, or revision of an existing question retains its original number; only a new independent decision topic consumes a new number.

Make each numbered item one coherent decision topic. It may contain tightly coupled context or subpoints that lead to one decision, but must not bundle choices the user could decide independently. Keep dependent decisions for later rounds.

For each question:

1. state the relevant facts or current judgment;
2. give the recommended approach, reason, and material impact;
3. ask an open question that allows the user to agree, modify the recommendation, propose a different approach, request more explanation, defer, or skip.

When several materially distinct approaches are genuinely viable, lead with the preferred approach and then explain the other viable approaches and their trade-offs. Treat them as non-exhaustive. Never invent options or impose a coded choice or response format.

The user may answer naturally or by question number. Wait for the response before asking questions unlocked by it.

If the user follows up, challenges a recommendation, expresses doubt, corrects evidence, or explores the current issue in more depth, pause the queued round and resolve that discussion first. Do not treat exploration as agreement. Incorporate the result into the record and review map, research any new direction, and resume only after the current discussion is settled.

State low-risk, reversible defaults without turning each one into a separate question. Ask for one grouped confirmation only when accepting the group is itself material. Never hide a material decision in a default block.

## Update the Map and Report Global Progress

After each user response, distinguish what was accepted, modified, challenged, deferred, or left open. Update the durable record, the top-level map, dependencies, and frontier before proceeding. If an upstream answer changes, identify which earlier conclusions it supersedes and what downstream work is affected.

Report one rough global percentage as a qualitative, holistic judgment of how close the whole review is to its agreed finish condition and action readiness. Do not calculate it from counts, ratios, weighted scores, or averaged dimensions. Re-estimate it from current evidence by considering the stage, stable top-level review map, unresolved high-impact dependencies, pending evidence, and the gap between design convergence and action readiness. Use a coarse value, normally rounded to the nearest ten and occasionally five, and prefix it with "about" or equivalent. Explain in one sentence what most advances the estimate and what most holds it back.

Never derive or carry the current percentage forward from counts of questions, decisions, findings, materials, tasks, checkboxes, completed branches, or any other evolving inventory. Labels such as "latest snapshot", "resolved items", or "authoritative record" do not make an item-count percentage globally valid. Treat percentages or X/Y ratios with an unclear or leaf-based basis as historical claims: do not quote them as current progress. If relevant, call the earlier estimate obsolete and replace it with a fresh qualitative global judgment. A prior qualitative global estimate made under this protocol may be cited as a trend, but re-estimate the current value independently. Let dependency leverage dominate the judgment: one unresolved upstream choice can keep global progress materially lower even when many leaf items are settled.

Use stage anchors only to calibrate this judgment, never as a formula: about 20% means exploration; about 40% means the map exists but major direction remains unsettled; about 60% means the main path is converging while material decisions remain; about 80% means consequential decisions are largely settled but action specification or evidence still blocks; about 90% means only final blockers or audit remain. Reserve 100% for a passed final audit and satisfied finish condition. For example, do not write "30/36 items, so 85%"; write "about 70% overall: the main path has converged, but three upstream decisions and their implementation contracts still block action."

At a progress update, report:

- the current stage, such as exploration, main-path convergence, action specification, or final audit;
- one rough global percentage and its one-sentence qualitative rationale;
- completed top-level branches;
- remaining high-impact branches and dependencies;
- pending evidence, deferred items, and explicit exclusions.

When direction or design has converged substantially further than action or implementation detail, report those as separate qualitative readiness axes alongside the single global percentage. Do not assign percentages to the axes, count their branches, or average them. The remaining-branch inventory and dependency structure explain the percentage and are more important than the number itself.

Report progress after the initial map, about every five completed rounds, after a major branch or scope change, when the user asks, and before finishing. At a checkpoint, also summarize confirmed decisions, supporting evidence and inferences, corrections or superseded conclusions, deferred and open items, and the next frontier. Do not mechanically print a percentage after every reply. A progress update may accompany the next question batch when no pause is needed.

## Finish

Before finishing, audit that:

- every relevant review dimension and top-level branch has been examined;
- no open material decision could change the recommendation, next action, scope, resource commitment, risk acceptance, or go/no-go decision;
- no pending fact is being treated silently as an assumption;
- deferred and excluded items are explicit and safe for the current goal;
- the durable record reflects the current conclusions, corrections, and remaining work.

Do not finish merely because a fixed number of rounds or a checkpoint has passed. Omit or safely defer low-level details instead of promoting them into material questions.

Finish when consequential matters are settled or safely deferred and both sides have enough shared understanding to act. Present a final summary with the global progress or readiness, confirmed decisions, evidence and inferences, accepted risks, deferred or open items, and the recommended next step. Ask whether the result is sufficient for action.

Let the user skip, accept, defer, revisit, or end the review at any time. If the user ends early, respect that choice and report the current readiness and remaining blockers. Do not implement the subject under review or take its side-effecting actions before final confirmation unless the user asks to decide and act in parallel; this restriction does not block research or maintenance of the review record.
