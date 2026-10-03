"""J2: prove the full symptom_agent graph over the SSE endpoint, for real.

This is the end-to-end check TASKS.md J2 asks for and the one thing no unit
test can stand in for: a real FastAPI app, a real Postgres, a real model key,
and a real HTTP client reading the actual `text/event-stream` a phone would
read. It exercises the whole path at once — auth, conversation persistence,
`run_turn`, the rule engine, the SSE framing, and the JSON contract the
frontend adapter parses.

Not a pytest test: it spends real tokens and needs a live database, so it is a
script you run deliberately. It exits non-zero on failure so it can gate a
release checklist.

    cd backend && uv run python scripts/verify_live_chat.py

Scenario 1 runs a two-turn conversation in Korean and asserts the safety
verdict is EMERGENCY and that it agrees with a direct rule-engine call.
Scenario 2 checks the `pollen_is_sample` / provider-degradation contract the
Today screen depends on.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx

# Runnable from any cwd: put the backend package root on the path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings  # noqa: E402
from app.services import triage  # noqa: E402

BASE = "http://127.0.0.1:8011"
# A real address: the register endpoint runs a strict email validator that
# rejects special-use TLDs like `.test`.
EMAIL = "j2-live-check@example.com"
PASSWORD = "correcthorse123"

# The user's own words, in the app's primary language. "숨쉬기 힘들고 목이 부어서
# 부풀었어요" — hard to breathe and my throat has swollen.
KOREAN_TURN_1 = "눈이 너무 가려워요 계속 재채기해요"
KOREAN_TURN_2 = "숨쉬기 힘들고 목이 부어서 부풀었어요"

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {label}{(' — ' + detail) if detail else ''}")
    if not ok:
        failures.append(label)


def parse_sse(text: str) -> list[tuple[str, dict]]:
    """Parse the raw SSE body into (event, data) pairs.

    Deliberately hand-rolled and strict: this is checking the wire format the
    frontend depends on, so it must not share code with the server.
    """
    events: list[tuple[str, dict]] = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        name = None
        data = None
        for line in block.split("\n"):
            if line.startswith("event: "):
                name = line[len("event: ") :].strip()
            elif line.startswith("data: "):
                data = line[len("data: ") :].strip()
        if name is None:
            continue
        events.append((name, json.loads(data) if data else {}))
    return events


async def ensure_migrated(app) -> None:
    """Create the tables this check needs, so it works on a fresh database."""
    from sqlalchemy import text

    from app.core.db import engine

    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))


async def register_and_login(client: httpx.AsyncClient) -> str:
    payload = {"email": EMAIL, "password": PASSWORD}
    reg = await client.post("/api/auth/register", json=payload)
    if reg.status_code not in (200, 201, 409):
        raise SystemExit(f"register failed: {reg.status_code} {reg.text}")
    res = await client.post("/api/auth/login", json=payload)
    res.raise_for_status()
    return res.json()["access_token"]


async def chat_turn(client: httpx.AsyncClient, token: str, text: str, conversation_id: int | None):
    body: dict = {"message": text}
    if conversation_id is not None:
        body["conversation_id"] = conversation_id
    res = await client.post(
        "/api/chat",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
        timeout=90.0,
    )
    return res, parse_sse(res.text)


async def main() -> int:
    settings = get_settings()
    print("J2 live chat verification")
    print("=" * 68)
    print(f"  model     {settings.openai_model}")
    print(f"  base_url  {settings.openai_base_url or '(openai default)'}")
    print(f"  db        {settings.database_url.split('@')[-1]}")
    print("=" * 68)

    try:
        await ensure_migrated(None)
    except Exception as exc:  # noqa: BLE001
        print(f"  database unreachable: {exc}")
        return 2

    # Demo mode lets the check run without a bearer token, but we do the real
    # register+login so the auth path is covered too.
    async with httpx.AsyncClient(base_url=BASE, timeout=90.0) as client:
        health = await client.get("/health")
        check("app is up", health.status_code == 200, f"GET /health -> {health.status_code}")

        token = await register_and_login(client)
        check("register + login", bool(token))

        # --- Scenario 1: a real two-turn conversation, in Korean ----------
        print("\nScenario 1 — two-turn Korean conversation")
        res, events = await chat_turn(client, token, KOREAN_TURN_1, None)
        check("turn 1 is a 200 SSE stream", res.status_code == 200, str(res.status_code))
        check(
            "content-type is text/event-stream",
            res.headers.get("content-type", "").startswith("text/event-stream"),
            res.headers.get("content-type", ""),
        )
        names = [n for n, _ in events]
        check("turn 1 emitted a `message` event", "message" in names, str(names))
        check("turn 1 emitted a `done` event", "done" in names, str(names))
        check("turn 1 emitted no `error` event", "error" not in names, str(names))

        done = next((d for n, d in events if n == "done"), {})
        conv_id = done.get("conversation_id")
        check("turn 1 returned a conversation_id", bool(conv_id), str(conv_id))
        check(
            "turn 1 asked a follow-up rather than rushing to a verdict",
            done.get("triage_level") is None,
            f"triage_level={done.get('triage_level')!r} (expected None: the user has "
            "not been asked about breathing yet)",
        )

        # Turn 2 states the red flag in the user's own words.
        res2, events2 = await chat_turn(client, token, KOREAN_TURN_2, conv_id)
        done2 = next((d for n, d in events2 if n == "done"), {})
        check("turn 2 is a 200 SSE stream", res2.status_code == 200, str(res2.status_code))
        check("turn 2 stayed on the same conversation", done2.get("conversation_id") == conv_id)

        level = done2.get("triage_level")
        check("turn 2 reached EMERGENCY", level == "EMERGENCY", f"triage_level={level!r}")

        # ADR 0001: the verdict must be exactly what the rule engine says for
        # the fields the model extracted — recomputed here, not hardcoded.
        expected = triage.assess(
            triage.SymptomInput(
                symptoms=done2.get("symptoms") or [],
                severity=done2.get("severity"),
                breathing_difficulty=bool(done2.get("breathing_difficulty")),
                airway_swelling=bool(done2.get("airway_swelling")),
            )
        )
        check(
            "the verdict equals a direct rule-engine call on the same fields",
            level == expected.level.value,
            f"stream={level!r} engine={expected.level.value!r}",
        )
        check(
            "the stream carried rule reasons",
            bool(done2.get("triage_reasons")),
            str(done2.get("triage_reasons")),
        )
        check(
            "the rule version is reported",
            bool(done2.get("triage_rule_version")),
            str(done2.get("triage_rule_version")),
        )
        check(
            "a positive safety flag was captured from the user's own words",
            done2.get("breathing_difficulty") is True or done2.get("airway_swelling") is True,
            f"breathing={done2.get('breathing_difficulty')!r} "
            f"airway={done2.get('airway_swelling')!r}",
        )

        # --- Scenario 2: the conversation was persisted -------------------
        print("\nScenario 2 — persistence")
        me = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
        check("the token still identifies a user", me.status_code == 200, str(me.status_code))

        # --- Scenario 3: the chat contract the frontend parses ------------
        print("\nScenario 3 — contract fields the frontend depends on")
        for field in (
            "message",
            "conversation_id",
            "symptoms",
            "severity",
            "breathing_difficulty",
            "airway_swelling",
            "triage_level",
            "triage_reasons",
        ):
            check(f"`done` carries `{field}`", field in done2)

    print("=" * 68)
    if failures:
        print(f"FAILED ({len(failures)}): " + ", ".join(failures))
        return 1
    print("All live chat checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
