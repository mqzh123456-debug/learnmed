#!/usr/bin/env python3
"""Local learning records. Python 3.10+, standard library only, no network calls."""
import argparse
from contextlib import contextmanager
import copy
from datetime import date, datetime, timedelta
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

RESULTS = {"wrong", "partial", "hinted", "correct"}
PRIORITIES = {"core": 0, "important": 1, "extension": 2}
INTERVALS = (1, 3, 7, 14, 30, 60)


def day(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("日期须为 YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("日期不存在") from exc


def text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} 必须为非空文本；未答题请勿提交检测")
    return value


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", value):
        raise ValueError("ID 须为1-96位字母、数字、点、下划线或连字符")
    return value


def positive(value, name):
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} 必须为正整数")
    return value


def strings(value, name, required=False):
    if not isinstance(value, list) or any(not isinstance(v, str) or not v.strip() for v in value):
        raise ValueError(f"{name} 必须为文本列表")
    if required and not value:
        raise ValueError(f"{name} 不可为空")
    if len(value) != len(set(value)):
        raise ValueError(f"{name} 存在重复值")


def source_check(source):
    identifier(source.get("id"))
    text(source.get("title"), "source.title")
    text(source.get("locator"), "source.locator")
    if source.get("verification") not in {"verified", "pending"}:
        raise ValueError("source.verification 须为 verified 或 pending")


def concept_check(concept, sources):
    identifier(concept.get("id"))
    for key in ("title", "topic", "prompt", "answer"):
        text(concept.get(key), f"concept.{key}")
    if concept.get("priority") not in PRIORITIES:
        raise ValueError("priority 须为 core / important / extension")
    if concept.get("verification") not in {"verified", "pending"}:
        raise ValueError("concept.verification 须为 verified 或 pending")
    positive(concept.get("estimated_minutes", 2), "estimated_minutes")
    strings(concept.get("source_ids"), "source_ids", True)
    strings(concept.get("aliases", []), "aliases")
    strings(concept.get("related_ids", []), "related_ids")
    strings(concept.get("tags", []), "tags")
    for sid in concept["source_ids"]:
        if sid not in sources:
            raise ValueError(f"未知来源 {sid}")
    if concept["verification"] == "verified" and any(sources[s]["verification"] != "verified" for s in concept["source_ids"]):
        raise ValueError("verified 知识点须引用已核验来源")


def verified(data, concept):
    return concept["verification"] == "verified" and all(data["sources"][s]["verification"] == "verified" for s in concept["source_ids"])


def read_store(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            raise ValueError("不支持的记录版本")
        if not isinstance(data.get("sources"), dict) or not isinstance(data.get("concepts"), dict) or not isinstance(data.get("sessions"), list):
            raise ValueError("记录结构无效")
        day(data["created"])
        text(data["timezone"], "timezone")
        for key, source in data["sources"].items():
            source_check(source)
            if key != source["id"]:
                raise ValueError("来源ID不一致")
        for key, c in data["concepts"].items():
            concept_check(c, data["sources"])
            day(c["created"])
            day(c["due"])
            day(c.get("revision_date", c["created"]))
            positive(c["revision"], "revision")
            if key != c["id"]:
                raise ValueError("知识点ID不一致")
        return data
    except (OSError, json.JSONDecodeError, KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"记录不可读或已损坏，未覆盖：{exc}") from exc


@contextmanager
def locked(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".lock")
    try:
        handle = lock.open("x", encoding="utf-8")
    except FileExistsError as exc:
        raise ValueError(f"记录正在写入或有遗留锁：{lock}；先确认没有其他写入进程") from exc
    try:
        with handle:
            handle.write(str(os.getpid()))
        yield path
    finally:
        lock.unlink(missing_ok=True)


def save(path, data):
    # Replace only a fully written file in the same directory; errors leave old data intact.
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=path.name + ".", suffix=".tmp", delete=False) as f:
            name = f.name
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        # Windows sync/scanner processes may briefly hold the destination open.
        for attempt in range(4):
            try:
                os.replace(name, path)
                break
            except PermissionError as exc:
                if getattr(exc, "winerror", None) not in {5, 32, 33} or attempt == 3:
                    raise
                time.sleep(0.05 * (attempt + 1))
    finally:
        if name and Path(name).exists():
            Path(name).unlink()


