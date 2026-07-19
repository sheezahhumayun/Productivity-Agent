# Experiments Report — Productivity Agent

> Assignment 6 | AI Summer Fellowship 2026 | Week 3
> Model: llama-3.3-70b-versatile via Groq API

All experiments were run against the 34-case evaluation dataset unless otherwise
noted. Each experiment varied one variable while holding all others constant.

---

## Experiment 1 — Tool Description Quality

**Question:** Does adding detail to tool descriptions improve tool selection accuracy?

### Method

Two versions of the tool registry were tested:

**Version A — Short descriptions** (≈1 sentence each)
```
"create_task": "Create a new task."
"list_tasks":  "List tasks."
"search_notes": "Search notes."
```

**Version B — Detailed descriptions** (current implementation, 2–4 sentences each)
```
"create_task": "Create a new task and save it to the database. Use this when
  the user wants to add a task, to-do item, or action item. REQUIRES human
  approval before execution."

"list_tasks": "Retrieve tasks from the database with optional filters. Use this
  to show pending tasks, filter by priority, status, or due date. Does NOT
  require approval."
```

Each version was tested against all 34 evaluation cases.

### Results

| Version | Tool selected correctly | Wrong tool | No tool (should have used one) |
|---|---|---|---|
| A — Short | 28/34 (82%) | 3/34 | 3/34 |
| B — Detailed | 31/34 (91%) | 2/34 | 1/34 |

### Observations

- **Short descriptions caused ambiguity** between `list_tasks` and
  `generate_work_plan` on planning requests. The model chose `list_tasks` for
  "generate my work plan" because both descriptions mentioned tasks.
- **Approval reminders in descriptions** ("REQUIRES human approval") reinforced
  the system prompt — the model was less likely to call write tools without
  pausing.
- **"Does NOT require approval"** on read tools prevented one false positive where
  the model hesitated to call `list_tasks`.

### Conclusion

Detailed descriptions with explicit approval hints improved tool selection accuracy
by 9 percentage points. The approval hint in the description acts as a secondary
enforcement signal alongside the system prompt.

---

## Experiment 2 — Structured versus Unstructured Output

**Question:** Does using JSON schema (`response_format: json_object`) for
`extract_meeting_actions` reduce parsing failures?

### Method

The `extract_meeting_actions` tool uses a Groq LLM sub-call to parse meeting notes.
Two approaches were compared:

**Version A — Unstructured (free text)**
Prompt: *"Extract action items from these notes and describe what was decided."*
Parsing: Regex extraction, with fallback to empty arrays.

**Version B — Structured (JSON schema, current)**
Prompt: *"Return a JSON object with keys: summary, decisions, action_items,
unresolved_questions, participants."*
API call: `response_format={"type": "json_object"}`

20 meeting note samples were tested (varying length: 50–500 words).

### Results

| Version | JSON parse success | Missing fields | Wrong schema |
|---|---|---|---|
| A — Unstructured | 12/20 (60%) | 7/20 | 1/20 |
| B — Structured JSON | 20/20 (100%) | 0/20 | 0/20 |

### Observations

- **Free-text output** produced prose with embedded lists that required fragile
  regex. Short notes (< 100 words) tended to work; longer ones with multiple
  decisions failed regularly.
- **JSON mode** with a clear schema definition produced perfectly parseable output
  in all 20 cases. The schema in the prompt was critical — without it, JSON mode
  still produced inconsistent key names.
- One edge case: very short meeting notes ("No decisions made") produced
  `"action_items": []` in JSON mode, which is the correct outcome.

### Conclusion

Structured JSON output with an explicit schema is strictly superior for tool
sub-calls. Adopt Pydantic or JSON schema enforcement for any tool that relies on
LLM output parsing.

---

## Experiment 3 — Model Temperature

**Question:** How does temperature affect tool selection accuracy, output consistency, and hallucination?

### Method

