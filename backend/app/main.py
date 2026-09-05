from fastapi import FastAPI

app = FastAPI(title="College Compass")


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
