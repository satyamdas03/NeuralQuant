# Build context MUST be the repo root: `docker build -f apps/web/Dockerfile .`
FROM node:20-alpine
WORKDIR /app

# NEXT_PUBLIC_* vars are baked at build time
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_TELEMETRY_DISABLED=1

COPY apps/web/package*.json ./
RUN npm ci

COPY apps/web/ .
RUN npm run build

EXPOSE 3000
CMD ["npm", "start"]
