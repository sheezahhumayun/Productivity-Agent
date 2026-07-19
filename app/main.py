import sys
import os

# Make sure 'app' package is importable from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from datetime import datetime

from app.config import API_KEY, MAX_AGENT_STEPS
from app.database.models import init_db
from app.database import repository as repo
from app.agent.agent import run_agent, resume_after_approval
from app.agent.state import AgentRunResult
from app.logging.run_logger import setup_logging

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Productivity Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.approval-card {
    background: linear-gradient(135deg, #fff3cd 0%, #ffeeba 100%);
    border: 2px solid #ffc107;
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    margin: 0.8rem 0;
}
.approval-card.dark {
    background: linear-gradient(135deg, #3d2e00 0%, #4a3800 100%);
    border-color: #b8860b;
    color: #ffd700;
}
.tool-badge {
    display: inline-block;
    background: #6c757d;
    color: white;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 0.75rem;
    margin: 2px;
    font-family: monospace;
}
.step-counter {
    font-size: 0.75rem;
    color: #6c757d;
    text-align: right;
}
.task-priority-critical { color: #dc3545; font-weight: bold; }
.task-priority-high { color: #fd7e14; font-weight: bold; }
.task-priority-medium { color: #ffc107; }
.task-priority-low { color: #28a745; }
.status-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
}
.user-bubble {
    background: #e8f4fd;
    border-radius: 18px 18px 4px 18px;
    padding: 0.75rem 1rem;
    margin: 0.5rem 0;
    max-width: 85%;
    margin-left: auto;
    border: 1px solid #bee3f8;
}
.agent-bubble {
    background: #f8f9fa;
    border-radius: 18px 18px 18px 4px;
    padding: 0.75rem 1rem;
    margin: 0.5rem 0;
    max-width: 90%;
    border: 1px solid #e2e8f0;
}
</style>
""", unsafe_allow_html=True)


# ── Session state init ─────────────────────────────────────────────────────────
def _init_state():
    defaults = {
        "conversation": [],        # [{role, content, timestamp, tools_called}]
        "api_messages": [],        # raw anthropic messages for context
        "pending_approval": None,  # PendingApproval object
        "agent_status": "idle",    # idle | thinking | awaiting_approval
        "active_tab": "chat",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ── Sidebar ────────────────────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.title("🤖 Productivity Agent")
        st.caption("AI Summer Fellowship 2026 | Week 3")
        st.divider()

        # API key status
        if API_KEY:
            st.success("✅ API Key configured")
        else:
            st.error("❌ No API Key — add API_KEY to .env")

        st.divider()

        # Quick stats
        tasks = repo.list_tasks(limit=200)
        pending = [t for t in tasks if t["status"] == "pending"]
        in_prog = [t for t in tasks if t["status"] == "in_progress"]
        done = [t for t in tasks if t["status"] == "completed"]
        overdue = [t for t in tasks if t["status"] not in ("completed", "cancelled")
                   and t.get("due_date") and t["due_date"] < str(datetime.utcnow().date())]

        col1, col2 = st.columns(2)
        col1.metric("Pending", len(pending))
        col2.metric("In Progress", len(in_prog))
        col1.metric("Completed", len(done))
        col2.metric("Overdue", len(overdue), delta=f"-{len(overdue)}" if overdue else None,
                    delta_color="inverse")

        notes = repo.list_notes(limit=200)
        st.metric("Notes", len(notes))

        st.divider()
        st.caption("**Quick Commands**")
        quick = [
            "Show my pending tasks",
            "Generate today's work plan",
            "Show weekly report",
            "Create a high priority task",
        ]
        for q in quick:
            if st.button(q, use_container_width=True, key=f"quick_{q}"):
                st.session_state["_quick_input"] = q
                st.rerun()

        st.divider()
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.conversation = []
            st.session_state.api_messages = []
            st.session_state.pending_approval = None
            st.session_state.agent_status = "idle"
            st.rerun()

        st.caption(f"Max steps per request: {MAX_AGENT_STEPS}")


# ── Approval card ──────────────────────────────────────────────────────────────
def render_approval_card():
    pa = st.session_state.pending_approval
    if not pa:
        return

    st.markdown("""
    <div class="approval-card">
    <h4>⚠️ Approval Required</h4>
    </div>
    """, unsafe_allow_html=True)

    with st.container(border=True):
        col_icon, col_info = st.columns([0.08, 0.92])
        col_icon.markdown("### ⚠️")
        col_info.markdown(f"**Tool:** `{pa.tool_name}`")
        col_info.markdown(f"**Action:** {pa.human_description}")

        with st.expander("View full parameters"):
            st.json(pa.tool_input)

        col_a, col_r, _ = st.columns([1, 1, 3])
        if col_a.button("✅ Approve", type="primary", key="btn_approve"):
            _handle_approval(True)
        if col_r.button("❌ Reject", type="secondary", key="btn_reject"):
            _handle_approval(False)


def _handle_approval(approved: bool):
    pa = st.session_state.pending_approval
    st.session_state.pending_approval = None
    st.session_state.agent_status = "thinking"

    status_msg = "✅ Approved" if approved else "❌ Rejected"
    st.session_state.conversation.append({
        "role": "system",
        "content": f"{status_msg}: `{pa.tool_name}` — {pa.human_description}",
        "timestamp": datetime.now().strftime("%H:%M"),
    })

    with st.status("⚙️ Resuming agent...", expanded=True) as s:
        result = resume_after_approval(pa, approved, status_fn=s.write)
    _process_result(result)


# ── Process agent result ───────────────────────────────────────────────────────
def _process_result(result: AgentRunResult):
    if result.needs_approval:
        st.session_state.pending_approval = result.pending_approval
        st.session_state.agent_status = "awaiting_approval"
        # Show tool calls so far in the chat
        if result.tools_called:
            _add_tool_status_message(result.tools_called)

    elif result.error:
        st.session_state.agent_status = "idle"
        st.session_state.conversation.append({
            "role": "assistant",
            "content": f"❌ **Error:** {result.error}",
            "timestamp": datetime.now().strftime("%H:%M"),
            "tools_called": result.tools_called,
        })

    else:
        st.session_state.agent_status = "idle"
        # Update api_messages to include the full exchange
        # (simplified: we'll re-build from conversation on next turn)
        st.session_state.conversation.append({
            "role": "assistant",
            "content": result.response_text,
            "timestamp": datetime.now().strftime("%H:%M"),
            "tools_called": result.tools_called,
            "step_count": result.step_count,
        })

    st.rerun()


def _add_tool_status_message(tool_calls):
    tools_str = ", ".join(f"`{r.tool_name}`" for r in tool_calls if r.approved)
    if tools_str:
        st.session_state.conversation.append({
            "role": "system",
            "content": f"🔧 Tools executed: {tools_str}",
            "timestamp": datetime.now().strftime("%H:%M"),
        })


# ── Chat messages rendering ────────────────────────────────────────────────────
def render_messages():
    for msg in st.session_state.conversation:
        role = msg["role"]
        content = msg["content"]
        ts = msg.get("timestamp", "")

        if role == "user":
            with st.chat_message("user"):
                st.markdown(content)
                st.caption(ts)

        elif role == "assistant":
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(content)
                tools = msg.get("tools_called", [])
                if tools:
                    tool_names = list(dict.fromkeys(r.tool_name for r in tools))
                    badges = " ".join(f'<span class="tool-badge">🔧 {n}</span>' for n in tool_names)
                    steps = msg.get("step_count", 0)
                    st.markdown(
                        f'{badges} <span class="step-counter">{steps} step(s)</span>',
                        unsafe_allow_html=True,
                    )
                st.caption(ts)

        elif role == "system":
            st.info(content)


# ── Task panel ─────────────────────────────────────────────────────────────────
def render_tasks_tab():
    st.subheader("📋 Task Manager")

    filter_col1, filter_col2, filter_col3 = st.columns(3)
    with filter_col1:
        status_filter = st.selectbox("Status", ["All", "pending", "in_progress", "blocked", "completed", "cancelled"])
    with filter_col2:
        priority_filter = st.selectbox("Priority", ["All", "critical", "high", "medium", "low"])
    with filter_col3:
        search_tag = st.text_input("Tag filter", placeholder="e.g. dev")

    status_q = None if status_filter == "All" else status_filter
    priority_q = None if priority_filter == "All" else priority_filter
    tag_q = search_tag.strip() or None

    tasks = repo.list_tasks(status=status_q, priority=priority_q, tag=tag_q)

    if not tasks:
        st.info("No tasks found. Ask the agent to create some!")
        return

    priority_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
    status_emoji = {"pending": "⏳", "in_progress": "🔄", "blocked": "🚫", "completed": "✅", "cancelled": "❌"}

    for task in tasks:
        p_icon = priority_emoji.get(task["priority"], "⚪")
        s_icon = status_emoji.get(task["status"], "❓")
        with st.expander(f"{p_icon} #{task['id']} — {task['title']} {s_icon}"):
            col1, col2 = st.columns(2)
            col1.write(f"**Priority:** {task['priority'].upper()}")
            col1.write(f"**Status:** {task['status']}")
            col2.write(f"**Due:** {task.get('due_date') or 'Not set'}")
            col2.write(f"**Tags:** {', '.join(task.get('tags') or []) or 'None'}")
            if task.get("description"):
                st.write(f"**Description:** {task['description']}")
            if task.get("notes"):
                st.caption(f"Notes: {task['notes']}")
            st.caption(f"Created: {task['created_at']} | Updated: {task['updated_at']}")


# ── Notes panel ────────────────────────────────────────────────────────────────
def render_notes_tab():
    st.subheader("📝 Notes Library")
    search_q = st.text_input("Search notes", placeholder="Enter keywords...")

    if search_q:
        notes = repo.search_notes(search_q)
    else:
        notes = repo.list_notes()

    if not notes:
        st.info("No notes found. Ask the agent to save some!")
        return

    for note in notes:
        with st.expander(f"📄 #{note['id']} — {note['title']}"):
            col1, col2 = st.columns(2)
            col1.write(f"**Category:** {note.get('category') or 'Uncategorized'}")
            col2.write(f"**Tags:** {', '.join(note.get('tags') or []) or 'None'}")
            st.write(note["content"])
            st.caption(f"Created: {note['created_at']}")


# ── Logs panel ────────────────────────────────────────────────────────────────
def render_logs_tab():
    st.subheader("📊 Execution Logs")
    logs = repo.get_recent_logs(20)

    if not logs:
        st.info("No execution logs yet. Start chatting with the agent!")
        return

    status_color = {"completed": "🟢", "error": "🔴", "awaiting_approval": "🟡", "running": "🔵"}

    for log in logs:
        icon = status_color.get(log["status"], "⚪")
        with st.expander(
            f"{icon} [{log['run_id']}] {log['user_request'][:60]}... — {log['start_time']}"
        ):
            col1, col2, col3 = st.columns(3)
            col1.metric("Status", log["status"])
            col2.metric("Steps", log["step_count"])
            col3.metric("Duration", f"{log.get('duration_ms', 0)}ms")

            st.write(f"**Model:** `{log['model']}`")
            st.write(f"**Request:** {log['user_request']}")

            if log["tools_called"]:
                st.write("**Tools called:**")
                for tc in log["tools_called"]:
                    approved_str = "✅" if tc.get("approved") else ("❌" if tc.get("approved") is False else "⏳")
                    success_str = "✅" if tc.get("success") else "❌"
                    with st.expander(f"  {approved_str} `{tc['name']}` → {success_str}"):
                        if tc.get("input"):
                            st.write("**Input:**")
                            st.json(tc["input"])
                        if tc.get("result"):
                            st.write("**Result:**")
                            st.json(tc["result"])
                        if tc.get("error"):
                            st.error(f"Error: {tc['error']}")

            if log["errors"]:
                st.error(f"Errors: {log['errors']}")

            if log["final_outcome"]:
                with st.expander("Final outcome"):
                    st.write(log["final_outcome"])


# ── Main layout ────────────────────────────────────────────────────────────────
def main():
    setup_logging()
    init_db()
    _init_state()
    render_sidebar()

    # Main content area
    tab_chat, tab_tasks, tab_notes, tab_logs = st.tabs([
        "💬 Chat", "📋 Tasks", "📝 Notes", "📊 Logs"
    ])

    with tab_chat:
        # Status bar
        status_map = {
            "idle": ("💬 Ready", "normal"),
            "thinking": ("🧠 Agent thinking...", "warning"),
            "awaiting_approval": ("⚠️ Waiting for approval", "warning"),
        }
        status_text, status_type = status_map.get(st.session_state.agent_status, ("❓", "normal"))
        if st.session_state.agent_status != "idle":
            st.warning(status_text)

        # Message history
        render_messages()

        # Approval card — shown inline after messages (at bottom of conversation)
        if st.session_state.pending_approval:
            render_approval_card()

        # Show spinner if thinking
        if st.session_state.agent_status == "thinking":
            with st.spinner("Agent is working..."):
                pass

        st.divider()

        # Input area
        if st.session_state.agent_status not in ("awaiting_approval",):
            # Check for quick input from sidebar
            default_val = st.session_state.pop("_quick_input", "")

            user_input = st.chat_input(
                "Ask your productivity agent...",
                disabled=(st.session_state.agent_status == "thinking"),
            )

            if not user_input and default_val:
                user_input = default_val

            if user_input:
                if not API_KEY:
                    st.error("Please set API_KEY in your .env file to use the agent.")
                else:
                    # Add user message to display
                    st.session_state.conversation.append({
                        "role": "user",
                        "content": user_input,
                        "timestamp": datetime.now().strftime("%H:%M"),
                    })
                    st.session_state.agent_status = "thinking"
                    st.rerun()

        # If status is "thinking" and last message is from user, run the agent
        if (
            st.session_state.agent_status == "thinking"
            and st.session_state.conversation
            and st.session_state.conversation[-1]["role"] == "user"
        ):
            user_msg = st.session_state.conversation[-1]["content"]

            # Build api_messages from conversation (only user/assistant roles)
            api_messages = []
            for m in st.session_state.conversation[:-1]:  # exclude last user msg (passed separately)
                if m["role"] in ("user", "assistant"):
                    api_messages.append({"role": m["role"], "content": m["content"]})

            with st.status("🧠 Agent working...", expanded=True) as s:
                result = run_agent(user_msg, api_messages, status_fn=s.write)

            _process_result(result)

    with tab_tasks:
        render_tasks_tab()

    with tab_notes:
        render_notes_tab()

    with tab_logs:
        render_logs_tab()


if __name__ == "__main__":
    main()
