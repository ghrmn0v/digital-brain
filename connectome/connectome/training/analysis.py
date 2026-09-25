from typing import Any, Dict, List, Optional

from connectome.store import SqliteStore

POSITIVE = {"looked", "interacted", "opened_related", "marked_useful", "reacted_positive"}
NEGATIVE = {"dismissed", "marked_unnecessary", "reacted_negative"}


def recent_reward_rate(store: SqliteStore, window: int = 50) -> Optional[float]:
    feedback = store.feedback_rows()[-window:]
    if not feedback:
        return None
    total = sum(1.0 for row in feedback if row["reward_value"] > 0)
    return total / len(feedback)


def feedback_distribution(store: SqliteStore) -> Dict[str, int]:
    rows = store.feedback_rows()
    distribution: Dict[str, int] = {}
    for row in rows:
        kind = row["feedback"]
        distribution[kind] = distribution.get(kind, 0) + 1
    return distribution


def policy_agreement(store: SqliteStore) -> Optional[float]:
    decisions = store.decisions()
    feedback = store.feedback_rows()
    if not decisions or not feedback:
        return None
    by_behavior = {row["behavior_id"]: row for row in feedback}
    aligned = 0
    total = 0
    for decision in decisions:
        fb = by_behavior.get(decision["behavior_id"])
        if not fb:
            continue
        total += 1
        if fb["reward_value"] > 0:
            aligned += 1
    if total == 0:
        return None
    return aligned / total


def analyze(store: SqliteStore, window: int = 50) -> Dict[str, Any]:
    counts = store.counts()
    return {
        "decisions": counts["decisions"],
        "feedback_events": counts["feedback"],
        "reward_rate": recent_reward_rate(store, window),
        "policy_agreement": policy_agreement(store),
        "distribution": feedback_distribution(store),
    }


def main() -> None:
    import json
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else None
    store = SqliteStore(path)
    print(json.dumps(analyze(store), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()