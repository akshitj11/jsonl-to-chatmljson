# jsonl-to-chatmljson

Convert Codex session `.jsonl` files into ChatML-style JSON so they can be used with tools such as OpenCode.

## Why this exists

Codex stores session history as `.jsonl` files, often under a path like:

`C:\Users\YourName\.codex\sessions\2026\04\26\rollout-....jsonl`

This project converts those JSONL records into a simpler ChatML JSON structure:

[
  {
    "source": "path/to/session.jsonl",
    "messages": [
      {
        "role": "user",
        "content": "..."
      },
      {
        "role": "assistant",
        "content": "..."
      }
    ]
  }
]

## Features

- Converts one `.jsonl` file.
- Converts a whole directory of `.jsonl` files.
- Supports Codex-style session events.
- Supports common chat dataset formats:
  - `messages`
  - `prompt` / `completion`
  - `prompt` / `response`
  - `instruction` / `output`
  - `question` / `answer`
- Can add a system prompt to every conversation.
- Can optionally preserve detected tool outputs.

## Requirements

- Python 3.8 or newer

No third-party Python packages are required.

## Usage

From this repo folder:

`python jsonl_to_chatmljson.py INPUT OUTPUT`

### Convert one Codex session file

PowerShell example:

`python .\jsonl_to_chatmljson.py "C:\Users\Vijender Joshi\.codex\sessions\2026\04\26\rollout-2026-04-26T01-25-07-019dc635-ca93-79a0-b1eb-cc0bc1e9cd49.jsonl" ".\chatml-output.json"`

### Convert a whole Codex sessions directory

`python .\jsonl_to_chatmljson.py "C:\Users\Vijender Joshi\.codex\sessions" ".\all-codex-sessions-chatml.json"`

### Add a system prompt

`python .\jsonl_to_chatmljson.py input.jsonl output.json --system "You are a helpful assistant."`

### Include tool outputs

By default, the converter focuses on user and assistant text. To include detected tool/function outputs:

`python .\jsonl_to_chatmljson.py input.jsonl output.json --include-tools`

### Output one object instead of an array

If you are converting one file and want:

`{"source": "...", "messages": [...]}`

instead of:

`[{"source": "...", "messages": [...]}]`

run:

`python .\jsonl_to_chatmljson.py input.jsonl output.json --object`

### Compact output

`python .\jsonl_to_chatmljson.py input.jsonl output.json --compact`

## Example input

A Codex-style JSONL file may contain records like:

```examples/codex-session-sample.jsonl#L1-3
{"timestamp":"2026-04-26T01:25:07Z","type":"session_meta","payload":{"id":"example"}}
{"timestamp":"2026-04-26T01:25:08Z","type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"Create a hello world script"}]}}
{"timestamp":"2026-04-26T01:25:09Z","type":"response_item","payload":{"type":"message","role":"assistant","content":[{"type":"output_text","text":"Sure. Here is a simple hello world script."}]}}
