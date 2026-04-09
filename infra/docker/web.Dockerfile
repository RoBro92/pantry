FROM node:20-alpine

WORKDIR /workspace

COPY package.json /workspace/package.json
COPY package-lock.json /workspace/package-lock.json
COPY apps/web/package.json /workspace/apps/web/package.json
COPY packages/shared-types/package.json /workspace/packages/shared-types/package.json

RUN npm ci

COPY . /workspace

EXPOSE 3000
