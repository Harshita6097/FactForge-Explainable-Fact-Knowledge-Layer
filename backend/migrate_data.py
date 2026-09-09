import sqlite3
import uuid
from datetime import datetime, timezone

conn = sqlite3.connect("factforge.db")
conn.row_factory = sqlite3.Row

user = conn.execute("SELECT id, email FROM users LIMIT 1").fetchone()
if not user:
    print("No users found — register first then re-run")
    conn.close()
    exit(1)

uid = user["id"]
print(f"User: {user['email']} ({uid[:8]})")

orphan_count = conn.execute("SELECT COUNT(*) FROM documents WHERE project_id IS NULL").fetchone()[0]
print(f"Orphaned documents: {orphan_count}")

if orphan_count == 0:
    print("Nothing to migrate")
    conn.close()
    exit(0)

pid = str(uuid.uuid4())
now = datetime.now(timezone.utc).isoformat()

conn.execute(
    "INSERT INTO projects (id, name, description, created_at, updated_at, user_id) VALUES (?,?,?,?,?,?)",
    (pid, "Imported Documents", "Documents uploaded before projects were introduced", now, now, uid),
)
conn.execute("UPDATE documents SET project_id=? WHERE project_id IS NULL", (pid,))
conn.commit()

assigned = conn.execute("SELECT COUNT(*) FROM documents WHERE project_id=?", (pid,)).fetchone()[0]
remaining = conn.execute("SELECT COUNT(*) FROM documents WHERE project_id IS NULL").fetchone()[0]
print(f"Assigned {assigned} documents to project '{pid[:8]}'")
print(f"Remaining orphans: {remaining}")
conn.close()
print("Done")
