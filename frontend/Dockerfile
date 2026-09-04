# Build context is frontend/ (see docker-compose.yml). No NEXT_PUBLIC_*
# vars exist in this app (verified: BACKEND_URL is read server-side only,
# at request time, by lib/backend.ts / the proxy route) — so nothing needs
# to be baked in at build time; BACKEND_URL is supplied at container
# runtime via docker-compose instead.
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# next.config.ts sets output:"standalone" — .next/standalone carries only
# the production node_modules subset actually used, not the full tree.
FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
ENV PORT=3000 HOSTNAME=0.0.0.0
CMD ["node", "server.js"]
