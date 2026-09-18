"""Generate repeatable, fictional SQL Server seed matching Context Retriever Offer."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from valuetravel.data import PACKAGES

FIELDS = (
    "package_id",
    "name",
    "destination",
    "total_price",
    "available_rooms",
    "room_capacity",
    "eligible_reward_base",
    "cancellation",
    "departure_date",
    "data_label",
)


def literal(value):
    if isinstance(value, (int, float)):
        return str(value)
    return "N'" + str(value).replace("'", "''") + "'"


sql = """-- Fictional offers. Insert missing rows without replacing edited values.
USE value_travel;
SET NOCOUNT ON;
"""
for p in PACKAGES:
    sql += f"IF NOT EXISTS (SELECT 1 FROM dbo.offers WHERE package_id={literal(p['package_id'])})\nINSERT INTO dbo.offers (" + ", ".join(FIELDS) + ") VALUES ("
    sql += ", ".join(literal(p[f]) for f in FIELDS) + ");\n"
Path(__file__).resolve().parents[1].joinpath("deployment/rdi/sqlserver/seed.sql").write_text(sql)
print(f"Generated {len(PACKAGES)} synthetic offer rows")
