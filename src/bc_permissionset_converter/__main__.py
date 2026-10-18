"""Command line entry point: python -m bc_permissionset_converter <input> [options]"""

import argparse
import sys
from pathlib import Path

from .converter import convert, parse_ids
from .symbols import load_symbols


def collect_inputs(path: Path) -> list[Path]:
    if path.is_dir():
        return sorted(p for p in path.iterdir() if p.suffix.lower() in (".xml", ".csv"))
    return [path]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bc-permissionset-converter",
        description="Convert Business Central XML/CSV permission sets to AL permissionset objects.",
    )
    parser.add_argument("input", type=Path, help="XML/CSV file, or a folder of them")
    parser.add_argument("-o", "--output", type=Path, default=Path("output"), help="output folder (default: ./output)")
    parser.add_argument("--start-id", type=int, default=50000, help="first object ID (default: 50000)")
    parser.add_argument("--prefix", default="", help="object name prefix, e.g. 'ABC '")
    parser.add_argument("--table-execute", action="store_true", help="add 'table N = X' for every tabledata entry")
    parser.add_argument("--custom-tables", default="", help="extra table IDs for every set, e.g. '50100-50120,50150'")
    parser.add_argument("--custom-mask", default="RIMD", help="permission for custom tables (default: RIMD)")
    parser.add_argument("--symbols", type=Path, action="append", default=[],
                        help="folder of .app symbol files (e.g. .alpackages) or one .app; repeatable. Writes names instead of IDs")
    args = parser.parse_args(argv)

    inputs = collect_inputs(args.input)
    if not inputs:
        print(f"No XML or CSV files found in {args.input}", file=sys.stderr)
        return 1

    try:
        custom_tables = parse_ids(args.custom_tables)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1

    names = None
    if args.symbols:
        names, errors = load_symbols(args.symbols)
        for error in errors:
            print(f"warning: {error}")
        print(f"Loaded {len(names)} object names from symbols")

    try:
        results = convert(
            inputs, args.output, args.start_id, args.prefix,
            custom_tables, args.custom_mask, args.table_execute, names,
        )
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    for target, permission_set in results:
        print(f"{target}  ({len(permission_set.permissions)} permissions)")
        for warning in permission_set.warnings:
            print(f"  warning: {warning}")
    print(f"Done: {len(results)} permission set(s) written to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
