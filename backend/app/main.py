from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.routers import auth, files, maintenance, personnel, stores, transactions

app = FastAPI(
    title="KlongthomSales API",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def protect_origin(request: Request, call_next):
    if request.url.path.startswith(settings.API_PREFIX + "/"):
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            same_origin = f"{request.url.scheme}://{request.url.netloc}"
            if not origin or origin not in [same_origin, *settings.CORS_ORIGINS]:
                return JSONResponse({"detail": "Untrusted request origin"}, status_code=403)
        if request.method == "POST" and request.url.path.endswith("/files"):
            length = request.headers.get("content-length")
            if length:
                try:
                    too_large = int(length) > settings.PHOTO_MAX_BYTES + 65536
                except ValueError:
                    return JSONResponse({"detail": "Invalid content length"}, status_code=400)
                if too_large:
                    return JSONResponse({"detail": "Photo request exceeds 2 MB plus multipart overhead"}, status_code=413)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response
    return await call_next(request)


app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(stores.router, prefix=settings.API_PREFIX)
app.include_router(personnel.router, prefix=settings.API_PREFIX)
app.include_router(transactions.router, prefix=settings.API_PREFIX)
app.include_router(files.router, prefix=settings.API_PREFIX)
app.include_router(maintenance.router, prefix=settings.API_PREFIX)


@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok"}
