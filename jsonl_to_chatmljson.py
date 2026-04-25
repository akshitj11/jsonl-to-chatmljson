#!/usr/bin/env python3
"""
jsonl-to-chatmljson

Convert Codex session JSONL exports and other JSONL chat datasets into ChatML-style JSON.

Default output format:

[
  {
    "source": "input.jsonl",
    "messages": [
      {"role": "user", "content": "..."},
      {"role": "assistant", "content": "..."}
    ]
  }
]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


VALID_CHATML_ROLES = {"system", "user", "assistant", "tool"}

ROLE_ALIASES = {
    "human": "user",
    "person": "user",
    "client": "user",
    "input": "user",
    "prompt": "user",
    "ai": "assistant",
    "bot": "assistant",
    "model": "assistant",
    "completion": "assistant",
    "output": "assistant",
}


def normalize_role(role: Any) -> Optional[str]:
    """Normalize role names to ChatML roles."""
    if role is None:
        return None

    role_text = str(role).strip().lower()
    role_text = ROLE_ALIASES.get(role_text, role_text)

    if role_text in VALID_CHATML_ROLES:
        return role_text

    return None


def stringify_scalar(value: Any) -> str:
    """Convert a scalar-ish value to text."""
    if value is None:
        return ""

    if isinstance(value, str):
        return value

    if isinstance(value, (int, float, bool)):
        return str(value)

    return ""


def extract_text_from_content(content: Any) -> str:
    """
    Extract readable text from common message content shapes.

    Supported examples:
    - "hello"
    - [{"type": "input_text", "text": "hello"}]
    - [{"type": "output_text", "text": "hello"}]
    - [{"text": "hello"}]
    - {"text": "hello"}
    - {"content": "hello"}
    """
    if content is None:
        return ""

    if isinstance(content, str):
        return content

    if isinstance(content, (int, float, bool)):
        return str(content)

    if isinstance(content, list):
        parts: List[str] = []

        for item in content:
            text = extract_text_from_content(item)
            if text:
                parts.append(text)

        return "\n".join(parts).strip()

    if isinstance(content, dict):
        # Codex/OpenAI style content parts often use text.
        preferred_text_keys = (
            "text",
            "content",
            "message",
            "value",
            "input",
            "output",
            "result",
        )

        for key in preferred_text_keys:
            if key in content:
                text = extract_text_from_content(content.get(key))
                if text:
                    return text.strip()

        # Some tool/function objects contain arguments; keep them only if textual.
        if "arguments" in content:
            text = extract_text_from_content(content.get("arguments"))
            if text:
                return text.strip()

        # Last resort: avoid dumping huge nested objects unless they are clearly text-like.
        return ""

    return ""


def maybe_message_from_role_content(obj: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Try to build a ChatML message from an object with role/content-like fields."""
    role = normalize_role(obj.get("role") or obj.get("author") or obj.get("speaker"))

    if not role:
        return None

    content_candidates = (
        "content",
        "text",
        "message",
        "body",
        "value",
        "input",
        "output",
    )

    content = ""
    for key in content_candidates:
        if key in obj:
            content = extract_text_from_content(obj.get(key))
            if content:
                break

    if not content:
        return None

    return {"role": role, "content": content.strip()}


def maybe_message_from_codex_event(obj: Dict[str, Any], include_tools: bool = False) -> Optional[Dict[str, str]]:
    """
    Extract messages from Codex CLI session events.

    Codex session files often contain JSONL records shaped like:
    {
      "timestamp": "...",
      "type": "response_item",
      "payload": {
        "type": "message",
        "role": "user",
        "content": [{"type": "input_text", "text": "..."}]
      }
    }

    Assistant messages are similar with role="assistant" and output_text parts.
    """
    event_type = str(obj.get("type", "")).strip().lower()
    payload = obj.get("payload")

    if isinstance(payload, dict):
        payload_type = str(payload.get("type", "")).strip().lower()

        # Most useful Codex records: response_item -> payload message.
        if payload_type == "message":
            msg = maybe_message_from_role_content(payload)
            if msg:
                return msg

        # Some event variants may already carry role/content inside payload.
        msg = maybe_message_from_role_content(payload)
        if msg:
            return msg

        # Optional tool/function output preservation.
        if include_tools:
            toolish_types = {
                "function_call_output",
                "tool_call_output",
                "local_shell_call",
                "custom_tool_call_output",
            }
            if payload_type in toolish_types:
                text = extract_text_from_content(payload)
                if text:
                    return {"role": "tool", "content": text.strip()}

    # Other possible direct Codex event names.
    if event_type in {"user_message", "user_input", "prompt"}:
        text = extract_text_from_content(payload if payload is not None else obj)
        if text:
            return {"role": "user", "content": text.strip()}

    if event_type in {"assistant_message", "assistant_output", "completion"}:
        text = extract_text_from_content(payload if payload is not None else obj)
        if text:
            return {"role": "assistant", "content": text.strip()}

    return None


def messages_from_messages_array(obj: Dict[str, Any]) -> List[Dict[str, str]]:
    """Extract a messages array from a JSON object if present."""
    messages = obj.get("messages")
    if not isinstance(messages, list):
        return []

    output: List[Dict[str, str]] = []

    for item in messages:
        if not isinstance(item, dict):
            continue

        msg = maybe_message_from_role_content(item)
        if msg:
            output.append(msg)

    return output


