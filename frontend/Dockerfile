FROM node:22-alpine
WORKDIR /srv/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
ARG NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build
USER node
EXPOSE 3000
CMD ["npm", "run", "start", "--", "-H", "0.0.0.0"]
