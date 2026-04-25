import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from jsonl2chatml.converter import ConversionError, convert_inputs


def _write(path: Path, lines):
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class ConverterTests(unittest.TestCase):
    def test_malformed_json_skips_non_strict(self):
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "a.jsonl"
            _write(
                source,
                [
                    '{"role":"user","content":"hello"}',
                    '{"role":"assistant","content":"ok"',
                    '{"role":"assistant","content":"done"}',
                ],
            )
            data, warnings = convert_inputs([str(source)])
            self.assertEqual(len(data["messages"]), 2)
            self.assertGreaterEqual(len(warnings), 1)

    def test_malformed_json_fails_strict(self):
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "a.jsonl"
            _write(source, ['{"role":"user","content":"hello"}', '{bad'])
            with self.assertRaises(ConversionError):
                convert_inputs([str(source)], strict=True)

    def test_mixed_metadata_and_empty_content(self):
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "a.jsonl"
            _write(
                source,
                [
                    '{"timestamp":"x","tokens":1}',
                    '{"role":"user","content":"   "}',
                    '{"role":"user","content":"hi"}',
                    '{"role":"assistant","content":"yo"}',
                    '{"role":"assistant","content":null}',
                ],
            )
            data, _ = convert_inputs([str(source)])
            self.assertEqual(
                data,
                {
                    "messages": [
                        {"role": "user", "content": "hi"},
                        {"role": "assistant", "content": "yo"},
                    ]
                },
            )

    def test_system_cleanup_order(self):
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "a.jsonl"
            _write(
                source,
                [
                    '{"role":"user","content":"u1"}',
                    '{"role":"system","content":"s1"}',
                    '{"role":"assistant","content":"a1"}',
                    '{"role":"system","content":"s2"}',
                ],
            )
            data, _ = convert_inputs([str(source)])
            self.assertEqual(
                [m["role"] for m in data["messages"]],
                ["system", "system", "user", "assistant"],
            )

    def test_messages_array_and_multi_file_flatten(self):
        with TemporaryDirectory() as tmp:
            source1 = Path(tmp) / "a.jsonl"
            source2 = Path(tmp) / "b.jsonl"
            _write(source1, ['{"messages":[{"role":"user","content":"one"}]}'])
            _write(source2, ['{"role":"assistant","content":"two"}'])
            data, _ = convert_inputs([str(source1), str(source2)])
            self.assertEqual(
                data,
                {
                    "messages": [
                        {"role": "user", "content": "one"},
                        {"role": "assistant", "content": "two"},
                    ]
                },
            )
            json.dumps(data)

    def test_codex_payload_message_content_array(self):
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "a.jsonl"
            _write(
                source,
                [
                    '{"type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"Create script"}]}}',
                    '{"type":"response_item","payload":{"type":"message","role":"assistant","content":[{"type":"output_text","text":"Done"}]}}',
                ],
            )
            data, _ = convert_inputs([str(source)])
            self.assertEqual(
                data,
                {
                    "messages": [
                        {"role": "user", "content": "Create script"},
                        {"role": "assistant", "content": "Done"},
                    ]
                },
            )


if __name__ == "__main__":
    unittest.main()
