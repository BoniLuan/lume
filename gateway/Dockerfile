FROM node:24.11.0-bookworm-slim AS web-build

ENV NPM_CONFIG_UPDATE_NOTIFIER=false \
    NPM_CONFIG_FUND=false

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.31.6-alpine AS runtime

COPY gateway/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=web-build /build/dist /usr/share/nginx/html

USER 101:101
EXPOSE 8080
