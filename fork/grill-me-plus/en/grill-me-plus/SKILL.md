---
name: grill-me-plus
description: Systematically examine a plan, project, decision, or idea through dependency-aware, structured question rounds. Ask at most three independent material questions per round, continue for as many rounds as needed, and report decision progress until consequential matters are settled or safely deferred. Use only when the user explicitly invokes this skill or asks for a structured review before acting on a consequential choice.
---

# Grill Me Plus

Build enough shared understanding to act. Examine the relevant dimensions of the subject, surface decisions, evidence, assumptions, risks, and unresolved disagreements, and keep agreement distinct from understanding.

Treat the review as a collaborative examination. Do not turn it into an adversarial exercise, an attempt to find as many flaws as possible, or a requirement that the user accept your recommendation.

## Build the Review Map

Scan the relevant dimensions before following one branch deeply:

- goal, intended outcome, and success or stop criteria;
- problem evidence, users, and affected stakeholders;
- scope, constraints, resources, and authorization;
- alternatives and trade-offs;
- assumptions, dependencies, and unknown facts;
- execution, ownership, operations, and support boundaries;
- risks, reversibility, and failure conditions.

Apply only dimensions that can affect the current goal. Mark irrelevant dimensions as not applicable instead of inventing questions for them.

Classify each material item as a fact, assumption, user decision, or risk. Map dependencies between items. Treat the **frontier** as material items whose prerequisites are settled and that can be addressed now without guessing another open answer.

Find available facts in the environment, existing material, or tools. Ask the user only for user-owned information, goals, preferences, trade-offs, authorization, or risk acceptance that cannot reasonably be established otherwise.

## Select Material Questions

Treat a candidate as material only when all of the following hold:

- plausible answers would materially change the conclusion, next action, scope, resource commitment, risk acceptance, or go/no-go decision;
- the answer is not already established by available evidence and requires user-owned information or judgment;
- the item cannot be safely defaulted or deferred within the current decision horizon;
- the item is not already answered and does not depend on another open question in the same round.

If a candidate fails this test, resolve it from evidence, record a safe default, defer it, or omit it. Never ask merely because a detail is interesting, might matter someday, or can be framed as a risk.

After filtering, rank material candidates by how much they can change direction or eliminate branches, the cost and reversibility of a wrong choice, how much downstream work they unblock, and their uncertainty or time sensitivity.

## Ask in Rounds

Ask one to three independent material questions per round. Three is a hard per-round maximum, not a target and not a limit on the number of rounds. Never add lower-impact questions to fill a round. Continue for as many rounds as the review requires.

Make each numbered item exactly one user decision. Context, recommendations, options, and supporting bullets must not contain additional questions. Keep dependent decisions for later rounds.

For each question, include:

- what decision is needed and what would materially change with the answer;
- your recommended answer and reason when evidence supports one, or state that no recommendation is justified yet;
- concrete options when they make the decision easier to answer.

Make the round easy to answer by number, such as `1A, 2 agree, 3 defer`. Wait for the response before asking questions unlocked by it.

If the user follows up, challenges a recommendation, expresses doubt, or explores the current issue in more depth, pause the queued round and resolve that discussion first. Ask only what the current discussion needs. Then incorporate its conclusions, recompute the full review map and frontier, and resume rounds without treating the discussion as answers to unrelated items.

State low-risk, reversible defaults without turning each one into a separate question. Ask for one grouped confirmation only when accepting the group is itself material. Never hide a material decision in a default block.

## Update and Report Progress

After every user response, update the review map and frontier. If an upstream answer changes, identify which earlier conclusions no longer hold.

Classify each current material item as settled, an open decision, or pending evidence. Count an item as settled when it is confirmed or when a safe default or deferral cannot block the current goal.

Before the next round, report visible progress without waiting for the user to ask:

`Decision progress: about N% (X of Y current material items settled; A open decisions; B pending evidence).`

Calculate `N` as settled material items divided by all currently identified material items and round to the nearest 5%. Treat it as an estimate over the current map; if a new material branch appears, explain that the percentage can decrease.

After every three completed rounds, or after a major branch is completed or invalidated, provide a checkpoint with confirmed decisions, evidence and assumptions, deferred and open items, invalidated conclusions, and the next frontier. A checkpoint is not a stop condition. Unless the finish criteria are met or the user pauses, include the next round after the checkpoint in the same response.

## Finish

Before finishing, verify that:

- every relevant review dimension has been examined;
- no open material item could change the recommendation, next action, scope, resource commitment, risk acceptance, or go/no-go decision;
- no pending fact is being treated silently as an assumption.

Do not finish merely because three rounds have passed or a checkpoint was produced. Omit or safely defer low-level implementation details instead of promoting them into material questions.

Finish when the consequential matters are settled or safely deferred and both sides have enough shared understanding to act. Present a final summary with decision progress, confirmed decisions, evidence and assumptions, accepted risks, deferred or open items, and the next step. Ask whether the result is sufficient for action.

Let the user skip, accept, defer, revisit, or end the review at any time. If the user ends early, respect that choice and still report the current progress and remaining blockers. Do not implement the plan or take side-effecting actions before final confirmation unless the user asks to decide and act in parallel.