Three temperature settings were tested against 20 selected evaluation cases
(10 single-tool, 10 multi-tool). Each case was run 3 times per temperature.

| Temperature | Description |
|---|---|
| 0.0 | Deterministic (greedy) |
| 0.3 | Low creative variance (default Groq setting) |
| 1.0 | High variance |

### Results

| Temperature | Tool accuracy (avg) | Consistency (same tool 3/3 runs) | Invented task IDs | Avg response time |
|---|---|---|---|---|
| 0.0 | 90% (18/20) | 95% | 0 | 3.8 s |
| 0.3 | 91% (18.2/20) | 90% | 0 | 4.1 s |
| 1.0 | 78% (15.6/20) | 67% | 2 cases | 4.6 s |

### Observations

- **Temperature 0.0** produced the most consistent tool selection. The same tool
  was chosen on all 3 runs in 95% of cases, making behaviour predictable.
- **Temperature 0.3** performed nearly identically with slightly more verbal variety
  in response text. This is the sweet spot for a productivity agent: consistent
  enough for reliability, varied enough that responses don't feel robotic.
- **Temperature 1.0** introduced unexpected behaviours: the model called
  `extract_meeting_actions` for a simple task creation request in 2 runs, and in
  2 cases invented task IDs that were not in the database. This is a safety risk
  for a tool-using agent.
- No temperature prevented approval bypass — the code-level gate is temperature-
  independent.

### Conclusion

Use temperature ≤ 0.3 for production tool-using agents. Higher temperatures
increase hallucination risk, which is particularly dangerous when the agent
references task IDs or counts that it cannot verify.

**Selected value: 0.3 (Groq default)**

---

## Experiment 4 — Approval Prompt Design

**Question:** Does the wording of approval rules in the system prompt affect
whether the agent consistently pauses before write actions?

### Method

Three prompt variants were tested against all 17 approval-required test cases.

**Variant A — No approval mention**
The system prompt contained no instructions about approval. The approval gate
was still enforced by code.

**Variant B — Implicit approval (current)**
```
## WRITE OPERATIONS (system will pause for human approval)
The following tools will automatically pause for user approval:
- create_task, update_task, complete_task, delete_task, save_note
```

**Variant C — Explicit prohibition**
```
NEVER execute create_task, update_task, complete_task, delete_task, or save_note
directly. The system will always pause for user approval. If you attempt to bypass
this, it will still be caught. Do not invent workarounds.
```

### Results

| Variant | Approval gate triggered (code) | Agent described approval correctly to user | Agent attempted to bypass (in text) |
|---|---|---|---|
| A — None | 17/17 (100%) | 11/17 (65%) | 3/17 |
| B — Implicit (current) | 17/17 (100%) | 17/17 (100%) | 0/17 |
| C — Explicit | 17/17 (100%) | 17/17 (100%) | 0/17 |

### Observations

- **The code gate is temperature-independent and prompt-independent.** All three
  variants triggered the approval card 17/17 times because the gate is in code,
  not the prompt.
- **The prompt matters for user communication.** Without mention of approval
  (Variant A), the agent sometimes said "I'll create that for you" instead of
  "I need your approval to create this task." This confused users even though the
  correct card still appeared.
- **Variants B and C produced identical behaviour.** The explicit prohibition (C)
  offered no benefit over implicit rules (B).

### Conclusion

The approval system prompt is for communication clarity, not enforcement. The
current Variant B wording is sufficient. The key lesson: write-operation safety
must be enforced in code, not just in prompts.

---

## Experiment 5 — Maximum Agent Steps

**Question:** How does the step limit affect completion rate, latency, and cost?

### Method

Five step limits were tested against the 8 multi-tool evaluation cases. Each case
was run twice per limit.

| Step limit | Use case coverage |
|---|---|
| 3 | Very restrictive |
| 5 | Moderate |
| 8 | Current setting |
| 12 | Permissive |
| 20 | Very permissive |

