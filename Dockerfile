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

# Passed via BuildKit secret mount (not --build-arg) so the key never
# appears in the command line, shell history, or the image's layer history.
RUN --mount=type=secret,id=college_scorecard_api_key \
    COLLEGE_SCORECARD_API_KEY="$(cat /run/secrets/college_scorecard_api_key)" python -m scripts.refresh_data

ENV SCORECARD_DB_PATH=/app/scorecard.sqlite
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
