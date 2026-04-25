import argparse
import sys

from .converter import ConversionError, convert_inputs, write_json, write_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jsonl2chatml")
    parser.add_argument("inputs", nargs="+", help="Input jsonl file(s) or directory")
    parser.add_argument("-o", "--output", required=True, help="Output JSON file")
    parser.add_argument("--strict", action="store_true", help="Fail on bad data")
    parser.add_argument("--no-system-cleanup", action="store_true", help="Keep original system position")
    parser.add_argument("--pretty", action="store_true", help="Pretty print output json")
    parser.add_argument("--markdown", help="Optional markdown transcript output path")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        data, warnings = convert_inputs(
            args.inputs,
            strict=args.strict,
            cleanup_system=not args.no_system_cleanup,
        )
    except ConversionError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)

    write_json(args.output, data, pretty=args.pretty)
    if args.markdown:
        write_markdown(args.markdown, data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
