# jsonl-to-chatmljson

Convert JSONL chat logs to strict OpenCode-compatible ChatML JSON.

## Output contract

This tool always writes a single JSON object:

```json
{
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

Rules enforced by converter:

- role must be one of `system`, `user`, `assistant`
- content must resolve to non-empty string
- malformed lines are skipped with warning, or fail in `--strict` mode
- metadata fields are dropped
- message order is preserved
- if system cleanup is enabled, all system messages are moved to top
- multiple files are flattened into one `messages` array

## Requirements

- Python 3.8+

## CLI

```bash
python -m jsonl2chatml input.jsonl -o output.json
```

Compatible legacy entrypoint:

```bash
python jsonl_to_chatmljson.py input.jsonl -o output.json
```

### Options

- `--strict` fail on malformed JSON or skipped non-message record
- `--no-system-cleanup` keep original position of system messages
- `--pretty` pretty-print JSON output
- `--markdown PATH` export transcript as Markdown

### Multiple input files

```bash
python -m jsonl2chatml a.jsonl b.jsonl -o merged.json
```

### Input directory

```bash
python -m jsonl2chatml C:\Users\YourName\.codex\sessions -o merged.json
```

## Examples

- Input: `examples/input/sample_mixed.jsonl`
- Output JSON: `examples/output/sample_output.json`
- Output Markdown: `examples/output/sample_transcript.md`

## Tests

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```