def initialize(path, on, timezone):
    day(on)
    text(timezone, "timezone")
    with locked(path) as dest:
        if dest.exists():
            raise ValueError("记录已存在；init 不会清空旧记录")
        save(dest, {"schema_version": 1, "created": on, "timezone": timezone, "sources": {}, "concepts": {}, "source_history": {}, "concept_history": {}, "sessions": []})
    return {"written": True, "path": str(Path(path).resolve())}


def upsert(path, payload, on):
    today = day(on)
    if not isinstance(payload, dict) or set(payload) - {"sources", "concepts"}:
        raise ValueError("upsert 输入仅支持 sources 和 concepts")
    if any(not isinstance(payload.get(k, []), list) for k in ("sources", "concepts")):
        raise ValueError("sources / concepts 须为列表")
    with locked(path) as dest:
        data = read_store(dest)
        old_sources = copy.deepcopy(data["sources"])
        old_concepts = copy.deepcopy(data["concepts"])
        data.setdefault("source_history", {})
        data.setdefault("concept_history", {})
        if today < day(data["created"]) or any(today < day(c.get("revision_date", c["created"])) for c in old_concepts.values()):
            raise ValueError("不能倒序修订知识库")
        if any(today < day(s["date"]) for s in data["sessions"]):
            raise ValueError("修订日期不可早于已记录检测日期")
        seen = set()
        for s in payload.get("sources", []):
            source_check(s)
            if s["id"] in seen:
                raise ValueError("同一批来源ID重复")
            seen.add(s["id"])
            if s["id"] in old_sources and s != old_sources[s["id"]]:
                data["source_history"].setdefault(s["id"], []).append({**copy.deepcopy(old_sources[s["id"]]), "archived_on": on})
            data["sources"][s["id"]] = copy.deepcopy(s)
        seen = set()
        for raw in payload.get("concepts", []):
            if set(raw) & {"revision", "revision_date", "created", "due", "status", "mastery"}:
                raise ValueError("不可通过 upsert 设置掌握状态、版本或复习日期")
            concept_check(raw, data["sources"])
            if raw["id"] in seen:
                raise ValueError("同一批知识点ID重复")
            seen.add(raw["id"])
            old = data["concepts"].get(raw["id"])
            c = {**copy.deepcopy(raw), "estimated_minutes": raw.get("estimated_minutes", 2), "aliases": raw.get("aliases", []), "related_ids": raw.get("related_ids", []), "tags": raw.get("tags", [])}
            c.update(created=old["created"] if old else on, revision=old["revision"] if old else 1, revision_date=old.get("revision_date", old["created"]) if old else on, due=old["due"] if old else (today + timedelta(days=1)).isoformat())
            data["concepts"][c["id"]] = c
        identities = set(data["concepts"])
        normalized = set()
        for c in data["concepts"].values():
            concept_check(c, data["sources"])
            key = (c["topic"].strip().casefold(), c["title"].strip().casefold())
            if key in normalized:
                raise ValueError("同主题同名知识点重复；复用原ID")
            normalized.add(key)
            for alias in c["aliases"]:
                if alias in identities:
                    raise ValueError("别名与知识点ID或其他别名冲突")
                identities.add(alias)
            if any(r not in data["concepts"] or r == c["id"] for r in c["related_ids"]):
                raise ValueError("related_ids 须引用其他现有知识点")
            changed_source = any(s in old_sources and old_sources[s] != data["sources"][s] for s in c["source_ids"])
            old = old_concepts.get(c["id"])
            changed_content = old and any(old[k] != c[k] for k in ("prompt", "answer", "source_ids", "verification"))
            if old and (changed_source or changed_content):
                data["concept_history"].setdefault(c["id"], []).append({**copy.deepcopy(old), "archived_on": on})
                c["revision"] = old["revision"] + 1
                c["revision_date"] = on
                c["due"] = (today + timedelta(days=1)).isoformat()
        save(dest, data)
    return {"written": True, "sources": len(data["sources"]), "concepts": len(data["concepts"])}


