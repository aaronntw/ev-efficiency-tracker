"""One-time SQLite -> PostgreSQL migration helper.
Usage: python -m backend.app.migrate_sqlite_to_postgres /data/ev_tracker.db
Back up both databases first. The target charges table must be empty.
"""
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from backend.app.main import Charge, ChargingProvider, Settings, engine


def parse_datetime(value):
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)


def migrate(source_path: str):
    path=Path(source_path)
    if not path.exists(): 
        raise SystemExit(f"SQLite database not found: {path}")
    
    with sqlite3.connect(path) as source:
        source.row_factory = sqlite3.Row

        with Session(engine) as target:
            if target.scalar(select(func.count()).select_from(Charge)):
                raise SystemExit("Target charges table is not empty; migration aborted.")
            settings_row=source.execute("SELECT * FROM settings WHERE id = 1").fetchone()
            if settings_row:
                keys=settings_row.keys(); current=target.get(Settings,1) or Settings(id=1)
                current.vehicle_name=settings_row["vehicle_name"]; current.usable_battery_kwh=settings_row["usable_battery_kwh"]
                current.maximum_range_km=settings_row["maximum_range_km"] if "maximum_range_km" in keys else 570.0; current.currency=settings_row["currency"]
                target.merge(current)
            charge_columns={r[1] for r in source.execute("PRAGMA table_info(charges)").fetchall()}
            provider_names=set()

            for row in source.execute("SELECT * FROM charges ORDER BY id"):
                if row["provider"]:
                    provider_names.add(row["provider"])

                target.add(
                    Charge(
                        id=row["id"],
                        charged_at=parse_datetime(row["charged_at"]),
                        odometer_km=row["odometer_km"],
                        soc_before=row["soc_before"],
                        soc_after=row["soc_after"],
                        range_before_km=(
                            row["range_before_km"]
                            if "range_before_km" in charge_columns
                            else None
                        ),
                        range_after_km=(
                            row["range_after_km"]
                            if "range_after_km" in charge_columns
                            else None
                        ),
                        kwh_charged=row["kwh_charged"],
                        amount_paid=row["amount_paid"],
                        connector_type=(
                            row["connector_type"]
                            if "connector_type" in charge_columns
                            else None
                        ),
                        provider=row["provider"],
                        location=row["location"],
                        notes=row["notes"],
                    )
                )

            # Migrate provider configuration if the source DB has the v1.4 table.
            source_tables = {
                row[0]
                for row in source.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }

            if "charging_providers" in source_tables:
                for row in source.execute(
                    "SELECT name, active FROM charging_providers ORDER BY name"
                ):
                    provider = target.scalar(
                        select(ChargingProvider)
                        .where(ChargingProvider.name == row["name"])
                    )

                    if provider:
                        provider.active = bool(row["active"])
                    else:
                        target.add(
                            ChargingProvider(
                                name=row["name"],
                                active=bool(row["active"]),
                            )
                        )
            else:
                # Compatibility with databases from before provider settings existed.
                existing = {
                    p.name
                    for p in target.scalars(select(ChargingProvider)).all()
                }

                for name in sorted(provider_names - existing):
                    target.add(ChargingProvider(name=name))
            target.commit()

            if engine.dialect.name == "postgresql":
                target.execute(text("""
                    SELECT setval(
                        pg_get_serial_sequence('charges', 'id'),
                        COALESCE((SELECT MAX(id) FROM charges), 1),
                        true
                    )
                """))
                target.commit()
            print(
                        f"Migrated "
                        f"{target.scalar(select(func.count()).select_from(Charge))} "
                        f"charging records to PostgreSQL."
            )

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python -m backend.app.migrate_sqlite_to_postgres "
            "/path/to/ev_tracker.db"
        )
    migrate(sys.argv[1])