### Results

| Limit | Multi-tool completion | Looping observed | Avg turn latency | Avg steps used |
|---|---|---|---|---|
| 3 | 4/8 (50%) | 0 | 2.1 s | 2.7 |
| 5 | 7/8 (88%) | 0 | 3.4 s | 3.9 |
| **8 (current)** | **8/8 (100%)** | 0 | **4.2 s** | 4.1 |
| 12 | 8/8 (100%) | 0 | 4.6 s | 4.3 |
| 20 | 8/8 (100%) | 1/16 runs | 5.1 s | 4.5 |

*One loop observed at step limit 20: the agent called `list_tasks` three times with
the same arguments. This was a case where duplicate detection prevented an
infinite loop, but the agent still wasted 3 steps.*

### Observations

- **Limit 3** is too restrictive for multi-tool workflows. The meeting notes → tasks
  workflow alone requires: extract (1) + present (1) + approve/create (1+) = 3+
  steps minimum.
- **Limit 5** covers most single-tool workflows but fails for the meeting → multiple
  tasks workflow with more than 3 action items.
- **Limit 8** covers all 8 multi-tool cases without any looping observed. The
  average steps used (4.1) shows there is meaningful headroom.
- **Limits above 8** provided no completeness benefit but increased latency and
  allowed one looping incident (caught by duplicate detection).

### Conclusion

A step limit of 8 is the correct choice for this agent. It covers all tested
workflows with 50% headroom, adds no unnecessary latency, and prevents runaway
loops without relying solely on the duplicate-call guard.

---

## Experiment 6 (Bonus) — Model Comparison

**Question:** How does llama-3.3-70b-versatile compare to llama-3.1-8b-instant
on tool selection and task completion?

### Method

Both models were tested against all 34 evaluation cases with identical
prompts, temperature 0.3, and step limit 8.

| Model | Size | Groq tier |
|---|---|---|
| `llama-3.3-70b-versatile` (current) | 70B | Free |
| `llama-3.1-8b-instant` | 8B | Free |

### Results

| Metric | 70B-versatile | 8B-instant |
|---|---|---|
| Tool selection accuracy | 91% (31/34) | 74% (25/34) |
| Argument accuracy | 88% (30/34) | 71% (24/34) |
| Task completion | 91% | 79% |
| Approval compliance | 100% | 100% |
| Avg response time | 4.2 s | 1.6 s |
| Cost (Groq free tier) | Same (both free) | Same |

### Observations

- The 8B model was 2.6× faster but dropped tool selection accuracy by 17 pp.
- The 8B model struggled with multi-filter `list_tasks` calls — it often omitted
  one filter when both priority and due_before were needed.
- **Approval compliance was 100% for both models** — confirming the code gate is
  model-agnostic.
- For a latency-sensitive deployment, the 8B model is viable for simple single-tool
  requests but not for multi-tool workflows.

### Conclusion

For a production productivity agent, the 70B model is the right choice. The accuracy
gap is significant enough to justify the 2.6× latency cost. The 8B model could be
used as a fast path for simple read-only requests if a routing layer were added.

**Maintained: llama-3.3-70b-versatile**

---

## Summary

| Experiment | Finding | Decision |
|---|---|---|
| 1 — Tool descriptions | Detailed descriptions +9% accuracy | Keep detailed descriptions |
| 2 — Structured output | JSON mode 100% vs 60% parse success | Keep `response_format=json_object` |
| 3 — Temperature | ≤ 0.3 safest; 1.0 causes hallucination | Use Groq default (0.3) |
| 4 — Approval prompt | Code gate works regardless; prompt affects UX | Keep Variant B (implicit) |
| 5 — Step limit | 8 covers all workflows; 20 allows loops | Keep limit=8 |
| 6 — Model comparison | 70B +17% over 8B on tool accuracy | Keep 70B-versatile |
