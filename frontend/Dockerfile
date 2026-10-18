# syntax=docker/dockerfile:1

# ---- build ----------------------------------------------------------------
FROM node:22-slim AS build
WORKDIR /app

# pnpm via corepack, pinned by the lockfile. Dependencies install before the
# source is copied so a code edit does not re-resolve the tree.
COPY package.json pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile

COPY . .

# The API base is baked into the bundle at build time - it is not read at
# runtime. `new URL(path, API_BASE_URL)` in src/api/client.ts needs an absolute
# origin, so this is the public site URL, e.g. https://allergy.example.com and
# NOT "/" or "". nginx proxies /api through to the backend, so same-origin.
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN test -n "$VITE_API_BASE_URL" || (echo "VITE_API_BASE_URL build arg is required" && exit 1)

RUN pnpm build

# ---- serve ----------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

# Probe over HTTP rather than running the CMD: `nginx -g "daemon off;"` starts a
# second foreground nginx that never exits, so every probe would time out and the
# container would sit permanently unhealthy. /health is proxied to the API, so
# this also reports whether the stack can actually serve a request.
HEALTHCHECK --interval=30s --timeout=4s --start-period=5s --retries=3 \
    CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1/health"]
CMD ["nginx", "-g", "daemon off;"]