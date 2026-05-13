from __future__ import annotations
import os
from datetime import datetime
from fastapi import APIRouter, Query
from sqlalchemy import create_engine, func, text
from sqlalchemy.orm import Session

from src.tracker.db import Application, Base

router = APIRouter(prefix="/api")


def _engine():
    db_path = os.environ.get("DB_PATH", "data/applications.db")
    return create_engine(f"sqlite:///{db_path}?mode=ro", connect_args={"uri": True})


@router.get("/stats")
def stats():
    with Session(_engine()) as s:
        total = s.query(Application).count()
        applied = s.query(Application).filter_by(status="applied").count()
        skipped = s.query(Application).filter_by(status="skipped").count()
        failed = s.query(Application).filter_by(status="failed").count()
        avg_score = s.query(func.avg(Application.match_score)).filter(
            Application.status == "applied"
        ).scalar() or 0
    return {
        "total": total,
        "applied": applied,
        "skipped": skipped,
        "failed": failed,
        "avg_score": round(float(avg_score), 1),
    }


@router.get("/applications")
def applications(
    status: str | None = Query(None),
    platform: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    with Session(_engine()) as s:
        q = s.query(Application)
        if status:
            q = q.filter_by(status=status)
        if platform:
            q = q.filter_by(platform=platform)
        total = q.count()
        items = q.order_by(Application.applied_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "items": [
                {
                    "id": a.id,
                    "title": a.title,
                    "company": a.company,
                    "location": a.location,
                    "platform": a.platform,
                    "score": a.match_score,
                    "status": a.status,
                    "applied_at": a.applied_at.isoformat() if a.applied_at else None,
                    "url": a.url,
                    "notes": a.notes,
                }
                for a in items
            ],
        }


@router.get("/timeline")
def timeline():
    with Session(_engine()) as s:
        rows = (
            s.query(
                func.date(Application.applied_at).label("day"),
                func.count().label("count"),
            )
            .filter(Application.status == "applied")
            .filter(Application.applied_at.isnot(None))
            .group_by("day")
            .order_by("day")
            .all()
        )
    return [{"day": r.day, "count": r.count} for r in rows]


@router.get("/top-companies")
def top_companies(limit: int = Query(10, ge=1, le=50)):
    with Session(_engine()) as s:
        rows = (
            s.query(Application.company, func.count().label("count"))
            .filter(Application.status == "applied")
            .group_by(Application.company)
            .order_by(func.count().desc())
            .limit(limit)
            .all()
        )
    return [{"company": r.company, "count": r.count} for r in rows]


@router.get("/score-distribution")
def score_distribution():
    buckets = {"0-49": 0, "50-69": 0, "70-89": 0, "90-100": 0}
    with Session(_engine()) as s:
        rows = s.query(Application.match_score).filter(Application.status == "applied").all()
    for (score,) in rows:
        if score is None:
            continue
        if score < 50:
            buckets["0-49"] += 1
        elif score < 70:
            buckets["50-69"] += 1
        elif score < 90:
            buckets["70-89"] += 1
        else:
            buckets["90-100"] += 1
    return buckets


@router.get("/platforms")
def platforms():
    with Session(_engine()) as s:
        rows = (
            s.query(Application.platform, func.count().label("count"))
            .filter(Application.status == "applied")
            .group_by(Application.platform)
            .all()
        )
    return [{"platform": r.platform, "count": r.count} for r in rows]
