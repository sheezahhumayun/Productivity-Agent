# Builder Journal — Productivity Agent

> Assignment 8 | AI Summer Fellowship 2026 | Week 3
> Maximum: two pages

---

## What I Built

A production-grade tool-using AI agent for personal productivity management.
The agent can create and manage tasks, save and search notes, extract structured
action items from meeting notes, and generate prioritised daily work plans. Every
write operation pauses for human approval before execution.

The stack: Groq API (llama-3.3-70b-versatile) via the OpenAI-compatible SDK,
Streamlit for the UI, SQLAlchemy with SQLite for persistence, Pydantic for input
validation. Ten tools, 31 automated tests, six assignment documents.

---

## Most Difficult Technical Problem

**The mid-run approval pause.** The core challenge was pausing the agent loop in
the middle of an LLM call cycle — not at the end of a turn, but mid-execution
when a write tool was encountered — then resuming it with perfect state fidelity
after the user approved or rejected.

Most examples of human-in-the-loop agents either restart the loop from scratch
(losing intermediate tool results) or use a state machine framework like LangGraph.
I needed a simpler approach that worked with vanilla Python and Streamlit.

---

## How I Solved It

The solution was to make the loop function return a value instead of blocking.
When the agent loop encounters an approval-required tool, instead of waiting, it
immediately packages all state into a `PendingApproval` dataclass — including the
full message history, step count, tool call records, and tool arguments — and
returns it to the caller.

Streamlit stores this dataclass in `st.session_state`. The UI renders the approval
card from it. When the user decides, `resume_after_approval()` unpacks the
dataclass, adds the tool result to the message history, and calls the exact same
`_run_loop()` function from where it left off.

The result is a clean functional design: the loop is a pure function that can be
started, paused (by returning), and resumed (by being called again with the saved
state). No threading, no async, no state machine framework required.

---

## Tool-Calling Errors Observed

**1. Invalid finish_reason.** Early testing with Groq's API sometimes returned
finish_reason `"length"` instead of `"stop"` or `"tool_calls"` when the response
was truncated. The loop now has a catch-all branch for unexpected finish reasons
that returns a clear error.

**2. JSON parse failure on tool arguments.** When the model was called with
temperature 1.0, it occasionally produced malformed JSON in the function arguments
field (a trailing comma inside an object). The fix was a try/except around
`json.loads(tc.function.arguments)` that defaults to an empty dict and lets
Pydantic validation surface the real error.

**3. Duplicate list_tasks calls.** On complex planning requests, the model
sometimes called `list_tasks` twice in one turn with identical arguments, then
returned a confused response that mentioned "the first call showed X, but the
second call showed Y" — even though both results were the same. The duplicate-
call detection guard fixed this by rejecting the second call with an error message.

**4. LLM ignoring the filter.** When asked "show me high priority tasks due this
week", the 70B model occasionally called `list_tasks({"priority": "high"})` without
the `due_before` argument. This happened when the system prompt did not explicitly
instruct the model to use all available filter parameters. Adding a note to the
tool description ("Use due_before to filter by deadline") reduced this to near-zero.

---

## Agent Behavior That Surprised Me

**The model handles rejection gracefully.** When a user clicks Reject on an
approval card, the tool result is `{"success": false, "status": "rejected"}`. I
expected the model to try again or loop — but in all test cases, it immediately
acknowledged the rejection and stopped trying. The system prompt instruction
("If rejected, acknowledge and stop") was effective.

**The model resolves conversational references accurately.** Asking "mark the
second one complete" after a list of tasks worked correctly in most cases. The
model resolved "second one" from the conversation history and called `complete_task`
with the right ID. This surprised me because I expected it to need explicit
context-passing code; the message history alone was sufficient.

**Temperature 1.0 caused the model to invent task IDs.** In two test runs, the
model wrote "I'll mark Task #7 as complete" and called `complete_task({"task_id": 7})`
when the most recently listed task IDs were #1–#3. This hallucination disappears
at temperature ≤ 0.3. The system prompt instruction ("Never invent task IDs") is
not sufficient — temperature control is required.

---

## What Failed During Testing

1. **Google Gemini 1.5-flash was removed from the API** mid-project after the initial
   `gemini-2.0-flash` model hit quota limits. Two models were unavailable in quick
   succession. Switching to Groq required 30 minutes of config work, after which
   everything worked on the first attempt.

2. **`_init_state()` called at module import** caused a crash on Streamlit Cloud.
   Streamlit session state is not available during import — only inside a running
   Streamlit session. The fix was moving all init calls inside `main()`.

3. **Test database isolation** — early test runs showed the DB not being cleared
   between tests. The fix was adding `Base.metadata.drop_all(engine);
   Base.metadata.create_all(engine)` in the `fresh_db` pytest fixture.

4. **The approval card appeared at the top of the chat** instead of at the end.
   Streamlit renders components in order. The fix was moving `render_approval_card()`
   to after `render_messages()`.

---

## What I Would Redesign

**Async agent loop.** The synchronous loop blocks Streamlit during long LLM calls.
Users see a spinner but no intermediate updates. A streaming approach using Groq's
streaming API would let the UI show each token as it arrives, making the experience
feel much more responsive.

**Persistent cross-session memory.** Currently the conversation resets on page
refresh. A session ID in the URL combined with a `conversation_history` table in
SQLite would let users resume previous conversations. This would make the tool
genuinely useful as a daily driver rather than just a demo.

**Batch approval.** When creating 5 tasks from meeting notes, the user must approve
each task individually. A batch approval card showing all proposed tasks at once
with individual checkboxes would be much more usable.

---

## What I Learned About Agent Reliability

1. **Safety must be in code, not prompts.** Every approval-critical behaviour was
   eventually enforced in Python. Prompts influence communication style; code
   enforces constraints.

2. **The agent loop is a function, not a process.** Thinking of the loop as a
   pure function that returns a result (including a mid-run "paused" result) made
   the approval flow simple to implement and test.

3. **Duplicate call detection is essential.** Without it, planning requests with
   vague references ("show me more tasks") would cause the model to loop on
   `list_tasks` until the step limit was reached.

4. **Tool descriptions are part of the system prompt.** Treating them as
   documentation-only was a mistake. Detailed descriptions with explicit approval
   hints acted as secondary enforcement signals and improved accuracy by ~9%.

5. **Temperature matters more than I expected.** At temperature 1.0 the agent
   hallucinated task IDs. This is a safety risk in any agent that references
   persistent records by ID. Production agents should use temperature ≤ 0.3.

---

## Goals for Week 4

1. **Persistent cross-session memory** with conversation history stored in SQLite.
2. **Streaming output** so users see the agent's response token-by-token.
3. **Semantic note search** using sentence embeddings (ChromaDB or Pinecone).
4. **Calendar integration** to pull due dates from Google Calendar.
5. **LangGraph refactor** to express the approval loop as a state machine node,
   making it easier to add new approval-requiring tools.