def attempts_for(data, concept_id):
    c = data["concepts"][concept_id]
    return [(s["date"], a) for s in data["sessions"] for a in s["attempts"] if a["concept_id"] == concept_id and a["concept_revision"] == c["revision"]]


def progress(data, concept_id):
    c = data["concepts"][concept_id]
    days = set()
    application = False
    attempts = attempts_for(data, concept_id)
    for when, a in attempts:
        if a["result"] == "correct":
            days.add(when)
            application = application or a["kind"] == "application"
        else:
            days.clear()
            application = False
    last = attempts[-1][1] if attempts else None
    if not verified(data, c):
        status = "pending"
    elif last is None:
        status = "untested"
    elif last["result"] != "correct":
        status = {"wrong": "relearn", "partial": "developing", "hinted": "supported"}[last["result"]]
    elif len(days) < 2:
        status = "recalled"
    else:
        status = "transfer-supported" if application else "retained"
    return {"status": status, "independent_days": len(days), "last_result": last["result"] if last else None, "last_confidence": last["confidence"] if last else None}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def record(path, payload, on=None):
    if not isinstance(payload, dict) or set(payload) - {"id", "date", "minutes", "attempts", "notes"}:
        raise ValueError("session 输入字段无效")
    identifier(payload.get("id"))
    when = day(payload.get("date"))
    positive(payload.get("minutes"), "minutes")
    if on is not None and when > day(on):
        raise ValueError("不可记录未来日期的已完成学习")
    if not isinstance(payload.get("attempts"), list):
        raise ValueError("attempts 须为列表；只读教材可以提交空列表")
    fingerprint = digest(payload)
    with locked(path) as dest:
        data = read_store(dest)
        for s in data["sessions"]:
            if s["id"] == payload["id"]:
                if s["input_digest"] != fingerprint:
                    raise ValueError("同一session ID内容冲突；原始作答保留")
                return {"written": False, "reason": "already-recorded"}
        if when < day(data["created"]) or any(when < day(s["date"]) for s in data["sessions"]):
            raise ValueError("session 日期须按时间顺序提交；不支持倒序补记检测")
        session = copy.deepcopy(payload)
        session["input_digest"] = fingerprint
        affected = set()
        for a in session["attempts"]:
            cid = a.get("concept_id")
            if cid not in data["concepts"]:
                raise ValueError(f"未知知识点 {cid}")
            c = data["concepts"][cid]
            if when < day(c.get("revision_date", c["created"])) or not verified(data, c):
                raise ValueError("检测早于当前版本生效日期或来源待核验，不能计入当前版本")
            for key in ("prompt", "user_answer", "expected_answer"):
                text(a.get(key), key)
            strings(a.get("source_ids"), "attempt.source_ids", True)
            if any(s not in c["source_ids"] or data["sources"][s]["verification"] != "verified" for s in a["source_ids"]):
                raise ValueError("检测来源须属于知识点的已核验来源")
            if a.get("result") not in RESULTS:
                raise ValueError("result 须为 wrong / partial / hinted / correct；无作答不是检测")
            if a.get("confidence") not in {"low", "medium", "high", "unknown"}:
                raise ValueError("confidence 须为 low / medium / high / unknown")
            if a.get("kind") not in {"recall", "application"}:
                raise ValueError("kind 须为 recall 或 application")
            a["concept_revision"] = c["revision"]
            a["source_snapshot"] = {sid: copy.deepcopy(data["sources"][sid]) for sid in a["source_ids"]}
            affected.add(cid)
        data["sessions"].append(session)
        for cid in affected:
            p = progress(data, cid)
            interval = INTERVALS[min(p["independent_days"], len(INTERVALS)) - 1] if p["last_result"] == "correct" else 1
            data["concepts"][cid]["due"] = (when + timedelta(days=interval)).isoformat()
        save(dest, data)
    return {"written": True, "id": session["id"], "progress": {cid: {**progress(data, cid), "due": data["concepts"][cid]["due"]} for cid in sorted(affected)}}