def messages_from_prompt_completion(obj: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Extract common dataset formats:
    - prompt/completion
    - instruction/output
    - question/answer
    - input/output
    """
    pairs: Tuple[Tuple[str, str], ...] = (
        ("prompt", "completion"),
        ("prompt", "response"),
        ("instruction", "output"),
        ("instruction", "response"),
        ("question", "answer"),
        ("input", "output"),
        ("user", "assistant"),
    )

    for left_key, right_key in pairs:
        if left_key in obj and right_key in obj:
            left = extract_text_from_content(obj.get(left_key))
            right = extract_text_from_content(obj.get(right_key))

            messages: List[Dict[str, str]] = []

            if left:
                messages.append({"role": "user", "content": left.strip()})

            if right:
                messages.append({"role": "assistant", "content": right.strip()})

            if messages:
                return messages

    return []


def extract_messages_from_record(record: Any, include_tools: bool = False) -> List[Dict[str, str]]:
    """Extract zero or more ChatML messages from one JSONL record."""
    if not isinstance(record, dict):
        return []

    extracted: List[Dict[str, str]] = []

    # Full messages array format.
    extracted.extend(messages_from_messages_array(record))

    if extracted:
        return extracted

    # Direct role/content message.
    msg = maybe_message_from_role_content(record)
    if msg:
        return [msg]

    # Codex-style event wrapper.
    msg = maybe_message_from_codex_event(record, include_tools=include_tools)
    if msg:
        return [msg]

    # Dataset pair format.
    pair_messages = messages_from_prompt_completion(record)
    if pair_messages:
        return pair_messages

    # Nested common containers.
    for key in ("payload", "data", "item", "message", "record"):
        nested = record.get(key)
        if isinstance(nested, dict):
            nested_messages = extract_messages_from_record(nested, include_tools=include_tools)
            if nested_messages:
                return nested_messages

    return []


def merge_consecutive_messages(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Merge adjacent messages with the same role."""
    merged: List[Dict[str, str]] = []

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "").strip()

        if not role or not content:
            continue

        if merged and merged[-1]["role"] == role:
            merged[-1]["content"] = f"{merged[-1]['content']}\n\n{content}".strip()
        else:
            merged.append({"role": role, "content": content})

    return merged


def read_jsonl_records(path: Path) -> Iterable[Tuple[int, Any]]:
    """Yield JSON objects from a JSONL file."""
    with path.open("r", encoding="utf-8-sig", errors="replace") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()

            if not stripped:
                continue

            try:
                yield line_number, json.loads(stripped)
            except json.JSONDecodeError as exc:
                print(
                    f"Warning: skipped invalid JSON at {path}:{line_number}: {exc}",
                    file=sys.stderr,
                )


def convert_file(
    path: Path,
    *,
    system_prompt: Optional[str] = None,
    include_tools: bool = False,
    merge_consecutive: bool = True,
) -> Dict[str, Any]:
    """Convert one JSONL file into one ChatML conversation object."""
    messages: List[Dict[str, str]] = []

    if system_prompt:
        messages.append({"role": "system", "content": system_prompt.strip()})

    for _, record in read_jsonl_records(path):
        extracted = extract_messages_from_record(record, include_tools=include_tools)
        messages.extend(extracted)

    if merge_consecutive:
        messages = merge_consecutive_messages(messages)

    return {
        "source": str(path),
        "messages": messages,
    }


def collect_input_files(input_path: Path) -> List[Path]:
    """Collect JSONL files from a file or directory input."""
    if input_path.is_file():
        return [input_path]

    if input_path.is_dir():
        return sorted(input_path.rglob("*.jsonl"))

    raise FileNotFoundError(f"Input path does not exist: {input_path}")


def write_json(path: Path, data: Any, pretty: bool = True) -> None:
    """Write JSON to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        if pretty:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")
        else:
            json.dump(data, file, ensure_ascii=False, separators=(",", ":"))


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert Codex session JSONL files to ChatML JSON for OpenCode.",
    )

    parser.add_argument(
        "input",
        help="Input .jsonl file or directory containing .jsonl files.",
    )

    parser.add_argument(
        "output",
        help="Output .json file.",
    )

    parser.add_argument(
        "--system",
        default=None,
        help="Optional system prompt to prepend to every conversation.",
    )

    parser.add_argument(
        "--include-tools",
        action="store_true",
        help="Include tool/function outputs as role='tool' messages when detected.",
    )

    parser.add_argument(
        "--no-merge-consecutive",
        action="store_true",
        help="Do not merge adjacent messages with the same role.",
    )

    parser.add_argument(
        "--compact",
        action="store_true",
        help="Write compact JSON instead of pretty-printed JSON.",
    )

    parser.add_argument(
        "--object",
        action="store_true",
        help="If converting one file, output a single object instead of a list containing one object.",
    )

    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    input_path = Path(args.input).expanduser()
    output_path = Path(args.output).expanduser()

    try:
        files = collect_input_files(input_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not files:
        print(f"Error: no .jsonl files found in {input_path}", file=sys.stderr)
        return 1

    conversations = [
        convert_file(
            file_path,
            system_prompt=args.system,
            include_tools=args.include_tools,
            merge_consecutive=not args.no_merge_consecutive,
        )
        for file_path in files
    ]

    if args.object and len(conversations) == 1:
        output_data: Any = conversations[0]
    else:
        output_data = conversations

    write_json(output_path, output_data, pretty=not args.compact)

    total_messages = sum(len(conversation["messages"]) for conversation in conversations)

    print(f"Converted {len(files)} file(s)")
    print(f"Extracted {total_messages} message(s)")
    print(f"Wrote {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
