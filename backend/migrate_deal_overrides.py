"""Add per-deal directory override columns."""
import sqlite3

conn = sqlite3.connect("absnexus.db")
c = conn.cursor()

cols = [
    ("deal", "export_directory_override", "VARCHAR(500)"),
    ("deal", "dag_archive_directory_override", "VARCHAR(500)"),
]

for table, col, typedef in cols:
    try:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typedef}")
        print(f"  + {table}.{col}")
    except Exception as e:
        print(f"  = {table}.{col} ({e})")

conn.commit()
conn.close()
print("Done")
