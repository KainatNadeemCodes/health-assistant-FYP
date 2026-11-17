# ============================================================
# AI-Powered Smart Health Assistant — Production Frontend Dockerfile
# Multi-stage containerization with Vite build and Nginx runtime
# ============================================================

# ── Stage 1: Build the Static Bundle ─────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Copy dependency manifests first for layer caching
COPY package.json package-lock.json ./

# Clean deterministic dependency installation
RUN npm ci

# Copy application source code
COPY . .

# Accept build-time environment variable for backend API URL
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL

# Build the production bundle into /app/dist
RUN npm run build


# ── Stage 2: Serve via Lightweight Nginx ─────────────────────
FROM nginx:alpine AS runner

# Remove default nginx boilerplate site
RUN rm -rf /etc/nginx/conf.d/default.conf

# Copy custom Nginx configuration with SPA routing and gzip
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy compiled static assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q -O - http://localhost/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
