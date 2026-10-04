"""Behavioral invariants for the local, standard-library learning record tool."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import uuid

SCRIPT = Path(__file__).resolve().parents[1] / "skills/learnmed/scripts/learning_store.py"
spec = importlib.util.spec_from_file_location("learning_store", SCRIPT)
store = importlib.util.module_from_spec(spec)
spec.loader.exec_module(store)


def material():
    return {
        "sources": [{"id": "S1", "title": "自编示例A", "locator": "第1节（无页码）", "verification": "verified"}],
        "concepts": [{"id": "K1", "title": "心输出量的决定因素", "topic": "生理学/循环", "priority": "core", "source_ids": ["S1"], "verification": "verified", "prompt": "心输出量由哪两个量共同决定？", "answer": "心率和每搏量。", "estimated_minutes": 2}],
    }


def event(event_id="R1", day="2026-10-04", result="correct", **overrides):
    attempt = {"concept_id": "K1", "prompt": "心输出量由哪两个量共同决定？", "user_answer": "心率和每搏量", "expected_answer": "心率和每搏量", "source_ids": ["S1"], "result": result, "confidence": "medium", "kind": "recall"}
    attempt.update(overrides)
    return {"id": event_id, "date": day, "minutes": 5, "attempts": [attempt], "notes": "今日学习"}


class StoreTests(unittest.TestCase):
    def setUp(self):
        # Keep test records inside the permitted workspace, including on Windows.
        self.test_root = SCRIPT.parents[3] / "learning-data" / "tests"
        self.test_root.mkdir(parents=True, exist_ok=True)
        self.temp_path = self.test_root / ("case-" + uuid.uuid4().hex)
        self.temp_path.mkdir()
        self.path = self.temp_path / "personal.learnmed.json"
        store.initialize(self.path, "2026-10-04", "Asia/Shanghai")
        store.upsert(self.path, material(), "2026-10-04")

    def tearDown(self):
        self.temp_path.resolve().relative_to(self.test_root.resolve())
        for file in self.temp_path.iterdir():
            file.unlink()
        self.temp_path.rmdir()

    def test_new_material_is_untested_and_due_tomorrow(self):
        data = store.read_store(self.path)
        self.assertEqual(store.progress(data, "K1")["status"], "untested")
        self.assertEqual(data["concepts"]["K1"]["due"], "2026-10-05")
        self.assertEqual(store.due(self.path, "2026-10-04", 10)["selected"], [])

    def test_same_event_is_idempotent(self):
        store.record(self.path, event())
        before = self.path.read_bytes()
        self.assertFalse(store.record(self.path, event())["written"])
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(len(store.read_store(self.path)["sessions"]), 1)

    def test_conflicting_retry_preserves_original(self):
        store.record(self.path, event())
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            store.record(self.path, event(result="wrong"))
        self.assertEqual(before, self.path.read_bytes())

    def test_same_day_correct_is_not_delayed_retention(self):
        store.record(self.path, event())
        store.record(self.path, event("R2"))
        data = store.read_store(self.path)
        self.assertEqual(store.progress(data, "K1")["status"], "recalled")
        self.assertEqual(store.progress(data, "K1")["independent_days"], 1)
        self.assertEqual(data["concepts"]["K1"]["due"], "2026-10-05")

    def test_delayed_application_supports_transfer(self):
        store.record(self.path, event())
        store.record(self.path, event("R2", "2026-10-05", kind="application", prompt="心率不变，每搏量增大时心输出量如何变？", user_answer="增大", expected_answer="增大"))
        data = store.read_store(self.path)
        self.assertEqual(store.progress(data, "K1")["status"], "transfer-supported")
        self.assertEqual(data["concepts"]["K1"]["due"], "2026-10-08")

    def test_wrong_and_hinted_do_not_claim_mastery(self):
        store.record(self.path, event(result="wrong", user_answer="只有心率", confidence="high"))
        self.assertEqual(store.progress(store.read_store(self.path), "K1")["status"], "relearn")
        store.record(self.path, event("R2", "2026-10-05", "hinted"))
        data = store.read_store(self.path)
        self.assertEqual(store.progress(data, "K1")["status"], "supported")
        self.assertEqual(data["concepts"]["K1"]["due"], "2026-10-06")

    def test_wrong_after_retention_resets_current_evidence(self):
        store.record(self.path, event())
        store.record(self.path, event("R2", "2026-10-05"))
        self.assertEqual(store.progress(store.read_store(self.path), "K1")["status"], "retained")
        store.record(self.path, event("R3", "2026-10-08", "wrong"))
        p = store.progress(store.read_store(self.path), "K1")
        self.assertEqual(p["status"], "relearn")
        self.assertEqual(p["independent_days"], 0)

    def test_future_and_out_of_order_sessions_rejected(self):
        store.record(self.path, event("R2", "2026-10-06"))
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            store.record(self.path, event("R1", "2026-10-04"))
        self.assertEqual(before, self.path.read_bytes())
        with self.assertRaises(ValueError):
            store.record(self.path, event("R3", "2026-10-06"), on="2026-10-05")

    def test_invalid_batch_is_all_or_nothing(self):
        bad = event()
        bad["attempts"].append({**bad["attempts"][0], "concept_id": "UNKNOWN"})
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            store.record(self.path, bad)
        self.assertEqual(before, self.path.read_bytes())

    def test_untested_is_not_an_attempt(self):
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            store.record(self.path, event(result="untested"))
        self.assertEqual(before, self.path.read_bytes())

    def test_missing_answer_and_unknown_source_rejected(self):
        for patch in ({"user_answer": ""}, {"source_ids": ["missing"]}, {"confidence": "sure"}):
            with self.assertRaises(ValueError):
                store.record(self.path, event(**patch))

    def test_upsert_preserves_history_and_schedule(self):
        store.record(self.path, event())
        patch = material()
        patch["concepts"][0]["title"] = "心输出量：心率与每搏量"
        store.upsert(self.path, patch, "2026-10-05")
        data = store.read_store(self.path)
        self.assertEqual(len(data["sessions"]), 1)
        self.assertEqual(data["concepts"]["K1"]["due"], "2026-10-05")
        self.assertEqual(store.progress(data, "K1")["status"], "recalled")

    def test_answer_revision_keeps_old_attempts_but_requires_retest(self):
        store.record(self.path, event())
        patch = material()
        patch["concepts"][0]["answer"] = "心率及每搏量；说明适用模型。"
        store.upsert(self.path, patch, "2026-10-05")
        data = store.read_store(self.path)
        self.assertEqual(data["concepts"]["K1"]["revision"], 2)
        self.assertEqual(data["sessions"][0]["attempts"][0]["expected_answer"], "心率和每搏量")
        self.assertEqual(store.progress(data, "K1")["status"], "untested")
        self.assertEqual(data["concepts"]["K1"]["due"], "2026-10-06")

    def test_source_revision_keeps_original_provenance_snapshot(self):
        store.record(self.path, event())
        patch = material()
        patch["sources"][0]["locator"] = "修订第2节（原第1节不再适用）"
        store.upsert(self.path, patch, "2026-10-10")
        data = store.read_store(self.path)
        old_attempt = data["sessions"][0]["attempts"][0]
        self.assertEqual(old_attempt["source_snapshot"]["S1"]["locator"], "第1节（无页码）")
        self.assertEqual(data["sources"]["S1"]["locator"], "修订第2节（原第1节不再适用）")
        self.assertEqual(store.progress(data, "K1")["status"], "untested")

    def test_revision_preserves_even_untested_old_concept_and_source(self):
        patch = material()
        patch["sources"][0]["locator"] = "新版第2节"
        patch["concepts"][0]["answer"] = "修订答案"
        store.upsert(self.path, patch, "2026-10-10")
        data = store.read_store(self.path)
        self.assertEqual(data["concept_history"]["K1"][0]["answer"], "心率和每搏量。")
        self.assertEqual(data["source_history"]["S1"][0]["locator"], "第1节（无页码）")
        self.assertEqual(data["concepts"]["K1"]["revision"], 2)

    def test_old_date_cannot_be_relabelled_as_new_revision_evidence(self):
        store.record(self.path, event())
        patch = material()
        patch["concepts"][0]["answer"] = "心率和每搏量（修订）。"
        store.upsert(self.path, patch, "2026-10-10")
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            store.record(self.path, event("R2", "2026-10-05"))
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(store.progress(store.read_store(self.path), "K1")["status"], "untested")

    def test_reading_only_does_not_change_schedule_or_status(self):
        store.record(self.path, {"id": "read-1", "date": "2026-10-04", "minutes": 8, "attempts": [], "notes": "只读教材"})
        data = store.read_store(self.path)
        self.assertEqual(store.progress(data, "K1")["status"], "untested")
        self.assertEqual(data["concepts"]["K1"]["due"], "2026-10-05")
        self.assertEqual(store.summary(self.path, "2026-10-04")["attempt_count"], 0)

    def test_exact_duplicate_title_and_alias_collisions_rejected(self):
        patch = material()
        patch["concepts"][0]["id"] = "K2"
        with self.assertRaises(ValueError):
            store.upsert(self.path, patch, "2026-10-04")
        patch["concepts"][0]["title"] = "另一概念"
        patch["concepts"][0]["aliases"] = ["K1"]
        with self.assertRaises(ValueError):
            store.upsert(self.path, patch, "2026-10-04")

    def test_pending_sources_excluded_from_quiz_and_export(self):
        patch = material()
        patch["sources"][0]["verification"] = "pending"
        patch["concepts"][0]["verification"] = "pending"
        store.upsert(self.path, patch, "2026-10-04")
        self.assertEqual(store.due(self.path, "2026-10-10", 10)["selected"], [])
        with self.assertRaises(ValueError):
            store.record(self.path, event())
        self.assertEqual(store.anki_text(store.read_store(self.path)).count("\n"), 4)

    def test_budget_returns_actionable_subset_and_remaining(self):
        patch = material()
        patch["concepts"] = []
        for i in range(2, 8):
            c = copy.deepcopy(material()["concepts"][0])
            c.update(id=f"K{i}", title=f"概念{i}")
            patch["concepts"].append(c)
        store.upsert(self.path, patch, "2026-10-04")
        queue = store.due(self.path, "2026-10-05", 5)
        self.assertEqual(len(queue["selected"]), 2)
        self.assertEqual(queue["remaining"], 5)
        self.assertLessEqual(queue["estimated_minutes"], 5)
        self.assertNotIn("answer", queue["selected"][0])

    def test_due_prioritizes_confident_errors_over_untested(self):
        patch = material()
        patch["concepts"][0].update(id="K2", title="另一概念")
        store.upsert(self.path, patch, "2026-10-04")
        store.record(self.path, event(result="wrong", confidence="high"))
        self.assertEqual(store.due(self.path, "2026-10-05", 2)["selected"][0]["id"], "K1")

    def test_calendar_validation_and_minute_budget(self):
        for day in ("2026-2-3", "2026-02-30"):
            with self.assertRaises(ValueError):
                store.due(self.path, day, 10)
        for minutes in (0, -1, True):
            with self.assertRaises(ValueError):
                store.due(self.path, "2026-10-05", minutes)

    def test_lock_and_corrupt_store_fail_without_overwrite(self):
        lock = self.path.with_name(self.path.name + ".lock")
        lock.write_text("another process", encoding="utf-8")
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            store.record(self.path, event())
        self.assertEqual(before, self.path.read_bytes())
        lock.unlink()
        self.path.write_text("not JSON", encoding="utf-8")
        with self.assertRaises(ValueError):
            store.upsert(self.path, material(), "2026-10-05")
        self.assertEqual(self.path.read_text(encoding="utf-8"), "not JSON")

    def test_transient_windows_file_busy_retries_without_losing_data(self):
        real_replace = store.os.replace
        busy = PermissionError(13, "temporary Windows sharing lock")
        busy.winerror = 32
        calls = []
        def replace(source, target):
            calls.append((source, target))
            if len(calls) == 1:
                raise busy
            return real_replace(source, target)
        with patch.object(store.os, "replace", side_effect=replace):
            store.record(self.path, event())
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(store.read_store(self.path)["sessions"]), 1)

    def test_persistent_file_busy_keeps_original_and_cleans_temp(self):
        busy = PermissionError(13, "persistent Windows sharing lock")
        busy.winerror = 32
        before = self.path.read_bytes()
        with patch.object(store.os, "replace", side_effect=busy):
            with self.assertRaises(PermissionError):
                store.record(self.path, event())
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.temp_path.glob("*.tmp")), [])
        self.assertFalse(self.path.with_name(self.path.name + ".lock").exists())

    def test_summary_uses_observed_denominators(self):
        store.record(self.path, event(result="wrong", user_answer="心率", confidence="high"))
        store.record(self.path, event("R2", "2026-10-05", "hinted"))
        summary = store.summary(self.path, "2026-10-10")
        self.assertEqual(summary["attempt_count"], 2)
        self.assertEqual(summary["independent_correct"], 0)
        self.assertEqual(summary["high_confidence_errors"], 1)
        self.assertEqual(summary["recorded_minutes"], 10)

    def test_anki_escapes_markup_tabs_and_newlines(self):
        patch = material()
        patch["concepts"][0].update(prompt="A\tB < C?", answer='一行\n<script>bad</script> & "引号"')
        store.upsert(self.path, patch, "2026-10-04")
        text = store.anki_text(store.read_store(self.path))
        self.assertIn("&lt;script&gt;", text)
        self.assertIn("<br>", text)
        self.assertNotIn("<script>", text)
        self.assertEqual(len(text.splitlines()[-1].split("\t")), 3)

    def test_initialize_never_replaces_existing(self):
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            store.initialize(self.path, "2026-10-05", "Asia/Shanghai")
        self.assertEqual(before, self.path.read_bytes())


if __name__ == "__main__":
    unittest.main()
