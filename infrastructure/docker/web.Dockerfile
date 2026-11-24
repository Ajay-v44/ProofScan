FROM node:22-bookworm-slim AS build
WORKDIR /srv/proofscan
COPY package.json package-lock.json ./
COPY apps/web/package.json ./apps/web/package.json
COPY apps/desktop/package.json ./apps/desktop/package.json
COPY apps/mobile/package.json ./apps/mobile/package.json
COPY packages/api-client/package.json ./packages/api-client/package.json
COPY packages/design-tokens/package.json ./packages/design-tokens/package.json
RUN npm ci --workspace @proofscan/web --workspace @proofscan/api-client --workspace @proofscan/design-tokens --include-workspace-root --no-audit
COPY apps/web ./apps/web
COPY packages/api-client ./packages/api-client
COPY packages/design-tokens ./packages/design-tokens
ARG API_INTERNAL_ORIGIN=http://api:8000
ARG PROOFSCAN_SITE_URL
ARG PROOFSCAN_WINDOWS_DOWNLOAD_URL
ARG PROOFSCAN_MACOS_DOWNLOAD_URL
ARG PROOFSCAN_ANDROID_DOWNLOAD_URL
ARG PROOFSCAN_IOS_DOWNLOAD_URL
ENV API_INTERNAL_ORIGIN=$API_INTERNAL_ORIGIN NEXT_TELEMETRY_DISABLED=1
RUN npm run build -w @proofscan/web

FROM node:22-bookworm-slim
WORKDIR /srv/proofscan
COPY --from=build --chown=node:node /srv/proofscan/apps/web/.next/standalone ./
COPY --from=build --chown=node:node /srv/proofscan/apps/web/.next/static ./apps/web/.next/static
COPY --from=build --chown=node:node /srv/proofscan/apps/web/public ./apps/web/public
ENV NODE_ENV=production HOSTNAME=0.0.0.0 PORT=3000 NEXT_TELEMETRY_DISABLED=1
USER node
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
