from __future__ import annotations

import argparse

from quay.service.runtime import diagnose_incident


def main() -> None:
    parser = argparse.ArgumentParser(prog="quay")
    subparsers = parser.add_subparsers(dest="command", required=True)

    diagnose = subparsers.add_parser("diagnose")
    diagnose.add_argument("workspace")
    diagnose.add_argument("query")
    diagnose.add_argument("--mode", default="incident")
    diagnose.add_argument("--tenant", default="acme")

    args = parser.parse_args()
    if args.command == "diagnose":
        bundle = diagnose_incident(query=args.query, mode=args.mode, tenant_id=args.tenant)
        print(f"focus: {', '.join(bundle.focus_files)}")
        print(f"docs: {', '.join(bundle.docs)}")
        print(f"config: {', '.join(bundle.configs)}")


if __name__ == "__main__":
    main()
