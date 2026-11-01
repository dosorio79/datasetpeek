from __future__ import annotations

import csv
import io
import json
import re

import polars as pl
import pytest

DATASET_NAME = "browser-smoke.csv"
SAMPLE_SEEDS = (42, 43, 44, 45)


def _synthetic_csv() -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["record_id", "label", "note"])
    for index in range(1, 31):
        writer.writerow([f"id-{index:02d}", f"group-{index % 3}", "<b>literal</b>"])
    return buffer.getvalue().encode("utf-8")


def _expected_sample_ids(csv_bytes: bytes) -> list[list[str]]:
    dataframe = pl.read_csv(io.BytesIO(csv_bytes))
    return [
        dataframe.sample(n=3, shuffle=True, seed=seed)["record_id"].to_list()
        for seed in SAMPLE_SEEDS
    ]


def _visible_sample_ids(page) -> list[str]:
    return page.locator("#sample-table tbody tr td:first-child").all_text_contents()


@pytest.mark.browser
def test_upload_cycle_and_download_reports(app_url, browser_page, tmp_path):
    from playwright.sync_api import expect

    page, page_errors = browser_page
    csv_bytes = _synthetic_csv()
    expected_samples = _expected_sample_ids(csv_bytes)
    analyze_requests: list[str] = []
    page.on(
        "request",
        lambda request: (
            analyze_requests.append(request.url)
            if request.method == "POST" and request.url.endswith("/analyze")
            else None
        ),
    )

    page.goto(app_url)
    for selector in ("#download-markdown", "#download-html", "#download-json", "#sample-table"):
        expect(page.locator(selector)).to_have_count(0)

    page.set_input_files(
        "#dataset",
        files=[{"name": DATASET_NAME, "mimeType": "text/csv", "buffer": csv_bytes}],
    )
    page.click("#analyze-submit")
    expect(page.locator("#sample-table")).to_be_visible()
    expect(page.locator(".results-stack > section").first).to_have_class(
        re.compile(r"\bexport-panel\b")
    )
    export_note = page.locator("#export-note")
    expect(export_note).to_have_css("opacity", "0")
    page.get_by_role("button", name="JSON export limitations").focus()
    expect(export_note).to_have_css("opacity", "1")
    expect(page.locator(".summary-block .scope-note")).to_be_visible()
    expect(page.locator(".scope-note")).to_contain_text("exported sample")
    expect(page.locator("#sample-set-label")).to_have_text("Sample 1")
    assert _visible_sample_ids(page) == expected_samples[0]
    assert len(analyze_requests) == 1, (
        "The initial analysis should issue exactly one POST /analyze request"
    )
    requests_after_analysis = len(analyze_requests)

    for index in range(1, len(expected_samples)):
        page.click("#next-sample")
        expect(page.locator("#sample-set-label")).to_have_text(f"Sample {index + 1}")
        assert _visible_sample_ids(page) == expected_samples[index]
    page.click("#next-sample")
    expect(page.locator("#sample-set-label")).to_have_text("Sample 1")
    assert _visible_sample_ids(page) == expected_samples[0]
    assert len(analyze_requests) == requests_after_analysis, "Sample cycling must stay client-side"

    sample_table = page.locator("#sample-table")
    assert page.locator("#sample-table b, #sample-table script, #sample-table img").count() == 0
    assert sample_table.inner_text().count("<b>literal</b>") >= 3

    tmp_path.mkdir(exist_ok=True)
    downloads = {
        "#download-json": "profile-model.json",
        "#download-markdown": "datasetpeek-report.md",
        "#download-html": "datasetpeek-report.html",
    }
    payloads: dict[str, bytes] = {}
    for selector, filename in downloads.items():
        with page.expect_download() as download_info:
            page.click(selector)
        download = download_info.value
        assert download.suggested_filename == filename
        destination = tmp_path / filename
        download.save_as(destination)
        payloads[filename] = destination.read_bytes()

    document = json.loads(payloads["profile-model.json"])
    assert document["schema_version"] == "1.0.0"
    assert document["file"]["filename"] == DATASET_NAME
    assert document["file"]["rows"] == 30
    assert document["file"]["columns"] == 3
    for key in ("sample_rows", "head_rows", "tail_rows", "sample_values", "sample_sets"):
        assert key not in document

    markdown = payloads["datasetpeek-report.md"].decode("utf-8")
    assert DATASET_NAME in markdown
    assert "# DatasetPeek Profile Report" in markdown
    assert "## Column Overview" in markdown

    html = payloads["datasetpeek-report.html"].decode("utf-8")
    assert DATASET_NAME in html
    assert "<!doctype html>" in html
    assert "Column Overview" in html

    assert len(analyze_requests) == requests_after_analysis, "Downloads must stay client-side"
    assert page_errors == []
