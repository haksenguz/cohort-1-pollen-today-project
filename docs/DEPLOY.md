# Deploying

How to put this app on a host that the public can reach, and how to tell
whether it is actually working once it is there.

The stack is five containers in Docker Compose. Nothing in this document needs
a Kubernetes cluster, a PaaS account, or a build server.

## What runs where

| Service | Image | Reachable from |
|---|---|---|
| `edge` | caddy | the internet, on ports 80 and 443 |
| `web` | nginx + the built PWA | `edge` only |
| `api` | FastAPI | `web` only, on `/api/` |
| `db` | postgres | `api` only, on `db:5432` |
| `redis` | redis | `api` only, on `redis:6379` |

The request path is browser, then `edge` for TLS, then `web` for the PWA and
the `/api` proxy, then `api`, then the database. The database and Redis have
no published port at all, so they are not reachable from outside the network.

`edge` exists because a PWA will not install over plain HTTP. A service worker
only registers on a secure origin, and `localhost` is the one exception. A
deployment without HTTPS is a website, not an installable app.

## What you need

- A Linux host with a public IP address. Any small VPS will do.
- Docker Engine with the Compose plugin. Install it with the guide for your
  distribution: <https://docs.docker.com/engine/install/>.
- A domain, with an A record pointing at the host's public IP.
- Inbound ports 80 and 443 open. The certificate is issued over port 80.
- The provider keys. Without them the app still starts and says plainly which
  feature is off. See `.env.example` for what each one buys you.

## First deploy

### 1. Get the code

```bash
git clone https://github.com/haksenguz/cohort-1-pollen-today-project.git
cd cohort-1-pollen-today-project
git checkout feat/ismoiljon
```

### 2. Point the domain at the host

Add an A record for your domain pointing at the host's public IP. It takes a
few minutes to propagate. Do this before the next step, because the
certificate is issued against the name and a name that does not resolve yet
cannot be issued.

### 3. Write the environment file

```bash
cp .env.example .env
chmod 600 .env
openssl rand -hex 32
```

That last command prints the value for `JWT_SECRET`. It signs every session
token, so it has to be random, and it has to differ from every other
deployment. Fill in at least these four:

```
PUBLIC_ORIGIN=https://your-domain
CORS_ORIGINS=["https://your-domain"]
JWT_SECRET=<the value from openssl rand -hex 32>
POSTGRES_PASSWORD=<a password of your own>
```

`PUBLIC_ORIGIN` is the one that gets baked into the JavaScript bundle at build
time and handed to Caddy as its site address. A wrong value here shows up as a
request to the wrong origin in the browser's network tab, so it has to be
right before the build, not after.

`CORS_ORIGINS` is the same value in JSON array form. The app is served from
one origin and calls its own API, so the list has one entry.

### 4. Build and start

```bash
docker compose up -d --build
docker compose ps
```

The first build pulls the base images and compiles the frontend, so it takes a
few minutes. Later builds reuse the layer cache.

Watch the edge obtain its certificate:

```bash
docker compose logs -f edge
```

Caddy asks Let's Encrypt for a certificate on the first start. It retries in
the background until it succeeds, so a DNS record that is not live yet resolves
itself without any action from you.

### 5. Check that it is up

```bash
curl -sS https://your-domain/health
```

The answer is `{"status":"ok","service":"allergy-ai-backend"}`. Then open the
site in a browser and register an account.

## Verify the deployment

The unit suite proves the code is correct. It does not prove the deployment
is. These two checks run against the live instance, through TLS and the edge,
and they fail loudly.

```bash
docker compose exec -e VERIFY_BASE_URL=https://your-domain api \
  python scripts/verify_live_chat.py
```

It registers an account, holds a two-turn Korean conversation, and asserts
that the second turn reaches `EMERGENCY` and that the verdict equals a direct
call to the rule engine on the same fields. It spends real tokens and writes a
test account, so it is a deliberate step, not part of every deploy.

```bash
docker compose exec api python scripts/verify_live_pollen.py
```

