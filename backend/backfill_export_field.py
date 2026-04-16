"""One-time backfill: copy payment_type into export_field for distribution
nodes that have payment_type set but export_field empty.

Safe to run multiple times — only touches rows where export_field is null.
"""
import sqlite3

conn = sqlite3.connect("absnexus.db")
c = conn.cursor()

c.execute("""
    UPDATE dag_node
    SET export_field = payment_type
    WHERE node_type = 'distribution'
      AND (export_field IS NULL OR export_field = '')
      AND payment_type IS NOT NULL
      AND payment_type != ''
""")
updated = c.rowcount
conn.commit()
conn.close()
print(f"Backfilled export_field on {updated} distribution nodes")
