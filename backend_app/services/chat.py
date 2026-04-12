from __future__ import annotations

import json
import logging
import re
import time
import threading
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import textwrap

import httpx
import openai

log = logging.getLogger(__name__)

from .execution import (
    build_file_block,
    collect_artifact_paths,
    execute_code_safe,
    snapshot_workspace_files,
)
from .workspace import collect_file_info, get_session_workspace
from ..settings import settings


client = openai.OpenAI(base_url=settings.api_base, api_key="dummy")
_STOP_EVENTS: dict[str, threading.Event] = {}
_STOP_EVENTS_LOCK = threading.Lock()
HEYWHALE_API_BASE = (
    "https://www.heywhale.com/api/model/services/691d42c36c6dda33df0bf645/app/v1"
)
REMOTE_STOP_SEQUENCES = ["</Code>", "</Answer>"]


@dataclass(frozen=True)
class ChatRuntimeConfig:
    provider: str = "local"
    temperature: float = 0.4
    model: str = settings.model_path
    api_key: str = ""
    api_base: str = ""


def _get_or_create_stop_event(session_id: str) -> threading.Event:
    sid = session_id or "default"
    with _STOP_EVENTS_LOCK:
        event = _STOP_EVENTS.get(sid)
        if event is None:
            event = threading.Event()
            _STOP_EVENTS[sid] = event
        return event


def request_stop(session_id: str) -> None:
    _get_or_create_stop_event(session_id).set()


def _normalize_temperature(value: Any) -> float:
    try:
        temperature = float(value)
    except (TypeError, ValueError):
        return 0.4
    return max(0.0, min(2.0, temperature))


def build_chat_runtime_config(payload: dict[str, Any] | None) -> ChatRuntimeConfig:
    body = payload or {}
    provider = str(body.get("provider") or "local").strip().lower() or "local"
    if provider not in {"local", "heywhale", "gemini"}:
        provider = "local"

    api_base = str(body.get("api_base") or "").strip()
    if provider == "heywhale" and not api_base:
        api_base = HEYWHALE_API_BASE

    model = str(body.get("model") or settings.model_path).strip() or settings.model_path
    api_key = str(body.get("api_key") or "").strip()

    return ChatRuntimeConfig(
        provider=provider,
        temperature=_normalize_temperature(body.get("temperature")),
        model=model,
        api_key=api_key,
        api_base=api_base,
    )


def _infer_missing_close_tag(content: str) -> str | None:
    if "<Code>" in content and "</Code>" not in content:
        return "</Code>"
    if "<Answer>" in content and "</Answer>" not in content:
        return "</Answer>"
    return None


def _starts_with_structured_tag(content: str) -> bool:
    return bool(
        re.match(
            r"^\s*<(Analyze|Understand|Code|Execute|Answer|File)>",
            content or "",
        )
    )


def _iter_local_stream(
    conversation: list[dict[str, Any]],
    runtime_config: ChatRuntimeConfig,
):
    response = client.chat.completions.create(
        model=runtime_config.model,
        messages=conversation,
        temperature=runtime_config.temperature,
        stream=True,
        extra_body={
            "add_generation_prompt": False,
            "stop_token_ids": [151676, 151645],
            "max_new_tokens": 32768,
        },
    )
    try:
        for chunk in response:
            yield chunk.choices[0].delta.content if chunk.choices else None, chunk
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()


def _iter_heywhale_stream(
    conversation: list[dict[str, Any]],
    runtime_config: ChatRuntimeConfig,
):
    if not runtime_config.api_key:
        raise ValueError("HeyWhale API key is required")

    request_body = {
        "messages": conversation,
        "temperature": runtime_config.temperature,
        "stream": True,
        "stop": REMOTE_STOP_SEQUENCES,
    }

    with httpx.Client(timeout=None) as http_client:
        with http_client.stream(
            "POST",
            f"{runtime_config.api_base.rstrip('/')}/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {runtime_config.api_key}",
            },
            json=request_body,
        ) as response:
            response.raise_for_status()
            for raw_line in response.iter_lines():
                if not raw_line:
                    continue
                line = raw_line.strip()
                if not line:
                    continue
                if line.startswith("data:"):
                    line = line[5:].strip()
                if line == "[DONE]":
                    break
                try:
                    payload = json.loads(line)
                except Exception:
                    continue
                choice = (payload.get("choices") or [{}])[0]
                delta = (choice.get("delta") or {}).get("content")
                finish_reason = choice.get("finish_reason")
                yield delta, {"choices": [{"finish_reason": finish_reason}]}


