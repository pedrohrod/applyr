import csv
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text
from sqlalchemy.orm import DeclarativeBase, Session
from loguru import logger


class Base(DeclarativeBase):
    pass


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(256), unique=True, nullable=False)
    title = Column(String(256))
    company = Column(String(256))
    location = Column(String(256))
    platform = Column(String(64))
    url = Column(Text)
    match_score = Column(Integer, default=0)
    status = Column(String(64), default="pending")  # pending | applied | failed | skipped
    retry_count = Column(Integer, default=0)
    applied_at = Column(DateTime, nullable=True)
    cover_letter = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)


MAX_RETRIES = 3


class Tracker:
    def __init__(self, db_url: str = "sqlite:///data/applications.db", csv_path: str | None = None):
        Path(db_url.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.csv_path = csv_path

    def should_skip(self, job_id: str) -> bool:
        """Skip if already applied, or if failed too many times."""
        with Session(self.engine) as s:
            app = s.query(Application).filter_by(job_id=job_id).first()
            if app is None:
                return False
            if app.status == "applied":
                return True
            if app.status == "skipped":
                return True
            if app.status == "failed" and app.retry_count >= MAX_RETRIES:
                return True
            return False

    # kept for backwards compatibility
    def already_applied(self, job_id: str) -> bool:
        return self.should_skip(job_id)

    def record(self, job, score: int, status: str, cover_letter: str = "", notes: str = "") -> None:
        try:
            with Session(self.engine) as s:
                existing = s.query(Application).filter_by(job_id=job.id).first()
                if existing:
                    existing.status = status
                    existing.match_score = score
                    existing.notes = notes
                    if status == "failed":
                        existing.retry_count = (existing.retry_count or 0) + 1
                    if status == "applied":
                        existing.applied_at = datetime.utcnow()
                else:
                    s.add(Application(
                        job_id=job.id,
                        title=job.title,
                        company=job.company,
                        location=job.location,
                        platform=job.platform,
                        url=job.url,
                        match_score=score,
                        status=status,
                        retry_count=1 if status == "failed" else 0,
                        applied_at=datetime.utcnow() if status == "applied" else None,
                        cover_letter=cover_letter,
                        notes=notes,
                    ))
                s.commit()
        except Exception as e:
            logger.error(f"Tracker DB error for {job.id}: {e}")

        if self.csv_path and status == "applied":
            self._append_csv(job, score, cover_letter)

        logger.debug(f"[{status.upper()}] {job.title} @ {job.company} (score={score})")

    def _append_csv(self, job, score: int, cover_letter: str) -> None:
        try:
            path = Path(self.csv_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            write_header = not path.exists()
            with open(path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if write_header:
                    writer.writerow(["date", "company", "title", "platform", "score", "url", "cover_letter"])
                writer.writerow([
                    datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
                    job.company, job.title, job.platform, score, job.url,
                    cover_letter[:100] + "..." if len(cover_letter) > 100 else cover_letter,
                ])
        except Exception as e:
            logger.error(f"Failed to write CSV: {e}")

    def stats(self) -> dict:
        with Session(self.engine) as s:
            total = s.query(Application).count()
            applied = s.query(Application).filter_by(status="applied").count()
            skipped = s.query(Application).filter_by(status="skipped").count()
            failed = s.query(Application).filter_by(status="failed").count()
        return {"total": total, "applied": applied, "skipped": skipped, "failed": failed}
