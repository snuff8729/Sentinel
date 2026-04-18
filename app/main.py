from fastapi import FastAPI

app = FastAPI(title="Sentinel")


@app.get("/")
async def root():
    return {"message": "Hello from Sentinel"}


@app.get("/health")
async def health():
    return {"status": "ok"}
