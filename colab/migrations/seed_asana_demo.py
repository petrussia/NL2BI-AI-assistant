"""Densify asana DuckDB: 50 tasks, linking to existing 16 projects + 20 users.

Adds project_task_data entries so multi-hop joins (tasks → projects → teams)
return non-empty results.
"""
import duckdb, random
from datetime import datetime, timedelta

random.seed(42)
PATH = "/content/drive/MyDrive/nl2bi_demo/spider2/asana.duckdb"

# Open read-write
conn = duckdb.connect(PATH, read_only=False)
try:
    # Inspect existing IDs
    proj_ids = [r[0] for r in conn.execute("SELECT id FROM project_data").fetchall()]
    user_ids = [r[0] for r in conn.execute("SELECT id FROM user_data").fetchall()]
    existing_task = conn.execute("SELECT COUNT(*) FROM task_data").fetchone()[0]
    print(f"projects: {len(proj_ids)}, users: {len(user_ids)}, existing tasks: {existing_task}")

    # Generate 50 synthetic tasks. Keep id-string format consistent ("123456")
    task_names = [
        "Design new landing page", "Fix login bug", "Write API docs", "Set up CI/CD pipeline",
        "Refactor user service", "Implement payment flow", "Add unit tests", "Migrate database",
        "Update dependencies", "Review pull request", "Schedule team meeting", "Plan Q4 roadmap",
        "Onboard new hire", "Audit security policy", "Deploy hotfix", "Investigate latency",
        "Write release notes", "Configure monitoring", "Optimize queries", "Setup analytics",
        "Mock API responses", "Implement OAuth flow", "Add error logging", "Write integration tests",
        "Update README", "Plan sprint demo", "Configure load balancer", "Migrate to TypeScript",
        "Improve search ranking", "Add multi-language support", "Optimize bundle size",
        "Setup feature flags", "Review architecture", "Update privacy policy",
        "Implement SSO", "Setup tracing", "Add cache layer", "Investigate memory leak",
        "Write postmortem", "Update production config", "Add health endpoint",
        "Set up redis cluster", "Migrate ORM v3", "Performance tuning",
        "Write developer guide", "Setup E2E tests", "Add rate limiting",
        "Plan capacity", "Onboarding doc", "Schedule retrospective",
    ]

    new_tasks = []
    new_pt = []  # project_task_data
    base_id = 1500000000000000  # large unique id space
    today = datetime(2024, 6, 1)
    for i, name in enumerate(task_names):
        tid = f'"{base_id + i}"'
        completed = random.random() < 0.45  # ~45% completed
        days_old = random.randint(1, 365)
        created = today - timedelta(days=days_old)
        completed_at = (created + timedelta(days=random.randint(1, 30))) if completed else None
        due = created + timedelta(days=random.randint(7, 30))
        assignee = random.choice(user_ids)
        # Each task is in 1-2 projects (project_task_data is m2m)
        n_proj = random.choice([1, 1, 1, 2])
        for proj in random.sample(proj_ids, n_proj):
            new_pt.append((proj, tid, today))
        new_tasks.append((
            tid,         # id
            assignee,    # assignee_id
            completed,   # completed
            completed_at, # completed_at
            None,        # completed_by_id (always null in original data)
            created,     # created_at
            due,         # due_on
            None,        # due_at
            today,       # modified_at
            name,        # name
            None,        # parent_id
            None,        # start_on
            f"Notes for: {name}",  # notes
            '"2104505001950"'  # workspace_id (matches existing)
        ))

    # Insert tasks
    conn.executemany("""
      INSERT INTO task_data
      (id, assignee_id, completed, completed_at, completed_by_id, created_at, due_on, due_at, modified_at, name, parent_id, start_on, notes, workspace_id)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, new_tasks)

    # Insert project_task_data
    conn.executemany("""
      INSERT INTO project_task_data(project_id, task_id, _fivetran_synced)
      VALUES (?,?,?)
    """, new_pt)

    conn.commit()
    print(f"inserted: {len(new_tasks)} tasks, {len(new_pt)} project_task links")

    # Verify
    print("\\nverify counts:")
    for tbl in ("task_data", "project_task_data"):
        n = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f"  {tbl}: {n}")
    print("\\ntasks per user (top 5):")
    for r in conn.execute("""
      SELECT u.id, u.name, COUNT(t.id) AS n
      FROM user_data u LEFT JOIN task_data t ON u.id = t.assignee_id
      GROUP BY u.id, u.name ORDER BY n DESC LIMIT 5
    """).fetchall():
        print("   ", r)
    print("\\ntasks per project (top 5):")
    for r in conn.execute("""
      SELECT p.id, COUNT(DISTINCT pt.task_id) AS n
      FROM project_data p LEFT JOIN project_task_data pt ON p.id = pt.project_id
      GROUP BY p.id ORDER BY n DESC LIMIT 5
    """).fetchall():
        print("   ", r)
    print("\\ncompleted by month:")
    for r in conn.execute("""
      SELECT date_trunc('month', created_at) AS m, COUNT(*) AS n
      FROM task_data WHERE created_at IS NOT NULL
      GROUP BY m ORDER BY m LIMIT 10
    """).fetchall():
        print("   ", r)
finally:
    conn.close()
print("\\nasana densified.")
