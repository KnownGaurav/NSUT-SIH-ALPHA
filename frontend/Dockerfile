# ==============================================================================
# Production Dockerfile for Railway ETA React Frontend
# Multi-stage build: Node.js Vite compiler -> Lightweight Nginx Web Server
# ==============================================================================

# Stage 1: Build production bundle
FROM node:20-alpine AS build

WORKDIR /app

# Copy dependency manifests and install packages
COPY package.json package-lock.json ./
RUN npm ci

# Copy frontend source code and compile
COPY . .
RUN npm run build

# Stage 2: Serve compiled assets with Nginx
FROM nginx:alpine

# Copy custom Nginx reverse proxy configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy production static build artifacts
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
