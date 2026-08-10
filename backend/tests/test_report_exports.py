from __future__ import annotations

import asyncio
from datetime import date
from io import BytesIO
from pathlib import Path
from threading import Event
from time import sleep
from zipfile import ZipFile

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.auth import COOKIE_NAME
from app.application.queries import DashboardQuery, build_platform_dashboard
from app.application.services.report_exports import (
    ReportArtifact,
    ReportJobError,
    ReportJobManager,
)
from app.domain.metrics import bootstrap_metric_catalog
from app.domain.platforms import PlatformId
from app.domain.reporting import ReportingRange
from app.infrastructure.reports import ReportContext, build_platform_xlsx
from app.main import create_app
from tests.test_phase6_dashboard_api import MemoryAuthority, MemoryReporting


def test_report_job_is_owner_bound_and_consumed_once() -> None:
    manager = ReportJobManager(ttl_seconds=60)
    completed = Event()

    def render(progress):
        progress(44, "Rendering workbook")
        completed.set()
        return ReportArtifact("report.xlsx", b"xlsx")

    try:
        view = manager.enqueue(
            owner_session_hash="owner-a",
            brand_id="101",
            rollup=False,
            task=render,
        )
        assert completed.wait(timeout=2)
        for _ in range(100):
            status = manager.status(job_id=view.job_id, owner_session_hash="owner-a")
            if status.state == "ready":
                break
            sleep(0.01)
        assert status.state == "ready"
        assert status.progress == 100
        with pytest.raises(ReportJobError, match="report_job_not_found"):
            manager.status(job_id=view.job_id, owner_session_hash="owner-b")
        artifact = manager.consume(job_id=view.job_id, owner_session_hash="owner-a")
        assert artifact == ReportArtifact("report.xlsx", b"xlsx")
        with pytest.raises(ReportJobError, match="report_job_not_found"):
            manager.consume(job_id=view.job_id, owner_session_hash="owner-a")
    finally:
        manager.close()


def test_report_job_expires_without_persistent_artifact() -> None:
    manager = ReportJobManager(ttl_seconds=0.02)
    try:
        view = manager.enqueue(
            owner_session_hash="owner-a",
            brand_id="101",
            rollup=False,
            task=lambda _progress: ReportArtifact("report.xlsx", b"xlsx"),
        )
        for _ in range(100):
            status = manager.status(job_id=view.job_id, owner_session_hash="owner-a")
            if status.state == "ready":
                break
            sleep(0.01)
        assert status.state == "ready"
        sleep(0.08)
        with pytest.raises(ReportJobError, match="report_job_not_found"):
            manager.consume(job_id=view.job_id, owner_session_hash="owner-a")
    finally:
        manager.close()


def test_instagram_workbook_is_native_safe_and_uses_dashboard_projection(
    tmp_path: Path,
) -> None:
    media = tmp_path / "ig.jpg"
    media.write_bytes(b"fixture")
    reporting = MemoryReporting(media)
    dashboard = build_platform_dashboard(
        store=reporting,
        catalog=bootstrap_metric_catalog(),
        platform=PlatformId.INSTAGRAM,
        query=DashboardQuery(
            requested_brand_id="101",
            resolved_brand_ids=("101",),
            rollup=False,
            date_range=ReportingRange(
                date(2026, 7, 1),
                date(2026, 7, 2),
                "custom",
            ),
        ),
    )
    artifact = build_platform_xlsx(
        dashboard=dashboard,
        context=ReportContext(
            brand_name="Pine Beach Belek",
            account_name="Instagram A",
            surface="instagram",
            tab="cover",
            rollup=False,
        ),
        progress=lambda _value, _stage: None,
    )

    assert artifact.filename == ("accumulate-pine-beach-belek-instagram-cover-2026-07-02.xlsx")
    with ZipFile(BytesIO(artifact.content)) as archive:
        names = set(archive.namelist())
        workbook_xml = archive.read("xl/workbook.xml").decode()
        worksheet_xml = "".join(
            archive.read(name).decode(errors="ignore")
            for name in names
            if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
        )
        chart_xml = "".join(
            archive.read(name).decode(errors="ignore")
            for name in names
            if name.startswith("xl/charts/chart")
        )

    expected_sheets = {
        "Report Info",
        "Page",
        "Content",
        "Stories",
        "Audience",
        "All Content",
        "Story History",
        "Data - Breakdowns",
        "Community",
        "Data Dictionary",
    }
    assert all(name in workbook_xml for name in expected_sheets)
    assert "xl/media/image1.png" in names
    assert not any(name.startswith("xl/externalLinks/") for name in names)
    assert not any(name.endswith("vbaProject.bin") for name in names)
    assert "<f>" not in worksheet_xml
    assert "#REF!" not in worksheet_xml
    assert "#VALUE!" not in worksheet_xml
    assert "38BDF8" in chart_xml
    assert "EC4899" in chart_xml


@pytest.mark.asyncio
async def test_xlsx_api_queues_reports_and_removes_first_download(
    tmp_path: Path,
) -> None:
    media = tmp_path / "ig.jpg"
    media.write_bytes(b"fixture")
    authority = MemoryAuthority()
    reporting = MemoryReporting(media)
    app = create_app(authority, reporting, tmp_path)
    cookies = {COOKIE_NAME: authority.raw_session}
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            cookies=cookies,
        ) as client:
            denied = await client.post(
                "/api/reports/xlsx",
                params={"surface": "instagram"},
                headers={"Origin": "http://invalid.test"},
            )
            assert denied.status_code == 403

            created = await client.post(
                "/api/reports/xlsx",
                params={
                    "surface": "instagram",
                    "tab": "cover",
                    "brand_id": "101",
                    "start_date": "2026-07-01",
                    "end_date": "2026-07-02",
                },
                headers={"Origin": "http://test"},
            )
            assert created.status_code == 202
            job = created.json()
            assert job["state"] in {"queued", "running", "ready"}
            assert 0 <= job["progress"] <= 100

            for _ in range(100):
                status = await client.get(f"/api/reports/xlsx/{job['job_id']}")
                assert status.status_code == 200
                body = status.json()
                if body["state"] == "ready":
                    break
                await asyncio.sleep(0.01)
            assert body["state"] == "ready"
            assert body["progress"] == 100

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                cookies={COOKIE_NAME: "another-session"},
            ) as another_client:
                wrong_owner = await another_client.get(f"/api/reports/xlsx/{job['job_id']}")
            assert wrong_owner.status_code == 404

            download = await client.post(
                f"/api/reports/xlsx/{job['job_id']}/download",
                headers={"Origin": "http://test"},
            )
            assert download.status_code == 200
            assert download.content.startswith(b"PK")
            assert download.headers["cache-control"] == "no-store"
            assert (
                'filename="accumulate-child-a-instagram-cover-2026-07-02.xlsx"'
                in download.headers["content-disposition"]
            )

            gone = await client.get(f"/api/reports/xlsx/{job['job_id']}")
            assert gone.status_code == 404
    finally:
        app.state.report_jobs.close()
