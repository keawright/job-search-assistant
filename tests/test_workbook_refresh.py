from datetime import date
import json

from openpyxl import Workbook, load_workbook
import pytest

from job_search_assistant.ingestion import Page
from job_search_assistant.workbook import update_workbook

TODAY = date(2026, 10, 15)


def source(path, extra_headers=(), extra_values=()):
    wb = Workbook()
    ws = wb.active
    ws.title = "Application priorities"
    ws.append(["Company", "Position title", "Job posting", "Application status", "Comment", *extra_headers])
    ws.append(["Original Co", "Original Title", "https://example.com/1", "Not applied", "Do not edit", *extra_values])
    wb.save(path)
    wb.close()


def get_values(path):
    wb = load_workbook(path)
    ws = wb["Assistant queue"]
    data = dict(zip([c.value for c in ws[1]], [c.value for c in ws[2]]))
    wb.close()
    return data


def test_refresh_never_overwrites_manual_fields_and_retains_full_description(tmp_path):
    original, output = tmp_path / "input.xlsx", tmp_path / "output.xlsx"
    source(original, ("Deadline",), (date(2026, 10, 30),))
    description = "Original job description. " * 1600
    def fetch(url):
        data = {"@type": "JobPosting", "title": "Fetched Title", "hiringOrganization": {"name": "Fetched Co"}, "description": description, "validThrough": "2026-10-20"}
        return Page(url, '<script type="application/ld+json">' + json.dumps(data) + '</script>')
    update_workbook(original, output, [], as_of=TODAY, refresh=True, fetcher=fetch)
    values = get_values(output)
    assert values["Company"] == "Original Co" and values["Position title"] == "Original Title"
    assert values["Comment"] == "Do not edit"
    assert values["Deadline"].date() == date(2026, 10, 30)
    assert len(values["Assistant description"]) == 30000
    snapshot = json.loads(__import__('pathlib').Path(values["Assistant snapshot"]).read_text(encoding="utf-8"))
    assert snapshot["extracted"]["description"] == description.strip()


@pytest.mark.parametrize("headers,values", [(("Vacancy status",), ("Closed on LinkedIn",)),
    (("Vacancy status",), ("Apparently closed — not on current board",)),
    (("Can work from Halifax?",), ("No — Toronto office required",))])
def test_legacy_exclusions_do_not_silently_become_actionable(tmp_path, headers, values):
    original, output = tmp_path / "input.xlsx", tmp_path / "output.xlsx"
    source(original, headers, values)
    update_workbook(original, output, [], as_of=TODAY, offline=True)
    assert get_values(output)["Assistant section"] == "Review"


def test_passed_date_excluded_and_original_formula_preserved(tmp_path):
    original, output = tmp_path / "input.xlsx", tmp_path / "output.xlsx"
    source(original, ("Deadline", "Calculation"), (date(2026, 10, 14), "=LEN(A2)"))
    update_workbook(original, output, [], as_of=TODAY, offline=True)
    values = get_values(output)
    assert values["Assistant section"] == "Review"
    assert values["Calculation"] == "=LEN(A2)"


def test_invalid_url_batch_leaves_no_output(tmp_path):
    original, output = tmp_path / "input.xlsx", tmp_path / "output.xlsx"
    source(original)
    with pytest.raises(ValueError):
        update_workbook(original, output, ["https://example.com/ok", "file:///private"], as_of=TODAY)
    assert not output.exists()


def test_invalid_assessment_keeps_original_data_for_review(tmp_path):
    original, output = tmp_path / "input.xlsx", tmp_path / "output.xlsx"
    source(original, ("Leadership fit",), ("strong",))
    update_workbook(original, output, [], as_of=TODAY, offline=True)
    values = get_values(output)
    assert values["Assistant section"] == "Review"
    assert values["Leadership fit"] == "strong"
    assert "Evidence required" in values["Assistant review flags"]
