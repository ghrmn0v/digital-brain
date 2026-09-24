"""Training dataset builder: turns the live persistence store into offline-ready labeled data.

Every recorded decision becomes one record, joined to its user feedback through
behavior_id (kept canonical end-to-end since the behaviorId == event id fix). The
flat CSV / JSONL output feeds the Phase 5/6/7 training pipelines so the fly can be
trained on real interaction data, not toy scenarios.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from connectome.event_processor import KNOWN_EVENTS, KNOWN_SOURCES
from connectome.policy import PRIORITY_LEVEL
from connectome.state_machine import states
from connectome.store import SqliteStore

LABEL_POSITIVE = "positive"
LABEL_NEGATIVE = "negative"
LABEL_NEUTRAL = "neutral"
LABEL_UNLABELED = "unlabeled"

EVENT_CODES: Dict[str, int] = {name: i for i, name in enumerate(sorted(KNOWN_EVENTS))}
SOURCE_CODES: Dict[str, int] = {name: i for i, name in enumerate(sorted(KNOWN_SOURCES))}
PRIORITY_LEVEL_CODES: Dict[str, int] = {
    name: i for i, name in enumerate(sorted(set(PRIORITY_LEVEL.values())))}
STATE_CODES: Dict[str, int] = {name: i for i, name in enumerate(states)}
UNKNOWN = -1


def code(field: str, table: Dict[str, int]) -> int:
    return table.get(field, UNKNOWN)


def label_for(reward: Optional[float]) -> str:
    if reward is None:
        return LABEL_UNLABELED
    if reward > 0:
        return LABEL_POSITIVE
    if reward < 0:
        return LABEL_NEGATIVE
    return LABEL_NEUTRAL


def build_dataset(store: SqliteStore, limit: int | None = None) -> Dict[str, Any]:
    feedback_index: Dict[str, Dict[str, Any]] = {}
    for fb in store.feedback_rows():
        current = feedback_index.get(fb["behavior_id"])
        if current is None or current["created_at"] <= fb["created_at"]:
            feedback_index[fb["behavior_id"]] = fb

    records: List[Dict[str, Any]] = []
    for decision in store.decisions(limit or 100000):
        behavior_id = decision["behavior_id"]
        linked = feedback_index.get(behavior_id)
        reward = linked["reward_value"] if linked else None
        records.append({
            "behavior_id": behavior_id,
            "event": decision["event"],
            "event_code": code(decision["event"], EVENT_CODES),
            "source": decision["source"],
            "source_code": code(decision["source"], SOURCE_CODES),
            "priority": decision["priority"],
            "priority_level": decision["priority_level"],
            "priority_level_code": code(decision["priority_level"], PRIORITY_LEVEL_CODES),
            "state": decision["state"],
            "state_code": code(decision["state"], STATE_CODES),
            "confidence": decision["confidence"],
            "reward_value": reward,
            "feedback": linked["feedback"] if linked else None,
            "label": label_for(reward),
            "created_at": decision["created_at"],
        })

    labeled = [r for r in records if r["label"] != LABEL_UNLABELED]
    stats = {
        "decisions": len(records),
        "labeled": len(labeled),
        "unlabeled": len(records) - len(labeled),
        "linkage_rate": round((len(labeled) / len(records)) * 100, 2) if records else 0.0,
        "positive": sum(1 for r in labeled if r["label"] == LABEL_POSITIVE),
        "negative": sum(1 for r in labeled if r["label"] == LABEL_NEGATIVE),
        "neutral": sum(1 for r in labeled if r["label"] == LABEL_NEUTRAL),
        "feedback_rows_total": len(store.feedback_rows()),
    }
    return {"records": records, "stats": stats, "codes": {
        "events": EVENT_CODES, "sources": SOURCE_CODES,
        "priority_levels": PRIORITY_LEVEL_CODES, "states": STATE_CODES,
    }}


def write_dataset(dataset: Dict[str, Any], out_dir: Path) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    records = dataset["records"]
    columns = list(records[0].keys()) if records else list(dataset["codes"].keys())

    csv_path = out_dir / "train_decisions.csv"
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(records)

    jsonl_path = out_dir / "train_decisions.jsonl"
    with jsonl_path.open("w") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    metas = out_dir / "dataset_meta.json"
    metas.write_text(json.dumps(
        {"stats": dataset["stats"], "codes": dataset["codes"]}, indent=2, ensure_ascii=False))

    return [csv_path, jsonl_path, metas]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build labeled training dataset from the learning store")
    parser.add_argument("--db", default=None, help="sqlite path (default: FLY_DB or ~/.fly/connectome.db)")
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "datasets")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)

    db_path = args.db or os.environ.get("FLY_DB") or str(Path.home() / ".fly" / "connectome.db")
    store = SqliteStore(db_path)
    try:
        dataset = build_dataset(store, limit=args.limit)
        written = write_dataset(dataset, args.out)
    finally:
        store.close()

    stats = dataset["stats"]
    print(f"decisions: {stats['decisions']}  labeled: {stats['labeled']} "
          f"({stats['linkage_rate']}%)  +{stats['positive']}/-{stats['negative']}/0{stats['neutral']}")
    for path in written:
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())