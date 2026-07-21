---
name: grill-me-plus
description: Stress-test a plan, decision, or idea through dependency-aware rounds of three high-value questions. Use when the user explicitly invokes this skill or asks to be grilled, interviewed, or challenged before acting on a consequential choice.
---

# Grill Me Plus

Interview the user until both sides share enough understanding to act. Surface the user's decisions, evidence, assumptions, risks, and unresolved disagreements. Shared understanding does not require agreement with your recommendations.

## Prepare

Map the goal, scope, constraints, and dependent decisions. Treat the **frontier** as decisions whose prerequisites are settled and that can be answered without guessing another open decision.

Find available facts in the environment, existing material, or tools. Ask the user only about goals, preferences, trade-offs, authorization, and risk acceptance.

## Ask in Rounds

Ask three independent, high-value frontier questions per round. Ask fewer only when dependencies leave fewer than three answerable questions. Prioritize decisions that change direction, have high costs, are hard to reverse, or unblock downstream work.

Number each question and include:

- why the decision matters now;
- your recommended answer and reason;
- concrete options when useful.

Make the round easy to answer by number, such as `1A, 2 agree, 3 defer`. Wait for the response before asking questions unlocked by it.

If the user follows up, challenges a recommendation, expresses doubt, or explores the current issue in more depth, pause the interview queue and resolve that discussion first. Ask only questions needed to clarify it. Then incorporate its conclusions, recompute the full frontier, and resume batches of three whenever three independent questions are available. Do not treat the discussion as answers to other open questions.

Group low-risk, reversible decisions with obvious defaults into one confirmation block. Keep high-impact decisions separate.

## Update and Finish

After each response, update the decision tree and frontier. If an upstream decision changes, identify which earlier conclusions no longer hold.

Summarize after three rounds, a major branch, an invalidated conclusion, or when no high-value questions remain. Include confirmed decisions, evidence and assumptions, open questions, and the next step.

Finish when the goal, scope, constraints, and consequential decisions are clear and the remaining questions can be deferred or handled with safe defaults. Present a final summary and ask whether it is sufficient for action.

Do not implement the plan or take side-effecting actions before that confirmation unless the user asks to decide and act in parallel. Let the user skip, accept, defer, revisit, or end the interview at any time.
