from __future__ import annotations

import json

from fastapi import APIRouter, Body
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from ..services.chat import bot_stream, build_chat_runtime_config, request_stop
from ..services.execution import execute_code_safe
from ..services.planner import generate_plan
from ..services.workspace import get_session_workspace
from ..services import session_store as store
from ..settings import settings


router = APIRouter()


@router.post("/execute")
async def execute_code_api(request: dict):
    code = request.get("code", "")
    session_id = request.get("session_id", "default")
    workspace_dir = get_session_workspace(session_id)

    if not code:
        return {
            "success": False,
            "result": "Error: No code provided",
            "message": "Code execution failed",
        }

    try:
        result = await run_in_threadpool(execute_code_safe, code, workspace_dir, session_id)
        return {
            "success": True,
            "result": result,
            "message": "Code executed successfully",
        }
    except Exception as exc:
        return {
            "success": False,
            "result": f"Error: {exc}",
            "message": "Code execution failed",
        }


@router.post("/chat/plan")
async def plan_analysis(body: dict = Body(...)):
    session_id = body.get("session_id", "default")
    user_prompt = body.get("prompt", "")
    workspace_files = body.get("workspace", [])
    
    # Initialize session if not exists
    session = store.load_session(session_id)
    if not session:
        session = store.SessionMetadata(id=session_id, title=user_prompt[:50] or "New Analysis")
        store.save_session(session)

    try:
        result = await generate_plan(session_id, user_prompt, workspace_files)
        if result.get("plan"):
            session.plan = result["plan"]
            store.save_session(session)
        return result
    except Exception as exc:
        return {"plan": None, "error": str(exc)}


@router.post("/chat/completions")
async def chat(body: dict = Body(...)):
    messages = body.get("messages", [])
    workspace = body.get("workspace", [])
    session_id = body.get("session_id", "default")
    plan = body.get("plan")
    router_enabled = bool(body.get("router_enabled", False))
    runtime_config = build_chat_runtime_config(body)

    # Initialize/Load session
    session = store.load_session(session_id)
    if not session:
        # Try to infer title from the first user message
        title = "New Analysis"
        for m in messages:
            if m.get("role") == "user":
                title = m.get("content", "")[:50]
                break
        session = store.SessionMetadata(
            id=session_id, 
            title=title, 
            messages=messages,
            plan=plan,
            engine="gemini" if runtime_config.provider == "gemini" else "deepanalyze"
        )
    else:
        session.messages = messages
        if plan:
            session.plan = plan
        session.engine = "gemini" if runtime_config.provider == "gemini" else "deepanalyze"
    
    store.save_session(session)

    def generate():
        full_response = ""
        for delta_content in bot_stream(messages, workspace, session_id, runtime_config, plan=plan, router_enabled=router_enabled):
            full_response += delta_content
            chunk = {
                "id": "chatcmpl-stream",
                "object": "chat.completion.chunk",
                "created": 1677652288,
                "model": runtime_config.model or settings.model_path,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": delta_content},
                        "finish_reason": None,
                    }
                ],
            }
            yield json.dumps(chunk) + "\n"

        # Save the full assistant response to history
        session.messages.append({"role": "assistant", "content": full_response})
        store.save_session(session)

        end_chunk = {
            "id": "chatcmpl-stream",
            "object": "chat.completion.chunk",
            "created": 1677652288,
            "model": runtime_config.model or settings.model_path,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        yield json.dumps(end_chunk) + "\n"

    return StreamingResponse(generate(), media_type="text/plain")


@router.post("/chat/stop")
async def stop_chat(body: dict = Body(default={})):
    session_id = body.get("session_id", "default")
    request_stop(session_id)
    return {"message": "stop requested", "session_id": session_id}
