# Dockerfile
FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend-build /frontend/dist ./static

ARG COLLEGE_SCORECARD_API_KEY
ENV COLLEGE_SCORECARD_API_KEY=${COLLEGE_SCORECARD_API_KEY}
RUN python -m scripts.refresh_data

ENV SCORECARD_DB_PATH=/app/scorecard.sqlite
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