GEMINI_SYSTEM_PROMPT = textwrap.dedent("""\
    You are an autonomous data science agent. You analyze datasets by writing
    and executing Python code iteratively until you reach a conclusion.

    ## Output Format
    Structure your output using these XML tags:

    <Analyze> — Reasoning, planning, and reflection. Think step-by-step about
    what to do next, what you've learned so far, and what hypotheses to test.

    <Understand> — Data comprehension. Describe the structure, types, quality,
    and relationships in the data.

    <Code> — Python code to execute. Wrap code in a markdown code block:
    ```python
    # your code here
    ```
    </Code>

    After you write a </Code> closing tag, STOP generating immediately. The
    system will execute your code and return results in an <Execute> block.
    You will then continue from there. NEVER generate <Execute> blocks yourself
    — they are injected by the execution environment only.

    <Answer> — Your final conclusion. Summarize findings, key insights,
    and recommendations. This ends the analysis.

    ## Rules
    - CRITICAL: After writing </Code>, you MUST stop. Do NOT write <Execute> or
      guess what the output might be. Wait for the system to provide real results.
    - Always start with <Analyze> to plan your approach
    - Read data files from the current working directory (they're already there)
    - We are running each Code block in a separate session, so you can't rely on the previous session's state. So, you need to load the data and do all the preprocessing steps in each session.
    - Use pandas, matplotlib, seaborn, numpy, scipy, scikit-learn as needed
    - Save visualizations with plt.savefig('descriptive_name.png', dpi=150, bbox_inches='tight')
    - Always call plt.close() after saving figures
    - Save important results, statistics, and summaries to .txt files using
      open('descriptive_name.txt', 'w').write(content). For example, save
      EDA summaries, model metrics, statistical test results, etc.
    - Print results explicitly so they appear in execution output
    - Iterate: analyze results, write more code, refine until you have a thorough answer
    - End with <Answer> containing a clear, well-structured summary
""")


GEMINI_STREAM_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}"
    ":streamGenerateContent?alt=sse"
)


