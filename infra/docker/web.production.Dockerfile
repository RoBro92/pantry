FROM node:20-alpine AS deps

WORKDIR /app

COPY package.json package-lock.json /app/
COPY apps/web/package.json /app/apps/web/package.json
COPY packages/shared-types/package.json /app/packages/shared-types/package.json

RUN npm install

FROM deps AS builder

ARG NEXT_PUBLIC_APP_VERSION=0.0.0-dev
ENV NEXT_PUBLIC_APP_VERSION=${NEXT_PUBLIC_APP_VERSION}

COPY . /app

RUN npm run build --workspace @pantry/web

FROM node:20-alpine AS runner

ENV NODE_ENV=production

WORKDIR /app

COPY --from=builder /app/package.json /app/package.json
COPY --from=builder /app/package-lock.json /app/package-lock.json
COPY --from=builder /app/apps/web /app/apps/web
COPY --from=builder /app/packages/shared-types /app/packages/shared-types
COPY --from=builder /app/node_modules /app/node_modules
COPY --from=builder /app/VERSION /app/VERSION

EXPOSE 3000

CMD ["npm", "run", "start", "--workspace", "@pantry/web", "--", "--hostname", "0.0.0.0", "--port", "3000"]
