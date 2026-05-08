from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


DATASET = "Contextbench/ContextBench"
DEFAULT_CONFIG = "contextbench_verified"
DEFAULT_SPLIT = "train"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a small ContextBench sample from Hugging Face to JSONL.")
    parser.add_argument("--output", required=True, help="Destination JSONL path.")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="Dataset config.")
    parser.add_argument("--split", default=DEFAULT_SPLIT, help="Dataset split.")
    parser.add_argument("--offset", type=int, default=0, help="Starting row offset.")
    parser.add_argument("--length", type=int, default=10, help="Number of rows to export.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = fetch_rows(config=args.config, split=args.split, offset=args.offset, length=args.length)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    print(f"wrote {len(rows)} rows to {output}")


def fetch_rows(*, config: str, split: str, offset: int, length: int) -> list[dict]:
    params = urlencode(
        {
            "dataset": DATASET,
            "config": config,
            "split": split,
            "offset": offset,
            "length": length,
        }
    )
    url = f"https://datasets-server.huggingface.co/rows?{params}"
    with urlopen(url, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return [item["row"] for item in payload.get("rows", [])]


if __name__ == "__main__":
    main()