def _convert_messages_to_gemini_format(
    conversation: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert OpenAI-style messages to Gemini contents format."""
    contents: list[dict[str, Any]] = []
    for msg in conversation:
        role = msg.get("role", "")
        content = str(msg.get("content", ""))
        if role == "user":
            contents.append({"role": "user", "parts": [{"text": content}]})
        elif role == "assistant":
            contents.append({"role": "model", "parts": [{"text": content}]})
        elif role == "execute":
            # Execution results go back as user messages
            contents.append({
                "role": "user",
                "parts": [{"text": f"[Execution Output]\n{content}"}],
            })
    # Gemini requires alternating user/model turns — merge consecutive same-role
    merged: list[dict[str, Any]] = []
    for c in contents:
        if merged and merged[-1]["role"] == c["role"]:
            merged[-1]["parts"].extend(c["parts"])
        else:
            merged.append(c)
    return merged


_GEMINI_MAX_RETRIES = 3
_GEMINI_RETRY_BACKOFF = [2, 4, 8]  # seconds
_GEMINI_RETRYABLE_STATUS = {429, 500, 502, 503}


def _iter_gemini_stream(
    conversation: list[dict[str, Any]],
    runtime_config: ChatRuntimeConfig,
):
    """Stream from Gemini API, yielding (delta_text, chunk_dict, is_thinking).

    Retries on transient errors (429, 5xx) with exponential backoff.
    """
    model = runtime_config.model or settings.gemini_model
    url = GEMINI_STREAM_API_URL.format(model=model)

    contents = _convert_messages_to_gemini_format(conversation)

    request_body = {
        "contents": contents,
        "systemInstruction": {"parts": [{"text": GEMINI_SYSTEM_PROMPT}]},
        "generationConfig": {
            "temperature": 1.0,
            "maxOutputTokens": 65536,
            "stopSequences": ["</Code>"],
            "thinkingConfig": {
                "thinkingLevel": "high",
                "includeThoughts": True,
            },
        },
    }

    last_exc: Exception | None = None
    for attempt in range(_GEMINI_MAX_RETRIES):
        try:
            with httpx.Client(timeout=None) as http_client:
                with http_client.stream(
                    "POST",
                    url,
                    headers={
                        "Content-Type": "application/json",
                        "x-goog-api-key": settings.gemini_api_key,
                    },
                    json=request_body,
                ) as response:
                    if response.status_code in _GEMINI_RETRYABLE_STATUS:
                        wait = _GEMINI_RETRY_BACKOFF[min(attempt, len(_GEMINI_RETRY_BACKOFF) - 1)]
                        log.warning(
                            "Gemini returned %s, retrying in %ds (attempt %d/%d)",
                            response.status_code, wait, attempt + 1, _GEMINI_MAX_RETRIES,
                        )
                        time.sleep(wait)
                        continue
                    response.raise_for_status()

                    for raw_line in response.iter_lines():
                        if not raw_line:
                            continue
                        line = raw_line.strip()
                        if not line:
                            continue
                        if line.startswith("data:"):
                            line = line[5:].strip()
                        if line == "[DONE]" or not line:
                            break
                        try:
                            payload = json.loads(line)
                        except Exception:
                            continue

                        candidates = payload.get("candidates") or []
                        if not candidates:
                            continue

                        parts = (
                            candidates[0].get("content", {}).get("parts") or []
                        )
                        for part in parts:
                            text = part.get("text")
                            if text is None:
                                continue
                            is_thinking = bool(part.get("thought"))
                            yield text, payload, is_thinking

                        finish_reason = candidates[0].get("finishReason")
                        if finish_reason and finish_reason not in ("FINISH_REASON_UNSPECIFIED",):
                            break
                    # Successfully streamed — exit retry loop
                    return
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in _GEMINI_RETRYABLE_STATUS:
                last_exc = exc
                wait = _GEMINI_RETRY_BACKOFF[min(attempt, len(_GEMINI_RETRY_BACKOFF) - 1)]
                log.warning(
                    "Gemini HTTP %s, retrying in %ds (attempt %d/%d)",
                    exc.response.status_code, wait, attempt + 1, _GEMINI_MAX_RETRIES,
                )
                time.sleep(wait)
                continue
            raise
        except (httpx.ConnectError, httpx.ReadTimeout) as exc:
            last_exc = exc
            wait = _GEMINI_RETRY_BACKOFF[min(attempt, len(_GEMINI_RETRY_BACKOFF) - 1)]
            log.warning(
                "Gemini connection error, retrying in %ds (attempt %d/%d): %s",
                wait, attempt + 1, _GEMINI_MAX_RETRIES, exc,
            )
            time.sleep(wait)
            continue

    # All retries exhausted
    if last_exc:
        raise last_exc


def _resolve_workspace_selection(
    workspace: Iterable[str] | None,
    workspace_dir: str,
) -> list[Path]:
    workspace_root = Path(workspace_dir).resolve()
    resolved_paths: list[Path] = []
    for item in workspace or []:
        candidate = Path(item)
        if not candidate.is_absolute():
            candidate = (workspace_root / candidate).resolve()
        if candidate.exists() and candidate.is_file():
            resolved_paths.append(candidate)
    return resolved_paths


def _build_user_prompt(
    messages: list[dict[str, Any]],
    workspace: list[str],
    workspace_dir: str,
    plan: str | None = None,
) -> None:
    if not messages or messages[-1].get("role") != "user":
        return

    user_message = str(messages[-1].get("content") or "")
    selected_paths = _resolve_workspace_selection(workspace, workspace_dir)
    file_info = collect_file_info(selected_paths if selected_paths else workspace_dir)

    parts = [f"# Instruction\n{user_message}"]
    if plan:
        parts.append(
            f"# Analysis Plan\n{plan}\n\n"
            "Follow this plan. Execute each step, show results, "
            "and adapt if you discover something unexpected."
        )
    if file_info:
        parts.append(f"# Data\n{file_info}")

    messages[-1]["content"] = "\n\n".join(parts)


def _extract_code_to_execute(content: str) -> str | None:
    code_match = re.search(r"<Code>(.*?)</Code>", content, re.DOTALL)
    if not code_match:
        return None

    code_content = code_match.group(1).strip()
    md_match = re.search(r"```(?:python)?(.*?)```", code_content, re.DOTALL)
    return md_match.group(1).strip() if md_match else code_content


def bot_stream(
    messages: list[dict[str, Any]],
    workspace: list[str],
    session_id: str = "default",
    runtime_config: ChatRuntimeConfig | None = None,
    plan: str | None = None,
    router_enabled: bool = False,
):
    from .planner import (
        call_gemini_error_recovery,
        call_gemini_checkpoint,
        is_execution_error,
        validate_code_before_execution,
    )

    runtime_config = runtime_config or ChatRuntimeConfig()
    stop_event = _get_or_create_stop_event(session_id)
    stop_event.clear()
    conversation = deepcopy(messages or [])
    workspace_paths = list(workspace or [])
    workspace_dir = get_session_workspace(session_id)
    generated_dir = str(Path(workspace_dir) / "generated")
    Path(generated_dir).mkdir(parents=True, exist_ok=True)

    # Hybrid router state (never active for Gemini provider)
    router_active = (
        router_enabled
        and settings.router_active
        and runtime_config.provider != "gemini"
    )
    successful_exec_count = 0
    original_user_prompt = next(
        (str(m.get("content", "")) for m in (messages or []) if m.get("role") == "user"),
        "",
    )

    if conversation and conversation[0].get("role") == "assistant":
        conversation = conversation[1:]

    _build_user_prompt(conversation, workspace_paths, workspace_dir, plan=plan)

    initial_workspace = {
        path.resolve() for path in _resolve_workspace_selection(workspace_paths, workspace_dir)
    }
    finished = False
    should_patch_first_assistant_message = not any(
        str(message.get("role") or "") == "assistant" for message in conversation
    )

    try:
        while not finished:
            if stop_event.is_set():
                break

            cur_res = ""
            last_chunk = None
            leading_chunks: list[str] = []
            leading_decided = not should_patch_first_assistant_message
            is_gemini = runtime_config.provider == "gemini"

            if is_gemini:
                stream_iter_gemini = _iter_gemini_stream(conversation, runtime_config)
            elif runtime_config.provider == "heywhale":
                stream_iter_legacy = _iter_heywhale_stream(conversation, runtime_config)
            else:
                stream_iter_legacy = _iter_local_stream(conversation, runtime_config)

            # Gemini thinking state
            _in_thinking = False

            try:
                if is_gemini:
                    for delta, chunk, is_thinking in stream_iter_gemini:
                        if stop_event.is_set():
                            finished = True
                            break
                        last_chunk = chunk
                        if delta is None:
                            continue

                        if is_thinking:
                            # Wrap thinking deltas in <Thinking> tags
                            if not _in_thinking:
                                _in_thinking = True
                                yield "<Thinking>\n"
                            yield delta
                            continue

                        # Non-thinking text — close thinking block if open
                        if _in_thinking:
                            _in_thinking = False
                            yield "\n</Thinking>\n"

                        if not leading_decided:
                            leading_chunks.append(delta)
                            combined = "".join(leading_chunks)
                            if not combined.strip():
                                continue
                            leading_decided = True
                            should_prefix = not _starts_with_structured_tag(combined)
                            if should_prefix:
                                cur_res += "<Analyze>\n"
                                yield "<Analyze>\n"
                            cur_res += combined
                            yield combined
                            should_patch_first_assistant_message = False
                            continue

                        cur_res += delta
                        yield delta

                        if "</Answer>" in cur_res:
                            finished = True
                            break
                        # Break on </Code> so the backend can extract and
                        # execute the code, then call Gemini again with
                        # the real execution results.
                        if "</Code>" in cur_res:
                            break
                else:
                    for delta, chunk in stream_iter_legacy:
                        if stop_event.is_set():
                            finished = True
                            break
                        last_chunk = chunk
                        if delta is not None:
                            if not leading_decided:
                                leading_chunks.append(delta)
                                combined = "".join(leading_chunks)
                                if not combined.strip():
                                    continue
                                leading_decided = True
                                should_prefix = not _starts_with_structured_tag(combined)
                                if should_prefix:
                                    cur_res += "<Analyze>\n"
                                    yield "<Analyze>\n"
                                cur_res += combined
                                yield combined
                                should_patch_first_assistant_message = False
                                continue
                            cur_res += delta
                            yield delta
                        if "</Answer>" in cur_res:
                            finished = True
                            break
            except (httpx.HTTPError, RuntimeError) as exc:
                log.error("Stream request failed: %s", exc)
                if is_gemini:
                    # Yield an error message to the frontend instead of crashing
                    err_msg = (
                        f"\n<Analyze>\n[Error] Gemini API request failed after "
                        f"{_GEMINI_MAX_RETRIES} retries: {exc}\n"
                        f"Please try again.\n</Analyze>\n"
                    )
                    yield err_msg
                    finished = True
                    break
                raise RuntimeError(f"Stream request failed: {exc}") from exc

            # Close any open thinking block at end of stream
            if _in_thinking:
                _in_thinking = False
                yield "\n</Thinking>\n"

            if stop_event.is_set():
                break

            finish_reason = None
            if last_chunk:
                if is_gemini:
                    # Gemini uses finishReason in candidates
                    try:
                        fr = (last_chunk.get("candidates") or [{}])[0].get("finishReason")
                        if fr == "STOP":
                            finish_reason = "stop"
                    except Exception:
                        pass
                else:
                    try:
                        finish_reason = last_chunk["choices"][0]["finish_reason"]
                    except Exception:
                        finish_reason = getattr(last_chunk.choices[0], "finish_reason", None)

            missing_tag = _infer_missing_close_tag(cur_res)
            if finish_reason == "stop" and not finished and missing_tag:
                cur_res += missing_tag
                yield missing_tag
                if missing_tag == "</Answer>":
                    finished = True

            if "</Code>" not in cur_res or finished:
                continue

            conversation.append({"role": "assistant", "content": cur_res})
            code_str = _extract_code_to_execute(cur_res)
            if not code_str:
                continue

            # ── Pre-execution validator ──
            # Always apply lightweight code patching (auto-imports, encoding fixes).
            # Only emit RouterGuidance warnings when plan+router is active.
            if code_str:
                data_ctx = plan or ""
                patched_code, validation_warning = validate_code_before_execution(
                    code_str, data_ctx, file_names=workspace_paths,
                )
                if router_active and validation_warning:
                    warn_block = (
                        f"\n<RouterGuidance>\n[Pre-execution Check]\n"
                        f"{validation_warning}\n</RouterGuidance>\n"
                    )
                    yield warn_block
                    conversation.append({
                        "role": "execute",
                        "content": f"[Validation Warning] {validation_warning}",
                    })
                code_str = patched_code

            before_state = snapshot_workspace_files(workspace_dir)
            log.info("Before exec: %d files in workspace %s", len(before_state), workspace_dir)
            exe_output = execute_code_safe(code_str, workspace_dir, session_id)
            if stop_event.is_set():
                break
            after_state = snapshot_workspace_files(workspace_dir)
            new_files = [p for p in after_state if p not in before_state]
            modified_files = [p for p in after_state if p in before_state and after_state[p] != before_state[p]]
            log.info("After exec: %d files, %d new, %d modified", len(after_state), len(new_files), len(modified_files))
            if new_files:
                log.info("New files: %s", [str(p) for p in new_files])
            artifact_paths = collect_artifact_paths(
                before_state,
                after_state,
                generated_dir,
                session_id,
            )
            log.info("Artifact paths: %s", [str(p) for p in artifact_paths])

            exe_str = f"\n<Execute>\n```\n{exe_output}\n```\n</Execute>\n"
            file_block = build_file_block(artifact_paths, workspace_dir, session_id)
            yield exe_str + file_block

            # ── Hybrid Router: Error Recovery ──
            guidance_block = ""
            is_error = is_execution_error(exe_output)
            if (
                router_active
                and settings.router_error_recovery
                and is_error
                and not stop_event.is_set()
            ):
                guidance = call_gemini_error_recovery(
                    user_prompt=original_user_prompt,
                    data_context=plan or "",
                    conversation=conversation,
                    failed_code=code_str,
                    error_output=exe_output,
                )
                if guidance:
                    guidance_block = f"\n\n[Senior Analyst Guidance]\n{guidance}"
                    yield f"\n<RouterGuidance>\n{guidance}\n</RouterGuidance>\n"

            conversation.append({
                "role": "execute",
                "content": exe_output + guidance_block,
            })

            # ── Retry directive: tell the model to fix and re-run ──
            if is_error and guidance_block:
                retry_msg = (
                    "The code above failed. The Senior Analyst has provided "
                    "corrected code. You MUST re-run the corrected code for "
                    "this step NOW before moving on to the next step. "
                    "Do NOT skip this step or summarize — generate the fixed "
                    "<Code> block immediately."
                )
                conversation.append({"role": "execute", "content": retry_msg})

            # ── Hybrid Router: Periodic Checkpoint ──
            if not is_error:
                successful_exec_count += 1
            if (
                router_active
                and settings.router_checkpoints
                and not is_error
                and successful_exec_count > 0
                and successful_exec_count % settings.router_checkpoint_interval == 0
                and not finished
                and not stop_event.is_set()
            ):
                checkpoint = call_gemini_checkpoint(
                    user_prompt=original_user_prompt,
                    plan=plan,
                    conversation=conversation,
                    successful_rounds=successful_exec_count,
                )
                if checkpoint:
                    checkpoint_msg = f"[Checkpoint — Senior Analyst Review]\n{checkpoint}"
                    conversation.append({"role": "execute", "content": checkpoint_msg})
                    yield f"\n<RouterGuidance>\n{checkpoint_msg}\n</RouterGuidance>\n"

            current_files = {
                path.resolve() for path in Path(workspace_dir).rglob("*") if path.is_file()
            }
            new_files = [str(path) for path in current_files - initial_workspace]
            if new_files:
                workspace_paths.extend(new_files)
                initial_workspace.update(Path(path).resolve() for path in new_files)

    finally:
        stop_event.clear()