It calls KMA with the configured key and prints what the provider actually
answered. Seasons matter when reading the result: tree pollen is served from
March to June and weeds from August to October, so a run in January correctly
returns nothing.

## Updating

```bash
git pull
docker compose up -d --build
```

The API container runs `alembic upgrade head` on boot, so the schema follows
the code. It is a no-op once the database is at head.

## Backing up

The database lives in a Docker volume, and a volume on one disk is not a
backup. Dump it:

```bash
mkdir -p /srv/backups
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
  > /srv/backups/allergy-$(date +%F).dump
```

Daily at 03:00, keeping two weeks. Put this in the root crontab with `crontab
-e`, and note the escaped percent signs, which crontab otherwise reads as
end of line:

```
0 3 * * * cd /srv/allergy-ai && docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > /srv/backups/allergy-$(date +\%F).dump && find /srv/backups -name 'allergy-*.dump' -mtime +14 -delete
```

Copy the dumps off the host as well. A backup on the machine it protects is
one disk failure away from nothing.

## Restoring

Stop the API first, so nothing writes while the dump is going in.

```bash
docker compose stop api
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' \
  < /srv/backups/allergy-2026-10-28.dump
docker compose start api
```

## Rolling back

To go back to an earlier version of the code:

```bash
git log --oneline -5
git checkout <the-sha-you-want>
docker compose up -d --build
```

This does not roll the database back. The schema moves forward and stays
there. To undo a schema change, restore a dump.

## Rotating secrets

Everything secret lives in `.env` on the server, and nowhere else.

```bash
vim .env
docker compose up -d api
```

Rotating `JWT_SECRET` signs every existing session token out. Users log in
again, and nothing else changes.

Rotating a provider key takes effect the same way. The LLM key and the base
URL have to come from the same provider: a key pointed at the wrong host
answers `401` with a body that reads "Missing Authentication header" even
while the SDK is sending the header correctly, so it looks like a missing
credential rather than a mismatched host.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `docker compose up` exits with `set POSTGRES_USER` | `.env` is missing or incomplete | `cp .env.example .env` and fill in every required value |
| The `api` container restarts in a loop, the log says `Refusing to start in production mode` | `JWT_SECRET` is the example value or shorter than 32 characters | `openssl rand -hex 32`, put it in `.env`, restart |
| The chat answers with a canned breathing question | `OPENAI_BASE_URL` does not match the provider that issued the key | set the base URL for that provider and restart `api` |
| The site loads but the answer appears all at once | something between the browser and the API is buffering the event stream | `edge` needs `flush_interval -1` and nginx needs `proxy_buffering off` for `/api/` |
| The PWA will not install | the site is not served over HTTPS, or the browser is holding an old service worker | a secure origin is required, then hard reload |
| `Pollen: Unavailable` | no key, out of season, or the provider contract moved | `docker compose exec api python scripts/verify_live_pollen.py` prints the provider's own answer |
| The API answers a CORS error in the browser | `CORS_ORIGINS` does not match the origin the page was served from | set it to the public origin and restart `api` |
| Every user shares one rate limit bucket | the client IP is not reaching the API | nginx must forward `X-Forwarded-For` |
| `429` on the chat | the per-user limit, 20 turns a minute by default | raise `CHAT_RATE_LIMIT_PER_MINUTE` in `.env` |

## Known limits

- **One instance.** The chat rate limiter counts per process and in memory, so
  two replicas would each allow the full limit, and a restart clears it. The
  migration step is not safe from several replicas at once either. One host,
  one `api` container, for now.
- **No alert delivery.** The pipeline generates and stores alerts and sends
  nothing, so a high pollen alert reaches the user only when they open the
  Alerts tab. That is tracked as B-010.
- **The database is one volume.** No replication, no failover, no point in time
  recovery. The dump in the backup section is the whole recovery story.
- **The policy is a draft.** `GET /api/privacy/policy` returns
  `requires_legal_review: true`, because it was written from the code and not
  by a lawyer. Publishing it as-is is fine for a demo and not fine for a
  public service.
