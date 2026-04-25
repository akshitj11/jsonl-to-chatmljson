import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


VALID_ROLES = {"system", "user", "assistant"}


class ConversionError(Exception):
    pass


def _text_from_content(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts: List[str] = []
        for item in value:
            text = _text_from_content(item)
            if text:
                parts.append(text)
        return "\n".join(parts).strip()
    if isinstance(value, dict):
        for key in ("text", "content", "value", "message"):
            if key in value:
                text = _text_from_content(value[key])
                if text:
                    return text
    return ""


def _collect_paths(inputs: Sequence[str]) -> List[Path]:
    paths: List[Path] = []
    for item in inputs:
        candidate = Path(item).expanduser()
        if candidate.is_dir():
            paths.extend(sorted(candidate.rglob("*.jsonl")))
            continue
        if candidate.is_file() and candidate.suffix.lower() == ".jsonl":
            paths.append(candidate)
            continue
        raise ConversionError(f"invalid input path: {item}")
    if not paths:
        raise ConversionError("no jsonl files found")
    return paths


def _read_lines(path: Path) -> List[Tuple[int, str]]:
    with path.open("r", encoding="utf-8-sig", errors="replace") as file:
        return [(idx, line.strip()) for idx, line in enumerate(file, start=1) if line.strip()]


def _extract_message(obj: object) -> Optional[Dict[str, str]]:
    if not isinstance(obj, dict):
        return None
    role = obj.get("role")
    content = obj.get("content")
    if not isinstance(role, str) or role not in VALID_ROLES:
        return None
    if isinstance(content, str):
        normalized = content.strip()
    else:
        normalized = _text_from_content(content)
    if not normalized:
        return None
    return {"role": role, "content": normalized}


def _extract_from_record(record: object) -> List[Dict[str, str]]:
    direct = _extract_message(record)
    if direct:
        return [direct]
    if not isinstance(record, dict):
        return []
    messages = record.get("messages")
    if isinstance(messages, list):
        out: List[Dict[str, str]] = []
        for item in messages:
            msg = _extract_message(item)
            if msg:
                out.append(msg)
        return out
    payload = record.get("payload")
    if isinstance(payload, dict):
        nested = _extract_message(payload)
        if nested:
            return [nested]
    event_type = record.get("type")
    if isinstance(event_type, str) and isinstance(payload, dict):
        payload_type = payload.get("type")
        if event_type == "response_item" and payload_type == "message":
            nested = _extract_message(payload)
            if nested:
                return [nested]
    return []


def _cleanup_system(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    systems = [m for m in messages if m["role"] == "system"]
    non_systems = [m for m in messages if m["role"] != "system"]
    return systems + non_systems


def _to_markdown(messages: List[Dict[str, str]]) -> str:
    parts: List[str] = []
    for msg in messages:
        title = msg["role"].upper()
        parts.append(f"## {title}\n\n{msg['content']}")
    return "\n\n".join(parts) + ("\n" if parts else "")


def convert_inputs(
    inputs: Sequence[str],
    *,
    strict: bool = False,
    cleanup_system: bool = True,
) -> Tuple[Dict[str, List[Dict[str, str]]], List[str]]:
    paths = _collect_paths(inputs)
    warnings: List[str] = []
    messages: List[Dict[str, str]] = []

    for path in paths:
        for line_no, line in _read_lines(path):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                warning = f"{path}:{line_no} malformed json: {exc.msg}"
                warnings.append(warning)
                if strict:
                    raise ConversionError(warning) from exc
                continue

            extracted = _extract_from_record(record)
            if not extracted:
                warning = f"{path}:{line_no} skipped non-message record"
                warnings.append(warning)
                if strict:
                    raise ConversionError(warning)
                continue

            messages.extend(extracted)

    if cleanup_system:
        messages = _cleanup_system(messages)

    return {"messages": messages}, warnings


def write_json(path: str, data: Dict[str, List[Dict[str, str]]], pretty: bool) -> None:
    out_path = Path(path).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as file:
        if pretty:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")
        else:
            json.dump(data, file, ensure_ascii=False, separators=(",", ":"))


def write_markdown(path: str, data: Dict[str, List[Dict[str, str]]]) -> None:
    out_path = Path(path).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_to_markdown(data.get("messages", [])), encoding="utf-8")
