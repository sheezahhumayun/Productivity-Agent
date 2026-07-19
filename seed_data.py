"""
Run this script to populate sample data for demos.
Usage: python seed_data.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.database.models import init_db
from app.database import repository as repo

init_db()

# Sample tasks
tasks = [
    {
        "title": "Set up CI/CD pipeline",
        "description": "Configure GitHub Actions for automated testing and deployment",
        "priority": "high",
        "due_date": "2026-07-25",
        "tags": ["devops", "infrastructure"],
    },
    {
        "title": "Write API documentation",
        "description": "Document all REST endpoints using OpenAPI/Swagger",
        "priority": "medium",
        "due_date": "2026-07-28",
        "tags": ["docs", "backend"],
    },
    {
        "title": "Security audit",
        "description": "Review authentication flows and input validation",
        "priority": "critical",
        "due_date": "2026-07-22",
        "tags": ["security", "backend"],
    },
    {
        "title": "Update landing page copy",
        "description": "Revise hero section and feature descriptions based on user feedback",
        "priority": "low",
        "tags": ["marketing", "frontend"],
    },
    {
        "title": "Database performance optimization",
        "description": "Add indexes and optimize slow queries identified in monitoring",
        "priority": "high",
        "due_date": "2026-07-24",
        "status": "in_progress",
        "tags": ["backend", "database"],
    },
    {
        "title": "User onboarding flow",
        "description": "Design and implement the new user onboarding wizard",
        "priority": "high",
        "due_date": "2026-07-30",
        "tags": ["frontend", "ux"],
    },
    {
        "title": "Fix payment gateway timeout",
        "description": "Investigate and fix Stripe webhook timeout errors in production",
        "priority": "critical",
        "status": "blocked",
        "tags": ["backend", "payments"],
    },
]

# Sample notes
notes = [
    {
        "title": "Sprint Planning Notes — July 14",
        "content": """Attendees: Sarah (PM), Ahmed (Backend), Lisa (Frontend), Raj (DevOps)

DECISIONS:
- Prioritize security audit before v2 launch
- Move payment gateway fix to critical track
- Defer dark mode to next sprint

ACTION ITEMS:
- Ahmed: Fix Stripe webhook timeout by Wednesday
- Lisa: Complete onboarding wizard mockups by Thursday
- Raj: Set up staging environment by end of week
- Sarah: Update roadmap with revised launch date

OPEN QUESTIONS:
- Should we support OAuth in v2 or defer to v3?
- What's the SLA for the payment timeout fix?
""",
        "category": "meeting",
        "tags": ["sprint", "planning", "q3"],
    },
    {
        "title": "Authentication Architecture Notes",
        "content": """JWT vs Session tokens discussion:

JWT Pros: Stateless, scalable, works well for microservices
JWT Cons: Hard to revoke, token size increases with claims

Decision: Use short-lived JWTs (15min) + refresh tokens stored in httpOnly cookies.

Implementation notes:
- Use RS256 (asymmetric) not HS256
- Store refresh tokens in Redis with TTL
- Add token rotation on refresh
- Implement token blacklist for immediate revocation
""",
        "category": "research",
        "tags": ["auth", "security", "architecture"],
    },
    {
        "title": "API Rate Limiting Strategy",
        "content": """Rate limiting plan for public API:

Tiers:
- Free: 100 req/hour
- Pro: 1000 req/hour
- Enterprise: 10000 req/hour

Implementation:
- Use Redis sliding window algorithm
- Return X-RateLimit-* headers
- 429 status with Retry-After header
- Log all rate limit hits for analysis

Library: slowapi (FastAPI middleware)
""",
        "category": "research",
        "tags": ["api", "security", "backend"],
    },
]

print("Seeding tasks...")
for t in tasks:
    status = t.pop("status", "pending")
    task = repo.create_task(**t)
    if status != "pending":
        repo.update_task(task["id"], status=status)
    print(f"  ✓ Task #{task['id']}: {task['title']}")

print("\nSeeding notes...")
for n in notes:
    note = repo.save_note(**n)
    print(f"  ✓ Note #{note['id']}: {note['title']}")

print("\nSeed complete! Run: streamlit run app/main.py")
