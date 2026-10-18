"""Read object names from Business Central .app symbol packages (the files in .alpackages)."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

# SymbolReference.json collection -> AL permission keyword(s) it resolves.
SYMBOL_COLLECTIONS = {
    "Tables": ("table", "tabledata"),
    "Pages": ("page",),
    "Codeunits": ("codeunit",),
    "Reports": ("report",),
    "Queries": ("query",),
    "XmlPorts": ("xmlport",),
}

NAVX_HEADER_SIZE = 40

ObjectNames = dict[tuple[str, int], str]


def _collect(node: dict, names: ObjectNames) -> None:
    for collection, object_types in SYMBOL_COLLECTIONS.items():
        for obj in node.get(collection) or []:
            for object_type in object_types:
                names.setdefault((object_type, int(obj["Id"])), obj["Name"])
    for namespace in node.get("Namespaces") or []:  # BC24+ nests objects by namespace
        _collect(namespace, names)


def read_app(data: bytes) -> ObjectNames:
    """Return {(object type, id): name} for one .app file's bytes."""
    if data[:4] == b"NAVX":
        data = data[NAVX_HEADER_SIZE:]
    with zipfile.ZipFile(io.BytesIO(data)) as package:
        raw = package.read("SymbolReference.json").decode("utf-8-sig")
    # Some packages carry trailing bytes after the JSON document; read the first document only.
    symbols, _ = json.JSONDecoder().raw_decode(raw.lstrip())
    names: ObjectNames = {}
    _collect(symbols, names)
    return names


def read_table_list(text: str, is_json: bool) -> ObjectNames:
    """Read a custom table name list: JSON {"50100": "My Table"} or CSV lines '50100,My Table'."""
    if is_json:
        pairs = json.loads(text.lstrip("﻿")).items()
    else:
        pairs = (line.split(",", 1) for line in text.lstrip("﻿").splitlines() if "," in line)
    names: ObjectNames = {}
    for object_id, name in pairs:
        object_id, name = str(object_id).strip(), str(name).strip().strip('"')
        if object_id.isdigit() and name:
            names[("table", int(object_id))] = name
            names[("tabledata", int(object_id))] = name
    return names


def read_names_file(path: Path) -> ObjectNames:
    suffix = path.suffix.lower()
    if suffix == ".app":
        return read_app(path.read_bytes())
    return read_table_list(path.read_text(encoding="utf-8-sig"), suffix == ".json")


def load_symbols(paths: list[Path]) -> tuple[ObjectNames, list[str]]:
    """Load .app symbol files and custom .json/.csv table lists (files or folders).

    Earlier sources win when two define the same object.
    """
    names: ObjectNames = {}
    errors = []
    for path in paths:
        files = sorted(f for f in path.iterdir() if f.suffix.lower() in (".app", ".json", ".csv")) \
            if path.is_dir() else [path]
        for app in files:
            try:
                for key, name in read_names_file(app).items():
                    names.setdefault(key, name)
            except zipfile.BadZipFile:
                errors.append(f"{app.name} has no readable symbols (runtime/encrypted package?). "
                              "Download symbols for it, or its objects stay as IDs.")
            except (KeyError, ValueError) as error:
                errors.append(f"Could not read symbols from {app.name}: {error}")
    return names, errors
