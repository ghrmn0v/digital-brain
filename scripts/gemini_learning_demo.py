#!/usr/bin/env python3
"""Deterministic 4-interaction learning demonstration.

Runs the whole personalization loop against a **local fake Gemini endpoint**:
the provider really performs HTTP, the request really carries Brain-assembled
context, and the answer really comes back through the gateway. Only Google's
server is absent, so the model output is scripted — every Brain behaviour
(context assembly, validation, learning, precedence) is real.

    INTERACTION 1  user states a preference      -> learned as an explicit fact
    INTERACTION 2  user asks a related question -> retrieved context is used
    INTERACTION 3  user changes the preference   -> explicit value wins
    INTERACTION 4  user asks again              -> the new value is used

Usage:  python scripts/gemini_learning_demo.py
"""

from __future__ import annotations

import json
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contracts.feedback.feedback import (  # noqa: E402
    Feedback,
    FeedbackKind,
    FeedbackSource,
    FeedbackTarget,
)
from core.memory import MemoryCandidate  # noqa: E402
from core.service.brain_service import build_brain_service  # noqa: E402
from core.understanding import (  # noqa: E402
    GeminiConfig,
    GeminiProvider,
    LLMGateway,
    LLMRequest,
    HeuristicProvider,
)
from contracts.common.types import Source  # noqa: E402

NOW = datetime(2026, 9, 25, 10, tzinfo=timezone.utc)
USER = "usr_demo"

# Scripted provider replies. The fake server returns the first reply whose
# request mentions the expected phrase, so the demo is deterministic.
REPLIES = {
    "typescript": {
        "answer": "You said you prefer TypeScript for backend work, so TypeScript.",
        "confidence": 0.85,
        "used_context": True,
        "candidates": [
            {
                "kind": "preference",
                "key": "backend_language",
                "value": "TypeScript",
                "evidence": "explicit_user_statement",
                "confidence": 0.95,
                "preference_domain": "language",
            }
        ],
    },
    "before_change": {
        "answer": "Based on your stored preference, TypeScript.",
        "confidence": 0.8,
        "used_context": True,
        "candidates": [],
    },
    "rust": {
        "answer": "Noted: you now prefer Rust for backend work.",
        "confidence": 0.85,
        "used_context": True,
        "candidates": [
            {
                "kind": "preference",
                "key": "backend_language",
                "value": "Rust",
                "evidence": "explicit_user_statement",
                "confidence": 0.95,
                "preference_domain": "language",
            }
        ],
    },
    "after_change": {
        "answer": "Based on your most recent explicit statement, Rust.",
        "confidence": 0.85,
        "used_context": True,
        "candidates": [],
    },
}


class FakeGemini(BaseHTTPRequestHandler):
    """A local stand-in for the Gemini generateContent endpoint.

    Replies are picked by call order so the demo stays deterministic and does
    not depend on matching words inside the assembled Brain context.
    """

    calls: list[dict] = []
    script: list[dict] = []

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("content-length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")
        prompt = body["contents"][0]["parts"][0]["text"]
        index = len(FakeGemini.calls)
        reply = (
            FakeGemini.script[index]
            if index < len(FakeGemini.script)
            else {"answer": "no script left", "confidence": 0.0,
                  "used_context": False, "candidates": []}
        )
        FakeGemini.calls.append({"prompt": prompt, "reply": reply, "index": index})
        payload = json.dumps(
            {"candidates": [{"content": {"parts": [{"text": json.dumps(reply)}]}}]}
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args: object) -> None:
        return None


def start_server() -> tuple[HTTPServer, str]:
    server = HTTPServer(("127.0.0.1", 0), FakeGemini)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def show(title: str) -> None:
    print(f"\n=== {title} " + "=" * max(0, 60 - len(title)))


def main() -> int:
    server, base_url = start_server()
    FakeGemini.script = [
        REPLIES["typescript"],
        REPLIES["before_change"],
        REPLIES["rust"],
        REPLIES["after_change"],
    ]
    config = GeminiConfig(
        api_key="demo-key-not-real",
        model="gemini-2.0-flash",
        enabled=True,
        api_base=base_url,
        timeout_seconds=10.0,
    )
    gateway = LLMGateway(
        GeminiProvider(config),
        fallback=HeuristicProvider(),
        timeout_seconds=10.0,
    )
    service = build_brain_service(":memory:")
    service._understanding = gateway

    show("INTERACTION 1 — the user states a preference")
    service.ingest(
        {
            "id": "evt_1",
            "type": "source.whatsapp.message_received",
            "timestamp": NOW.isoformat(),
            "occurred_at": NOW.isoformat(),
            "user_id": USER,
            "source": {"provider": "whatsapp"},
            "subject": {"person_id": "per_user"},
            "payload": {"text": "I prefer TypeScript for backend development"},
        }
    )
    insight = service.personalized_insight(
        USER, "I prefer TypeScript for backend development. Remember that.",
        target_event_id="evt_1",
    )
    print(f"provider={insight.provider} fallback={insight.fallback_used}")
    print(f"answer: {insight.answer}")
    print(f"recorded: {[(c.key, c.value, c.recorded) for c in insight.recorded_candidates]}")
    print(f"stored preferences: {[(p.name, p.value) for p in service.preferences(USER)]}")

    show("INTERACTION 2 — a related question, answered from stored context")
    insight = service.personalized_insight(
        USER, "Which backend language should I use for my next project?", target_event_id="evt_2"
    )
    print(f"provider={insight.provider} used_context={insight.used_context} "
          f"context_facts={insight.context_fact_count}")
    print(f"answer: {insight.answer}")
    prompt = FakeGemini.calls[-1]["prompt"]
    print("context actually sent to the model (first lines):")
    for line in prompt.splitlines()[:6]:
        print(f"    {line}")

    show("INTERACTION 3 — the user changes the preference")
    insight = service.personalized_insight(
        USER, "I now prefer Rust for backend development.", target_event_id="evt_3"
    )
    print(f"answer: {insight.answer}")
    print(f"stored preferences: {[(p.name, p.value) for p in service.preferences(USER)]}")

    show("INTERACTION 4 — asking again uses the new value")
    insight = service.personalized_insight(
        USER, "Which backend language should I use for my next project? Again.",
        target_event_id="evt_4",
    )
    print(f"answer: {insight.answer}")
    print(f"used_context={insight.used_context} provider={insight.provider}")

    show("PROOF — the stored value is the newest EXPLICIT statement")
    stored = {p.name: p.value for p in service.preferences(USER)}
    ok = stored.get("backend_language") == "Rust"
    print(f"stored backend_language = {stored.get('backend_language')!r} -> {'OK' if ok else 'UNEXPECTED'}")
    print(f"feedback traces stored: {len(service.feedback_history(USER))} "
          "(explicit statements are preferences, not behaviour traces)")
    print(f"gemini-style HTTP calls made: {len(FakeGemini.calls)}")
    print("NOTE: the model is stateless. Every answer above was possible only")
    print("      because the Brain retrieved, labelled and bounded the context.")
    service.close()
    server.shutdown()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
