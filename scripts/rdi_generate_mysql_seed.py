"""Generate repeatable, fictional MySQL seed matching Context Retriever Offer."""

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
    "eligible_reward_base",
    "cancellation",
    "departure_date",
    "data_label",
)


def literal(value):
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


sql = """-- Fictional offers. MySQL is the intended price/inventory source of truth.
USE value_travel;
CREATE TABLE IF NOT EXISTS offers (
  package_id VARCHAR(16) PRIMARY KEY,
  name VARCHAR(160) NOT NULL,
  destination VARCHAR(80) NOT NULL,
  total_price DECIMAL(10,2) NOT NULL,
  available_rooms INT UNSIGNED NOT NULL,
  eligible_reward_base DECIMAL(10,2) NOT NULL,
  cancellation VARCHAR(512) NOT NULL,
  departure_date VARCHAR(10) NOT NULL,
  data_label VARCHAR(80) NOT NULL,
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
    ON UPDATE CURRENT_TIMESTAMP(6)
);
REVOKE ALL PRIVILEGES ON `value\\_travel`.* FROM 'value_travel_cdc'@'%';
GRANT SELECT, RELOAD, SHOW DATABASES, REPLICATION SLAVE, REPLICATION CLIENT
  ON *.* TO 'value_travel_cdc'@'%';
FLUSH PRIVILEGES;
"""
for p in PACKAGES:
    sql += "INSERT IGNORE INTO offers (" + ", ".join(FIELDS) + ") VALUES ("
    sql += ", ".join(literal(p[f]) for f in FIELDS) + ");\n"
Path("deployment/rdi/mysql/init.sql").write_text(sql)
print(f"Generated {len(PACKAGES)} synthetic offer rows")
