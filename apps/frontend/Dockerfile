# apps/frontend/Dockerfile
#
# Minimal Next.js frontend container using pnpm (dev-first).
# Production build should be a separate multi-stage Dockerfile.

FROM node:20-slim

# Environment sanity
ENV NODE_ENV=development \
    PNPM_HOME=/pnpm \
    PATH=/pnpm:$PATH

WORKDIR /app

# Enable pnpm via Corepack (bundled with Node 20)
RUN corepack enable \
    && corepack prepare pnpm@latest --activate

# Install dependencies first for better layer caching
# Supports both lockfile-present and lockfile-absent states
COPY apps/frontend/package.json apps/frontend/pnpm-lock.yaml* /app/

RUN pnpm install

# Copy the rest of the frontend code
COPY apps/frontend /app

EXPOSE 3000

# Next.js dev server
CMD ["pnpm", "dev"]
