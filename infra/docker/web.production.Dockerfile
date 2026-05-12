FROM node:20-alpine AS deps

WORKDIR /app

COPY package.json package-lock.json /app/
COPY apps/web/package.json /app/apps/web/package.json
COPY packages/shared-types/package.json /app/packages/shared-types/package.json

RUN npm ci

FROM deps AS builder

ARG NEXT_PUBLIC_APP_VERSION=0.0.0-dev
ENV NEXT_PUBLIC_APP_VERSION=${NEXT_PUBLIC_APP_VERSION}

COPY . /app

RUN npm run build --workspace @pantro/web

FROM node:20-alpine AS runner

ENV NODE_ENV=production

ARG PANTRO_UID=10001
ARG PANTRO_GID=10001

WORKDIR /app

RUN addgroup -g "${PANTRO_GID}" -S pantro \
    && adduser -u "${PANTRO_UID}" -S pantro -G pantro \
    && chown -R "${PANTRO_UID}:${PANTRO_GID}" /app

COPY --from=builder --chown=${PANTRO_UID}:${PANTRO_GID} /app/apps/web/.next/standalone ./
COPY --from=builder --chown=${PANTRO_UID}:${PANTRO_GID} /app/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder --chown=${PANTRO_UID}:${PANTRO_GID} /app/apps/web/public ./apps/web/public
COPY --from=builder --chown=${PANTRO_UID}:${PANTRO_GID} /app/VERSION /app/VERSION

EXPOSE 3000

USER ${PANTRO_UID}:${PANTRO_GID}

CMD ["node", "apps/web/server.js"]
