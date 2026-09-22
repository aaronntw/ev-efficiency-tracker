import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional
from urllib.parse import quote_plus

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, create_engine, inspect, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

APP_VERSION = os.getenv("APP_VERSION", "1.4.3")
APP_BUILD_SHA = os.getenv("APP_BUILD_SHA", "unknown")
DB_TYPE = os.getenv("DB_TYPE", "sqlite").strip().lower()
APP_TIMEZONE = os.getenv("TZ", "UTC").strip()

try:
    from zoneinfo import ZoneInfo
    ZoneInfo(APP_TIMEZONE)
except Exception as exc:
    raise RuntimeError(f"TZ must be a valid IANA timezone, got: {APP_TIMEZONE}") from exc

DEFAULT_PROVIDERS = []


def build_database_url():
    if DB_TYPE == "sqlite":
        path = Path(os.getenv("SQLITE_PATH", "/data/ev_tracker.db"))
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path}", {
            "connect_args": {"check_same_thread": False}
        }
    if DB_TYPE == "postgres":
        required = ["POSTGRES_HOST", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"]
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            raise RuntimeError(f"Missing PostgreSQL environment variables: {', '.join(missing)}")
        host = os.environ["POSTGRES_HOST"]
        port = os.getenv("POSTGRES_PORT", "5432")
        db = os.environ["POSTGRES_DB"]
        user = quote_plus(os.environ["POSTGRES_USER"])
        password = quote_plus(os.environ["POSTGRES_PASSWORD"])
        return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}", {"pool_pre_ping": True}
    raise RuntimeError("DB_TYPE must be either 'sqlite' or 'postgres'")


DATABASE_URL, engine_options = build_database_url()
engine = create_engine(DATABASE_URL, **engine_options)


class Base(DeclarativeBase):
    pass


class Settings(Base):
    __tablename__ = "settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    vehicle_name: Mapped[str] = mapped_column(String(100), default="My EV")
    usable_battery_kwh: Mapped[float] = mapped_column(Float, default=60.0)
    maximum_range_km: Mapped[float] = mapped_column(Float, default=400.0)
    currency: Mapped[str] = mapped_column(String(10), default="USD")


class ChargingProvider(Base):
    __tablename__ = "charging_providers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Charge(Base):
    __tablename__ = "charges"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    charged_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    odometer_km: Mapped[float] = mapped_column(Float)
    soc_before: Mapped[float] = mapped_column(Float)
    soc_after: Mapped[float] = mapped_column(Float)
    range_before_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    range_after_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    kwh_charged: Mapped[float] = mapped_column(Float)
    amount_paid: Mapped[float] = mapped_column(Float)
    connector_type: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


Base.metadata.create_all(engine)


def migrate_schema():
    inspector = inspect(engine)
    if "settings" in inspector.get_table_names():
        settings_columns = {c["name"] for c in inspector.get_columns("settings")}
        if "maximum_range_km" not in settings_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE settings ADD COLUMN maximum_range_km FLOAT DEFAULT 570.0"))
    if "charges" in inspector.get_table_names():
        charge_columns = {c["name"] for c in inspector.get_columns("charges")}
        if "connector_type" not in charge_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE charges ADD COLUMN connector_type VARCHAR(10)"))


def seed_providers():
    with Session(engine) as session:
        if session.scalar(select(ChargingProvider.id).limit(1)) is None:
            session.add_all([ChargingProvider(name=name) for name in DEFAULT_PROVIDERS])
            session.commit()


migrate_schema()
seed_providers()