def due(path, on, minutes):
    today = day(on)
    positive(minutes, "minutes")
    data = read_store(path)
    candidates = []
    for c in data["concepts"].values():
        if verified(data, c) and day(c["due"]) <= today:
            p = progress(data, c["id"])
            key = (0 if p["last_result"] == "wrong" and p["last_confidence"] == "high" else 1, PRIORITIES[c["priority"]], c["due"], c["id"])
            candidates.append((key, c, p))
    candidates.sort(key=lambda item: item[0])
    selected, used = [], 0
    for _, c, p in candidates:
        if used + c["estimated_minutes"] <= minutes:
            selected.append({"id": c["id"], "title": c["title"], "prompt": c["prompt"], "due": c["due"], "estimated_minutes": c["estimated_minutes"], **p})
            used += c["estimated_minutes"]
    return {"date": on, "selected": selected, "estimated_minutes": used, "due_total": len(candidates), "remaining": len(candidates) - len(selected), "pending_total": sum(not verified(data, c) for c in data["concepts"].values()), "smallest_item_minutes": min((c["estimated_minutes"] for _, c, _ in candidates), default=None)}


def summary(path, on):
    end = day(on)
    start = end - timedelta(days=6)
    data = read_store(path)
    sessions = [s for s in data["sessions"] if start <= day(s["date"]) <= end]
    attempts = [a for s in sessions for a in s["attempts"]]
    statuses = {}
    for cid in data["concepts"]:
        status = progress(data, cid)["status"]
        statuses[status] = statuses.get(status, 0) + 1
    return {"from": start.isoformat(), "to": on, "session_count": len(sessions), "attempt_count": len(attempts), "independent_correct": sum(a["result"] == "correct" for a in attempts), "hinted": sum(a["result"] == "hinted" for a in attempts), "high_confidence_errors": sum(a["result"] in {"wrong", "partial"} and a["confidence"] == "high" for a in attempts), "recorded_minutes": sum(s["minutes"] for s in sessions), "current_status_counts": statuses, "concept_count": len(data["concepts"]), "scope": "仅已记录知识点和作答；不能推算整门课程或考试成绩"}


def anki_text(data):
    def field(value):
        return html.escape(value).replace("\t", " ").replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")
    rows = ["#separator:tab", "#html:true", "#columns:Front\tBack\tTags", "#tags column:3"]
    for c in sorted(data["concepts"].values(), key=lambda c: c["id"]):
        if verified(data, c):
            provenance = "; ".join(data["sources"][s]["title"] + " / " + data["sources"][s]["locator"] for s in c["source_ids"])
            front = field(c["id"] + " · " + c["prompt"])
            back = field(c["answer"]) + "<br><br>来源：" + field(provenance)
            rows.append(front + "\t" + back + "\tlearnmed " + c["id"])
    return "\n".join(rows) + "\n"


def local_today(timezone):
    try:
        return datetime.now(ZoneInfo(timezone)).date().isoformat()
    except ZoneInfoNotFoundError as exc:
        raise ValueError("本机缺少时区数据库；请显式传入 --on YYYY-MM-DD") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", required=True, help="个人 *.learnmed.json 路径")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("init", "upsert", "record", "due", "summary", "export-anki"):
        p = sub.add_parser(command)
        p.add_argument("--on", help="本地日期 YYYY-MM-DD；缺省按记录时区")
        if command == "init":
            p.add_argument("--timezone", default="Asia/Shanghai")
        if command in {"upsert", "record"}:
            p.add_argument("--input", required=True, help="UTF-8 JSON文件")
        if command == "due":
            p.add_argument("--minutes", type=int, required=True)
    args = parser.parse_args()
    try:
        timezone = args.timezone if args.command == "init" else read_store(args.store)["timezone"]
        on = args.on or local_today(timezone)
        day(on)
        if args.command == "init":
            result = initialize(args.store, on, timezone)
        elif args.command in {"upsert", "record"}:
            payload = json.loads(Path(args.input).read_text(encoding="utf-8-sig"))
            result = upsert(args.store, payload, on) if args.command == "upsert" else record(args.store, payload, on=on)
        elif args.command == "due":
            result = due(args.store, on, args.minutes)
        elif args.command == "summary":
            result = summary(args.store, on)
        else:
            sys.stdout.write(anki_text(read_store(args.store)))
            return 0
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, TypeError, AttributeError) as exc:
        print(f"learnmed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
