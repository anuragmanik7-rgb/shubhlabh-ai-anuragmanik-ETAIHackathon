"""Small regression gates for the new corpus; full lifecycle is an explicit script.

These checks verify corpus integrity, daily aggregation uniqueness and rejection
semantics. They do not silently invoke models or repeatedly run the optimizer.
"""
import csv
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path

import pytest

from backend.app.domain import AppError
from backend.app.ingestion import import_table, ingest_document, correct_evidence
from backend.app.persistence import Store
from backend.app.seed import create_retailer
from scripts.evaluate_realistic import evaluation_clock

FOLDER = Path(__file__).resolve().parents[1] / "fixtures" / "remediation"
MANIFEST = json.loads((FOLDER / "manifest.json").read_text(encoding="utf-8"))


def rows(name):
    with (FOLDER / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_realistic_corpus_checksums_and_upload_bounds():
    for name, meta in MANIFEST["files"].items():
        content = (FOLDER / name).read_bytes()
        assert hashlib.sha256(content).hexdigest() == meta["sha256"], name
        assert len(content) == meta["bytes"] < 8 * 1024 * 1024, name
    for case in MANIFEST["operational_files"]:
        assert len(rows(case["path"])) == case["rows"] < 10000


def test_realistic_daily_cube_has_no_missing_or_duplicate_cells():
    end = date.fromisoformat(MANIFEST["business_date_ist"])
    expected_dates = {str(end - timedelta(days=i)) for i in range(1, 181)}
    expected_skus = {f"SKU{i:03d}" for i in range(1, 121)}
    expected_cities = {"Bengaluru", "Mumbai", "Delhi"}
    cube = {}
    censored = baskets = 0
    for case in MANIFEST["operational_files"]:
        if case["kind"] != "transactions":
            continue
        for row in rows(case["path"]):
            key = row["sku"], row["city"], row["date"]
            assert key not in cube, key
            assert row["sku"] in expected_skus and row["city"] in expected_cities
            assert row["date"] in expected_dates
            assert int(row["quantity"]) >= 0 and int(row["paid_price_paise"]) > 0
            assert row["stockout"] in ["true", "false"]
            assert set(row["basket_items"].split("|")) - {""} <= expected_skus
            censored += row["stockout"] == "true"
            baskets += bool(row["basket_items"])
            cube[key] = row
    assert len(cube) == len(expected_dates) * len(expected_skus) * len(expected_cities) == 64800
    assert censored == MANIFEST["dimensions"]["stockout_history_rows"]
    assert baskets == MANIFEST["dimensions"]["new_basket_rows"] == 1620


@pytest.mark.parametrize("case", MANIFEST["adversarial_imports"], ids=lambda c: c["path"])
def test_realistic_adversarial_imports_are_atomic(tmp_path, case):
    store = Store("sqlite:///" + (tmp_path / "adversarial.sqlite3").as_posix())
    try:
        with evaluation_clock(MANIFEST["scenario_clock_utc"]):
            original = create_retailer()
            store.put_new("fixture-test", "state", "retailer", original)
            if "expected_error" in case:
                with pytest.raises(AppError) as error:
                    import_table(store, "fixture-test", case["path"], (FOLDER / case["path"]).read_bytes(), case["kind"])
                assert error.value.code == case["expected_error"]
            else:
                result = import_table(store, "fixture-test", case["path"], (FOLDER / case["path"]).read_bytes(), case["kind"])
                assert result["status"] == "rejected"
            assert store.get("fixture-test", "state", "retailer") == original
    finally:
        store.engine.dispose()


def test_realistic_policy_evidence_requires_confirmation_and_image_abstains(tmp_path):
    store = Store("sqlite:///" + (tmp_path / "evidence.sqlite3").as_posix())
    try:
        with evaluation_clock(MANIFEST["scenario_clock_utc"]):
            original = create_retailer()
            store.put_new("fixture-test", "state", "retailer", original)
            for name in ["policy.txt", "policy.pdf"]:
                record = ingest_document(store, "fixture-test", name, (FOLDER / name).read_bytes(), "offline")
                assert record["fields"]["budget_paise"] == 1800000
                assert record["status"] == "needs_review"
                assert store.get("fixture-test", "state", "retailer") == original
            record = ingest_document(store, "fixture-test", "competitor-card.png", (FOLDER / "competitor-card.png").read_bytes(), "offline")
            assert record["status"] == "needs_review"
            assert "price_paise" not in record["fields"]
            assert store.get("fixture-test", "state", "retailer") == original
            incomplete = ingest_document(store, "fixture-test", "missing-critical-policy.pdf", (FOLDER / "missing-critical-policy.pdf").read_bytes(), "offline")
            with pytest.raises(AppError) as error:
                correct_evidence(store, "fixture-test", incomplete["id"], incomplete["fields"])
            assert error.value.code == "INCOMPLETE_POLICY"
            assert store.get("fixture-test", "state", "retailer") == original
    finally:
        store.engine.dispose()
