# ── Frontend – React + Vite (multi-stage) ────────────────────────────────────

# Stage 1: build
FROM node:20-alpine AS builder

WORKDIR /app

# Install deps (separate layer for better caching)
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --frozen-lockfile

# Copy source and build
COPY frontend/ ./
# VITE_API_BASE_URL is baked in at build time.
# Pass it via --build-arg or set it in .env before building.
ARG VITE_API_BASE_URL=http://localhost:5000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# Stage 2: serve with nginx
FROM nginx:1.27-alpine AS runtime

# Remove default nginx page
RUN rm -rf /usr/share/nginx/html/*

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# nginx config: single-page app routing + proxy /chat → backend
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
