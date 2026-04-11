from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Optional

from ..services import session_store as store

router = APIRouter()


@router.get("/sessions")
async def list_sessions():
    return {"sessions": store.list_sessions()}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    session = store.load_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.to_dict()


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    success = store.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session deleted"}


@router.patch("/sessions/{session_id}/title")
async def update_session_title(session_id: str, body: dict = Body(...)):
    title = body.get("title")
    if not title:
        raise HTTPException(status_code=400, detail="Title is required")
    success = store.update_session_title(session_id, title)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Title updated"}
