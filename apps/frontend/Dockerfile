# syntax=docker/dockerfile:1.7
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
    && corepack prepare pnpm@9.15.4 --activate

# Install dependencies first for better layer caching
# Supports both lockfile-present and lockfile-absent states
# Include pnpm-workspace.yaml so build approvals are honored.
COPY package.json pnpm-lock.yaml* pnpm-workspace.yaml /app/

RUN --mount=type=cache,target=/pnpm/store \
    pnpm install --prefer-offline

# Copy the rest of the frontend code
COPY . /app

EXPOSE 3000

# Next.js dev server
CMD ["pnpm", "dev"]