class ChargeCreate(BaseModel):
    charged_at: datetime
    odometer_km: int = Field(gt=0)
    soc_before: int = Field(ge=0, le=100)
    soc_after: int = Field(ge=0, le=100)
    kwh_charged: float = Field(gt=0)
    amount_paid: float = Field(ge=0)
    connector_type: Optional[Literal["AC", "DC"]] = None
    provider: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("charged_at")
    @classmethod
    def require_aware_timestamp(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("charged_at must include a UTC offset")
        return value.astimezone(timezone.utc).replace(tzinfo=None)


class SettingsIn(BaseModel):
    vehicle_name: str = "My EV"
    usable_battery_kwh: float = Field(gt=10, le=300)
    maximum_range_km: float = Field(gt=0)
    currency: str = "USD"


class ProviderIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


app = FastAPI(title="EV Efficiency Tracker", version=APP_VERSION)


def get_settings(session):
    s = session.get(Settings, 1)
    if not s:
        s = Settings()
        session.add(s)
        session.commit()
        session.refresh(s)
    return s


def previous_charge(session, charge):
    return session.scalar(select(Charge).where(Charge.id != charge.id, Charge.odometer_km < charge.odometer_km).order_by(Charge.odometer_km.desc()))


def serialize(c, prev, s):
    charged_at = c.charged_at
    charged_at_utc = (charged_at.replace(tzinfo=timezone.utc) if charged_at.tzinfo is None else charged_at.astimezone(timezone.utc)).isoformat().replace("+00:00", "Z")
    r = {
        "id": c.id, "charged_at": charged_at_utc, "odometer_km": round(c.odometer_km),
        "soc_before": round(c.soc_before), "soc_after": round(c.soc_after),
        "kwh_charged": c.kwh_charged, "amount_paid": c.amount_paid,
        "connector_type": c.connector_type, "provider": c.provider, "location": c.location, "notes": c.notes,
        "distance_km": None, "soc_used_pct": None, "estimated_energy_used_kwh": None,
        "efficiency_km_per_kwh": None, "theoretical_distance_km": None,
        "efficiency_percent": None, "charging_cost_per_kwh": None, "charging_cost_per_km": None,
    }
    r["charging_cost_per_kwh"] = c.amount_paid / c.kwh_charged if c.kwh_charged else None
    if prev:
        distance = c.odometer_km - prev.odometer_km
        soc_used = prev.soc_after - c.soc_before
        r["distance_km"] = distance
        r["soc_used_pct"] = soc_used
        if distance >= 0 and soc_used > 0:
            energy = soc_used / 100 * s.usable_battery_kwh
            theoretical = soc_used / 100 * s.maximum_range_km
            r["estimated_energy_used_kwh"] = energy
            r["theoretical_distance_km"] = theoretical
            r["efficiency_km_per_kwh"] = distance / energy if energy > 0 else None
            r["efficiency_percent"] = distance / theoretical * 100 if theoretical > 0 else None
            r["charging_cost_per_km"] = c.amount_paid / distance if distance > 0 else None
    return r


@app.get("/api/health")
def health():
    return {"status": "ok", "database": DB_TYPE, "timezone": APP_TIMEZONE}


@app.get("/api/version")
def version():
    return {"version": APP_VERSION, "build_sha": APP_BUILD_SHA, "database": DB_TYPE, "timezone": APP_TIMEZONE}


@app.get("/api/settings")
def read_settings():
    with Session(engine) as session:
        s = get_settings(session)
        return {"vehicle_name": s.vehicle_name, "usable_battery_kwh": s.usable_battery_kwh, "maximum_range_km": s.maximum_range_km or 400.0, "currency": s.currency}


@app.put("/api/settings")
def update_settings(data: SettingsIn):
    with Session(engine) as session:
        s = get_settings(session)
        for k, v in data.model_dump().items():
            setattr(s, k, v)
        session.commit()
        return data


@app.get("/api/providers")
def list_providers(include_inactive: bool = False):
    with Session(engine) as session:
        stmt = select(ChargingProvider).order_by(ChargingProvider.name.asc())
        if not include_inactive:
            stmt = stmt.where(ChargingProvider.active.is_(True))
        return [{"id": p.id, "name": p.name, "active": p.active} for p in session.scalars(stmt).all()]


@app.post("/api/providers", status_code=201)
def create_provider(data: ProviderIn):
    name = data.name.strip()
    with Session(engine) as session:
        existing = session.scalar(select(ChargingProvider).where(ChargingProvider.name == name))
        if existing:
            if not existing.active:
                existing.active = True
                session.commit()
                session.refresh(existing)
                return {"id": existing.id, "name": existing.name, "active": existing.active}
            raise HTTPException(409, "Charging provider already exists")
        provider = ChargingProvider(name=name)
        session.add(provider)
        session.commit()
        session.refresh(provider)
        return {"id": provider.id, "name": provider.name, "active": provider.active}


@app.put("/api/providers/{provider_id}")
def update_provider(provider_id: int, data: ProviderIn):
    name = data.name.strip()
    with Session(engine) as session:
        provider = session.get(ChargingProvider, provider_id)
        if not provider:
            raise HTTPException(404, "Charging provider not found")
        duplicate = session.scalar(select(ChargingProvider).where(ChargingProvider.name == name, ChargingProvider.id != provider_id))
        if duplicate:
            raise HTTPException(409, "Charging provider already exists")
        old_name = provider.name
        provider.name = name
        for charge in session.scalars(select(Charge).where(Charge.provider == old_name)).all():
            charge.provider = name
        session.commit()
        return {"id": provider.id, "name": provider.name, "active": provider.active}


@app.delete("/api/providers/{provider_id}")
def delete_provider(provider_id: int):
    with Session(engine) as session:
        provider = session.get(ChargingProvider, provider_id)
        if not provider:
            raise HTTPException(404, "Charging provider not found")
        provider.active = False
        session.commit()
        return {"deleted": True}


@app.get("/api/charges")
def list_charges(limit: int = Query(200, ge=1, le=1000)):
    with Session(engine) as session:
        s = get_settings(session)
        rows = session.scalars(select(Charge).order_by(Charge.odometer_km.asc())).all()[-limit:]
        return [serialize(c, rows[i - 1] if i else None, s) for i, c in enumerate(rows)][::-1]


@app.post("/api/charges", status_code=201)
def create_charge(data: ChargeCreate):
    with Session(engine) as session:
        s = get_settings(session)
        c = Charge(**data.model_dump())
        session.add(c)
        session.commit()
        session.refresh(c)
        return serialize(c, previous_charge(session, c), s)


@app.put("/api/charges/{charge_id}")
def update_charge(charge_id: int, data: ChargeCreate):
    with Session(engine) as session:
        s = get_settings(session)
        c = session.get(Charge, charge_id)
        if not c:
            raise HTTPException(404, "Charging record not found")
        for k, v in data.model_dump().items():
            setattr(c, k, v)
        session.commit()
        session.refresh(c)
        return serialize(c, previous_charge(session, c), s)


@app.delete("/api/charges/{charge_id}")
def delete_charge(charge_id: int):
    with Session(engine) as session:
        c = session.get(Charge, charge_id)
        if not c:
            raise HTTPException(404, "Charging record not found")
        session.delete(c)
        session.commit()
        return {"deleted": True}


@app.get("/api/export.csv")
def export_csv():
    import csv
    import io
    with Session(engine) as session:
        s = get_settings(session)
        rows = session.scalars(select(Charge).order_by(Charge.odometer_km.asc())).all()
        out = io.StringIO()
        w = csv.writer(out)
        cols = ["id", "charged_at", "connector_type", "odometer_km", "soc_before", "soc_after", "kwh_charged", "amount_paid", "charging_cost_per_kwh", "provider", "location", "distance_km", "soc_used_pct", "estimated_energy_used_kwh", "efficiency_km_per_kwh", "theoretical_distance_km", "efficiency_percent", "charging_cost_per_km", "notes"]
        w.writerow(cols)
        for i, c in enumerate(rows):
            r = serialize(c, rows[i - 1] if i else None, s)
            w.writerow([r[k] for k in cols])
        out.seek(0)
        return StreamingResponse(iter([out.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=ev-charging.csv"})

