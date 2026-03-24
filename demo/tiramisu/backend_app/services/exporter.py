from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .workspace import (
    build_download_url,
    get_session_workspace,
    register_generated_paths,
    uniquify_path,
)


def extract_sections_from_messages(messages: list[dict[str, Any]]) -> str:
    if not isinstance(messages, list):
        return ""

    parts: list[str] = []
    appendix: list[str] = []
    tag_pattern = r"<(Analyze|Understand|Code|Execute|File|Answer)>([\s\S]*?)</\1>"

    for message in messages:
        if (message or {}).get("role") != "assistant":
            continue

        content = str((message or {}).get("content") or "")
        step = 1
        for match in re.finditer(tag_pattern, content, re.DOTALL):
            tag, segment = match.groups()
            segment = segment.strip()
            if tag == "Answer":
                parts.append(f"{segment}\n")
            appendix.append(f"\n### Step {step}: {tag}\n\n{segment}\n")
            step += 1

    final_text = "".join(parts).strip()
    if appendix:
        final_text += (
            "\n\n---\n\n# Appendix: Detailed Process\n"
            + "".join(appendix).strip()
        )
    return final_text


def save_md(md_text: str, base_name: str, workspace_dir: str) -> Path:
    target_dir = Path(workspace_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    md_path = uniquify_path(target_dir / f"{base_name}.md")
    md_path.write_text(md_text, encoding="utf-8")
    return md_path


def _sanitize_filename_component(
    raw: str,
    *,
    fallback: str,
    max_length: int = 80,
) -> str:
    text = str(raw or "").strip()
    if not text:
        return fallback

    # Forbidden Windows filename characters + control characters
    text = re.sub(r'[<>:"/\\|?*\x00-\x1F]+', "_", text)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"_+", "_", text).strip(" ._")

    if not text:
        text = fallback

    if len(text) > max_length:
        text = text[:max_length].rstrip(" ._") or fallback

    return text


def _build_export_base_name(title: str, *, prefix: str, timestamp: str) -> str:
    safe_title = _sanitize_filename_component(title, fallback=prefix, max_length=80)
    return f"{safe_title}_{timestamp}"


def _to_file_meta(
    session_id: str,
    workspace_root: Path,
    file_path: Path | None,
) -> dict[str, Any] | None:
    if file_path is None:
        return None
    rel_path = file_path.relative_to(workspace_root).as_posix()
    return {
        "name": file_path.name,
        "path": rel_path,
        "download_url": build_download_url(f"{session_id}/{rel_path}"),
    }


def export_report_from_body(body: dict[str, Any]) -> dict[str, Any]:
    messages = body.get("messages", [])
    if not isinstance(messages, list):
        raise ValueError("messages must be a list")

    title = (body.get("title") or "").strip()
    session_id = body.get("session_id", "default")
    workspace_dir = get_session_workspace(session_id)
    workspace_root = Path(workspace_dir)

    md_text = extract_sections_from_messages(messages)
    if not md_text:
        md_text = "(No <Analyze>/<Understand>/<Code>/<Execute>/<Answer> sections found.)"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = _build_export_base_name(title, prefix="Report", timestamp=timestamp)

    export_dir = workspace_root / "generated" / "reports"
    export_dir.mkdir(parents=True, exist_ok=True)

    md_path = save_md(md_text, base_name, str(export_dir))
    register_generated_paths(
        session_id,
        [md_path.relative_to(workspace_root).as_posix()],
    )

    md_meta = _to_file_meta(session_id, workspace_root, md_path)

    return {
        "message": "exported",
        "md": md_path.name,
        "files": {
            "md": md_meta,
        },
        "download_urls": {
            "md": md_meta["download_url"] if md_meta else None,
        },
    }
