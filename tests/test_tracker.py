import pytest
from src.tracker.db import Tracker, MAX_RETRIES
from src.scrapers.linkedin import Job


@pytest.fixture
def tracker(tmp_path):
    db_url = f"sqlite:///{tmp_path}/test.db"
    return Tracker(db_url=db_url)


@pytest.fixture
def job():
    return Job(
        id="job-001",
        title="Software Engineer",
        company="Test Corp",
        location="Remote",
        url="https://example.com/job/1",
        platform="linkedin",
    )


def test_new_job_is_not_skipped(tracker, job):
    assert tracker.should_skip(job.id) is False


def test_applied_job_is_skipped(tracker, job):
    tracker.record(job, 80, "applied")
    assert tracker.should_skip(job.id) is True


def test_skipped_job_is_skipped(tracker, job):
    tracker.record(job, 40, "skipped")
    assert tracker.should_skip(job.id) is True


def test_failed_job_not_skipped_below_max_retries(tracker, job):
    tracker.record(job, 75, "failed")
    assert tracker.should_skip(job.id) is False


def test_failed_job_skipped_after_max_retries(tracker, job):
    for _ in range(MAX_RETRIES):
        tracker.record(job, 75, "failed")
    assert tracker.should_skip(job.id) is True


def test_retry_count_increments(tracker, job):
    tracker.record(job, 75, "failed")
    tracker.record(job, 75, "failed")
    with __import__("sqlalchemy.orm", fromlist=["Session"]).Session(tracker.engine) as s:
        from src.tracker.db import Application
        app = s.query(Application).filter_by(job_id=job.id).first()
        assert app.retry_count == 2


def test_stats_counts_correctly(tracker, job):
    job2 = Job(id="job-002", title="Dev", company="B", location="", url="", platform="gupy")
    job3 = Job(id="job-003", title="Dev", company="C", location="", url="", platform="gupy")

    tracker.record(job, 80, "applied")
    tracker.record(job2, 40, "skipped")
    tracker.record(job3, 70, "failed")

    stats = tracker.stats()
    assert stats["applied"] == 1
    assert stats["skipped"] == 1
    assert stats["failed"] == 1
    assert stats["total"] == 3


def test_csv_is_written_on_apply(tracker, job, tmp_path):
    csv_path = str(tmp_path / "applications.csv")
    tracker.csv_path = csv_path
    tracker.record(job, 80, "applied", cover_letter="Dear hiring manager...")

    import csv
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["date", "company", "title", "platform", "score", "url", "cover_letter"]
    assert rows[1][1] == "Test Corp"
    assert rows[1][4] == "80"


def test_csv_not_written_for_skipped(tracker, job, tmp_path):
    csv_path = str(tmp_path / "applications.csv")
    tracker.csv_path = csv_path
    tracker.record(job, 40, "skipped")

    import os
    assert not os.path.exists(csv_path)
