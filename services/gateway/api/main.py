from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.gateway.api.routers import admin, artifacts, auth, chats, health, nl2chart, runtime


app = FastAPI(
    title="NL2BI AI Assistant API",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001", "http://127.0.0.1:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(runtime.router)
app.include_router(artifacts.router)
app.include_router(nl2chart.router)
app.include_router(auth.router)
app.include_router(chats.router)
app.include_router(admin.router)

