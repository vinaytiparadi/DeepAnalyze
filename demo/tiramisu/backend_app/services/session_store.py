from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, List, Optional
from dataclasses import dataclass, asdict, field

from ..settings import settings


@dataclass
class SessionMetadata:
    id: str
    title: str = "Untitled Chat"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    messages: List[dict] = field(default_factory=list)
    plan: Optional[str] = None
    engine: str = "deepanalyze"
    report_theme: str = "literature"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> SessionMetadata:
        return cls(**data)


def _get_session_dir(session_id: str) -> Path:
    session_dir = Path(settings.workspace_base_dir) / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def _get_metadata_path(session_id: str) -> Path:
    return _get_session_dir(session_id) / "session_state.json"


def save_session(session: SessionMetadata) -> None:
    session.updated_at = time.time()
    path = _get_metadata_path(session.id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)


def load_session(session_id: str) -> Optional[SessionMetadata]:
    path = _get_metadata_path(session_id)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return SessionMetadata.from_dict(data)
    except Exception:
        return None


def list_sessions() -> List[dict]:
    workspace_root = Path(settings.workspace_base_dir)
    if not workspace_root.exists():
        return []

    sessions = []
    for item in workspace_root.iterdir():
        if item.is_dir():
            state_path = item / "session_state.json"
            if state_path.exists():
                try:
                    with open(state_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        # Return a summary for the list view
                        sessions.append({
                            "id": data["id"],
                            "title": data.get("title", "Untitled Chat"),
                            "created_at": data.get("created_at"),
                            "updated_at": data.get("updated_at"),
                            "engine": data.get("engine"),
                        })
                except Exception:
                    continue
    
    # Sort by updated_at descending
    sessions.sort(key=lambda s: s.get("updated_at", 0), reverse=True)
    return sessions


def delete_session(session_id: str) -> bool:
    import shutil
    session_dir = Path(settings.workspace_base_dir) / session_id
    if session_dir.exists() and session_dir.is_dir():
        shutil.rmtree(session_dir)
        return True
    return False


def update_session_title(session_id: str, title: str) -> bool:
    session = load_session(session_id)
    if session:
        session.title = title
        save_session(session)
        return True
    return False
