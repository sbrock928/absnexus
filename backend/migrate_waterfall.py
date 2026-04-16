"""One-time migration: add waterfall columns."""
import sqlite3

conn = sqlite3.connect("absnexus.db")
c = conn.cursor()

cols = [
    ("dag_node", "waterfall_order", "INTEGER"),
    ("deal", "waterfall_starting_var", "VARCHAR(100) DEFAULT 'total_available_funds'"),
    ("deal", "waterfall_ending_var", "VARCHAR(100) DEFAULT 'end_available_funds'"),
    ("deal", "waterfall_tolerance", "NUMERIC(18,4) DEFAULT 0.01"),
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
