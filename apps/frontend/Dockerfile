# apps/frontend/Dockerfile
#
# Minimal Next.js frontend container (dev-first).
# Production build can be added later with a multi-stage build.

FROM node:20-slim

# Keep npm quiet and predictable
ENV NODE_ENV=development \
    NPM_CONFIG_LOGLEVEL=warn

WORKDIR /app

# Install dependencies first for better layer caching
COPY apps/frontend/package.json apps/frontend/package-lock.json* /app/

RUN npm install

# Copy the rest of the frontend code
COPY apps/frontend /app

EXPOSE 3000

# Dev server
CMD ["npm", "run", "dev"]
