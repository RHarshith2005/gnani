"""NegoAI gateway.

Run locally:
    uvicorn api.main:app --reload --port 8000

The app serves the JSON API, the voice WebSocket, and — when ``web/dist``
exists — the built SPA on the same origin, so one command runs the whole demo.
"""

from __future__ import annotations

import logging
import secrets
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import db
from .config import settings
from .negotiation.personas import PERSONAS
from .voice.gateway import router as voice_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

app = FastAPI(title="NegoAI", version="1.0.0", description="Community procurement voice agent")

origins = ["*"] if settings.allow_origins == "*" else [o.strip() for o in settings.allow_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(voice_router)


@app.on_event("startup")
def _startup() -> None:
    conn = db.init_db()
    db.seed(conn)
    logging.getLogger("negoai").info("database ready at %s", settings.database_path)
    logging.getLogger("negoai").info(
        "gnani=%s llm=%s", settings.stt_mode, "on" if settings.has_llm else "scripted"
    )


@app.get("/api/health")
def health() -> dict:
    database = db.health()
    return {
        "ok": database.get("ok", False),
        "service": "negoai",
        "version": "1.0.0",
        "database": database,
        "capabilities": settings.as_public(),
        "languages": ["kn-IN", "hi-IN", "en-IN"],
        "community": {"id": db.COMMUNITY_ID, "name": "Green Residency", "households": 120},
    }


@app.get("/api/vendors")
def vendors() -> dict:
    return {"vendors": [persona.to_dict() for persona in PERSONAS]}


@app.get("/api/demand")
def demand(product: str = "water can") -> dict:
    return db.aggregate_demand(db.COMMUNITY_ID, product)


@app.get("/api/demand/summary")
def demand_summary() -> dict:
    """Households and total weekly quantity per product (Prompt 8)."""
    return db.demand_summary(db.COMMUNITY_ID)


@app.get("/api/demand/requests")
def demand_requests(limit: int = 20) -> dict:
    return {"requests": db.list_demand(db.COMMUNITY_ID, limit=limit)}


# Demo roles only: no password, no signup. Tokens live in memory for one hour.
_DEMO_USERS = {
    "resident": {"id": "res-asha", "name": "Asha", "flat": "A-204", "role": "resident"},
    "admin": {"id": "res-admin", "name": "Society admin", "flat": "Office", "role": "admin"},
}
_DEMO_TOKENS: dict[str, dict] = {}
_DEMO_TOKEN_TTL = 3600


class DemoLoginIn(BaseModel):
    role: str = Field(default="resident", pattern="^(resident|admin)$")


@app.post("/api/demo-login")
def demo_login(payload: DemoLoginIn) -> dict:
    """Pick a seeded demo role; there is deliberately no real authentication."""
    now = time.time()
    for token, entry in list(_DEMO_TOKENS.items()):
        if entry["expires_at"] <= now:
            _DEMO_TOKENS.pop(token, None)
    token = secrets.token_urlsafe(24)
    user = dict(_DEMO_USERS[payload.role])
    _DEMO_TOKENS[token] = {"user": user, "expires_at": now + _DEMO_TOKEN_TTL}
    return {
        "token": token,
        "token_type": "demo",
        "expires_in": _DEMO_TOKEN_TTL,
        "user": user,
        "notice": "Synthetic demo role. No real signup, no password, no production auth.",
    }


@app.get("/api/demo-users")
def demo_users() -> dict:
    return {"users": list(_DEMO_USERS.values())}


@app.get("/api/sessions")
def sessions(limit: int = 20) -> dict:
    return {"sessions": db.list_sessions(limit=max(1, min(limit, 100)))}


@app.get("/api/sessions/{session_id}/events")
def session_events(session_id: str) -> dict:
    events = db.get_events(session_id)
    if not events:
        raise HTTPException(status_code=404, detail="No events for that session")
    return {"session_id": session_id, "events": events}


class ApprovalIn(BaseModel):
    negotiation_id: str = Field(min_length=1)
    decision: str = Field(pattern="^(approved|rejected)$")
    note: str = ""
    offer_id: str | None = None


@app.post("/api/approvals")
def create_approval(payload: ApprovalIn) -> dict:
    approval_id = db.save_approval(
        negotiation_id=payload.negotiation_id,
        decision=payload.decision,
        note=payload.note,
        offer_id=payload.offer_id,
    )
    db.add_event(
        payload.negotiation_id,
        actor="admin",
        type="approval",
        payload={"decision": payload.decision, "note": payload.note},
    )
    return {"id": approval_id, "decision": payload.decision}


# ------------------------------------------------------------------ static SPA
DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
if DIST.exists():
    assets = DIST / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        if full_path.startswith(("api/", "ws/")):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (DIST / full_path).resolve()
        if full_path and candidate.is_file() and DIST.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(DIST / "index.html")
