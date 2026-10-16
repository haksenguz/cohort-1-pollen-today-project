"""Live check: prove POST /api/chat really returns 429 over HTTP.

Not a pytest test — it needs a running server. Run the server with
CHAT_RATE_LIMIT_PER_MINUTE=3, then:

    cd backend && uv run python scripts/verify_rate_limit.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = "http://127.0.0.1:8012"
EMAIL = "ratelimit-live@example.com"
PASSWORD = "correcthorse123"

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{(' — ' + detail) if detail else ''}")
    if not ok:
        failures.append(label)


async def main() -> int:
    print("Live rate-limit verification")
    print("=" * 68)
    async with httpx.AsyncClient(base_url=BASE, timeout=30.0) as client:
        payload = {"email": EMAIL, "password": PASSWORD}
        await client.post("/api/auth/register", json=payload)
        res = await client.post("/api/auth/login", json=payload)
        res.raise_for_status()
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        check("logged in", bool(token))

        # A nonexistent conversation id: the request is refused by the 404
        # branch, but only *after* the limiter has been consulted, so this
        # exercises the limiter without needing a real model call.
        codes: list[int] = []
        retry_after: str | None = None
        limit_header: str | None = None
        for _ in range(6):
            r = await client.post(
                "/api/chat", json={"message": "hi", "conversation_id": 999_999}, headers=headers
            )
            codes.append(r.status_code)
            if r.status_code == 429:
                retry_after = r.headers.get("retry-after")
                limit_header = r.headers.get("x-ratelimit-limit")
                body = r.json()
                check(
                    "the 429 detail tells the user what to do",
                    "too quickly" in str(body.get("detail", "")),
                    str(body.get("detail")),
                )
                check("the 429 is JSON, not an SSE event", "text/event-stream" not in r.headers.get("content-type", ""))

        print(f"  codes: {codes}")
        check("some early requests passed the limiter", 404 in codes, str(codes))
        check("a later request was refused with 429", 429 in codes, str(codes))
        check(
            "the limiter bites at the configured point, not immediately",
            codes.count(404) >= 2,
            f"expected at least 2 admitted before refusal, got {codes.count(404)}",
        )
        check("Retry-After is present and numeric", bool(retry_after) and retry_after.isdigit(), str(retry_after))
        check("X-RateLimit-Limit is present", limit_header == "3", str(limit_header))

        # A second user must be unaffected.
        other = {"email": "ratelimit-other@example.com", "password": PASSWORD}
        await client.post("/api/auth/register", json=other)
        r2 = await client.post("/api/auth/login", json=other)
        other_token = r2.json()["access_token"]
        r3 = await client.post(
            "/api/chat",
            json={"message": "hi", "conversation_id": 999_999},
            headers={"Authorization": f"Bearer {other_token}"},
        )
        check("a different user is not locked out", r3.status_code == 404, f"got {r3.status_code}")

    print("=" * 68)
    if failures:
        print(f"FAILED ({len(failures)}): " + ", ".join(failures))
        return 1
    print("Live rate-limit checks passed.")
    return 0


if __name__ == "__main__":
    print(json.dumps({"note": "run the server with CHAT_RATE_LIMIT_PER_MINUTE=3"}))
    sys.exit(asyncio.run(main()))
