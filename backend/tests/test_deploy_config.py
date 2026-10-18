"""Deploy configuration must be asserted, not annotated.

Every one of these settings fails *silently*. Remove `proxy_buffering off` and
the app does not error, does not crash, and does not log anything — it simply
streams the whole answer at once at the end, which looks like a slow model. The
only artefact of that mistake is a comment saying the line matters, and a
comment does not fail a build.

So the assertions here are written to fail when a line goes missing, which rules
out two easy ways to write them badly:

- **Grepping the whole file.** `proxy_buffering off` appearing anywhere would
  pass, including in a comment, or in a block that no longer serves `/api/`.
  Comments are stripped and directives are located inside the specific
  `location` block that needs them.
- **Checking a value's presence but not its value.** `proxy_buffering on` also
  contains the word `proxy_buffering`. Each directive is asserted as a pair.

Deliberately a backend test, not a frontend one: the frontend gate cannot fail
on this, and a deploy invariant that only one lane's gate can see is one commit
away from being wrong.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
NGINX = REPO / "frontend" / "nginx.conf"
COMPOSE = REPO / "docker-compose.yml"
FRONTEND_DOCKERFILE = REPO / "frontend" / "Dockerfile"
BACKEND_DOCKERFILE = BACKEND / "Dockerfile"

_LOCATION = re.compile(r"location\s+(?:=\s*)?([^\s{]+)\s*\{")


def _without_comments(text: str) -> str:
    """Drop `#` comments.

    This is the whole point of the module. A commented-out directive is a
    directive that does nothing, and without this step it would satisfy every
    assertion below.
    """
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def _locations(text: str) -> dict[str, str]:
    """`location <selector>` -> its body, by brace matching.

    Braces rather than a regex, because a location block can contain nested
    blocks and the naive version silently truncates at the first `}`.
    """
    found: dict[str, str] = {}
    for match in _LOCATION.finditer(text):
        start = match.end()
        depth = 1
        index = start
        while index < len(text) and depth:
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
            index += 1
        found[match.group(1)] = text[start : index - 1]
    return found


def _directives(body: str) -> dict[str, str]:
    """Directive name -> value, for a single location body."""
    out: dict[str, str] = {}
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        name, _, value = stripped.partition(" ")
        out.setdefault(name, value.strip())
    return out


@pytest.fixture(scope="module")
def nginx_text() -> str:
    return _without_comments(NGINX.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def nginx_locations(nginx_text: str) -> dict[str, str]:
    return _locations(nginx_text)


# --- the SSE block --------------------------------------------------------


def test_api_location_exists(nginx_locations: dict[str, str]) -> None:
    assert "/api/" in nginx_locations, "no location /api/ block found to check"


@pytest.mark.parametrize(
    ("directive", "value"),
    [
        # nginx buffers proxied responses by default, and a buffered SSE stream
        # is not SSE: the client gets nothing, then gets all of it at once.
        ("proxy_buffering", "off;"),
        # A cache in front of an event stream replays a stale turn.
        ("proxy_cache", "off;"),
        # gzip re-buffers what proxy_buffering off just released. Keeping both
        # looks like belt-and-braces and silently undoes the first one.
        ("gzip", "off;"),
        ("chunked_transfer_encoding", "on;"),
        ("proxy_http_version", "1.1;"),
    ],
    ids=["buffering", "cache", "gzip", "chunked", "http-version"],
)
def test_api_location_disables_sse_hostile_defaults(
    nginx_locations: dict[str, str], directive: str, value: str
) -> None:
    body = _directives(nginx_locations["/api/"])
    assert body.get(directive) == value, (
        f"location /api/ needs `{directive} {value}` for server-sent events to "
        f"stream; found {body.get(directive)!r}"
    )


def test_api_location_does_not_keep_the_connection_alive(nginx_locations: dict[str, str]) -> None:
    """`Connection ""` clears the header; `keep-alive` would not.

    An SSE connection is meant to be long-lived. Proxying it with an explicit
    keep-alive makes nginx and the upstream negotiate a connection neither wants.
    """
    block = nginx_locations["/api/"]
    assert re.search(r'proxy_set_header\s+Connection\s+""\s*;', block), (
        'location /api/ needs `proxy_set_header Connection "";` for a long-lived stream'
    )


def test_api_location_forwards_the_client_ip(nginx_locations: dict[str, str]) -> None:
    """The rate limiter keys on the client IP.

    Behind nginx, without X-Forwarded-For, every request appears to come from
    the proxy and shares one bucket — so one user can rate-limit everyone. It
    does not error; it just throttles the whole userbase at once.
    """
    block = nginx_locations["/api/"]
    assert re.search(r"proxy_set_header\s+X-Forwarded-For\s+\$proxy_add_x_forwarded_for", block), (
        "location /api/ must forward X-Forwarded-For or the rate limiter sees one IP"
    )
    assert re.search(r"proxy_set_header\s+X-Forwarded-Proto\s+\$scheme", block)


# --- caching --------------------------------------------------------------


@pytest.mark.parametrize("location", ["/assets/", "/fonts/"])
def test_hashed_assets_are_cached_hard(nginx_locations: dict[str, str], location: str) -> None:
    """Filenames are content-hashed, so a year is safe."""
    body = _directives(nginx_locations[location])
    assert body.get("expires") == "1y;", f"{location} should cache its hashed files for a year"
    assert "immutable" in body.get("add_header", ""), (
        f"{location} should be immutable - the filename changes when the bytes do"
    )


@pytest.mark.parametrize("location", ["/index.html", "/sw.js"])
def test_shell_and_service_worker_are_never_cached(
    nginx_locations: dict[str, str], location: str
) -> None:
    """A cached shell or worker keeps booting the previous build, and the PWA
    update prompt never fires because it never sees a new worker."""
    body = _directives(nginx_locations[location])
    assert "no-cache" in body.get("add_header", ""), f"{location} must not be cached"


def test_manifest_is_not_cached(nginx_locations: dict[str, str]) -> None:
    body = _directives(nginx_locations["/manifest.webmanifest"])
    assert "no-cache" in body.get("add_header", "")


# --- server level ---------------------------------------------------------


def test_server_tokens_are_off(nginx_text: str) -> None:
    assert re.search(r"^\s*server_tokens\s+off\s*;", nginx_text, re.M)


def test_long_streaming_timeouts_are_set(nginx_text: str) -> None:
    """The default 60s read timeout cuts a long turn off mid-answer."""
    for directive in ("proxy_read_timeout", "proxy_send_timeout", "send_timeout"):
        match = re.search(rf"{directive}\s+(\d+)s\s*;", nginx_text)
        assert match, f"{directive} is not set"
        assert int(match.group(1)) >= 3600, f"{directive} too low for a long turn"


# --- compose --------------------------------------------------------------


@pytest.fixture(scope="module")
def compose() -> dict[str, str]:
    import yaml

    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


@pytest.mark.parametrize("service", ["db", "redis", "api"])
def test_internal_services_publish_no_host_ports(compose: dict, service: str) -> None:
    """A mapped 5432 or 6379 on a public host is an open database and an open
    Redis. Nothing warns about it; the stack starts happily and is exploitable.
    """
    assert "ports" not in compose["services"][service], (
        f"{service} must not publish a host port; it is reachable on the internal network"
    )


def test_only_web_is_published(compose: dict) -> None:
    published = [name for name, cfg in compose["services"].items() if "ports" in cfg]
    assert published == ["web"], f"unexpected published services: {published}"


def test_db_credentials_are_required_but_provider_keys_are_not(compose: dict) -> None:
    """`:?` means "fail loudly if absent" — right for a password, wrong for an
    optional key. An absent LLM key must degrade honestly, not stop the deploy.
    """
    db_env = compose["services"]["db"]["environment"]
    assert db_env["POSTGRES_PASSWORD"].startswith("${POSTGRES_PASSWORD:?")

    api_env = compose["services"]["api"]["environment"]
    for optional in ("OPENAI_API_KEY", "POLLEN_API_KEY", "NAVER_CLIENT_ID"):
        assert ":?" not in api_env[optional], (
            f"{optional} must degrade when absent, not fail the container"
        )


# --- images ---------------------------------------------------------------


def test_backend_runs_migrations_before_serving() -> None:
    """`init_db()` uses create_all, which does not alter existing tables, so the
    migration step is the only thing that brings a live database up to date."""
    text = BACKEND_DOCKERFILE.read_text(encoding="utf-8")
    assert 'CMD ["./entrypoint.sh"]' in text
    assert "alembic upgrade head" in (BACKEND / "entrypoint.sh").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "path",
    [
        # A CRLF shell script fails with '\r: not found' on the first line, and
        # the container dies at CMD with a message that names neither the file
        # nor the cause.
        BACKEND / "entrypoint.sh",
        # nginx does not strip \r, so a directive ends up as 'off;' plus a
        # carriage return and the config is rejected at startup.
        NGINX,
        # Both images use backslash line continuations, where a trailing \r is
        # part of the joined command rather than whitespace.
        BACKEND_DOCKERFILE,
        FRONTEND_DOCKERFILE,
    ],
    ids=["entrypoint.sh", "nginx.conf", "backend/Dockerfile", "frontend/Dockerfile"],
)
def test_files_that_ship_into_a_container_are_lf_only(path: Path) -> None:
    """The build cannot see this: git happily stores CRLF, and the failure only
    appears on a machine that did not author the file.

    This is not hypothetical. A mutation harness that read and rewrote these
    files with Python's default text mode converted nginx.conf to CRLF, and the
    working tree looked clean the whole time because git normalises line endings
    when diffing. `.gitattributes` stops it recurring; this asserts it anyway,
    because .gitattributes only governs what git checks *out* — a file already in
    the tree stays however it is.
    """
    raw = path.read_bytes()
    assert b"\r" not in raw, (
        f"{path.name} contains CR bytes; it must be LF-only or it will not work "
        "inside the container"
    )


def test_frontend_image_requires_an_absolute_api_base() -> None:
    """`new URL(path, API_BASE_URL)` throws at runtime on "" or "/", and it
    throws in the browser, not at build time. The build has to refuse instead."""
    text = FRONTEND_DOCKERFILE.read_text(encoding="utf-8")
    assert "ARG VITE_API_BASE_URL" in text
    assert re.search(r'test\s+-n\s+"\$VITE_API_BASE_URL"', text), (
        "the build must fail when VITE_API_BASE_URL is missing"
    )


def test_frontend_healthcheck_does_not_run_the_server_forever() -> None:
    """`nginx -g "daemon off;"` is the container's job, not the probe's.

    As a healthcheck it starts a second foreground nginx that never exits, so
    every probe times out and the container is marked unhealthy forever — which
    is indistinguishable, to anything waiting on `service_healthy`, from the
    container being broken.
    """
    text = FRONTEND_DOCKERFILE.read_text(encoding="utf-8")
    healthcheck = re.search(r"HEALTHCHECK(.*?)(?=\n\n|\nCMD|\Z)", text, re.S)
    assert healthcheck, "no HEALTHCHECK in frontend/Dockerfile"
    body = healthcheck.group(1)
    assert "daemon off" not in body, (
        "the healthcheck must probe over HTTP, not start the server in the foreground"
    )
    assert "wget" in body or "curl" in body or "nginx -t" in body
