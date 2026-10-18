"""Convert Business Central XML permission set exports into AL permissionset objects."""

from __future__ import annotations

import csv
import io
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

# XML <ObjectType> value (spaces removed, lower-cased) -> AL permission keyword.
OBJECT_TYPES: dict[str, str] = {
    "tabledata": "tabledata",
    "table": "table",
    "report": "report",
    "codeunit": "codeunit",
    "xmlport": "xmlport",
    "page": "page",
    "query": "query",
    "system": "system",
}

# Output order inside the Permissions property.
TYPE_ORDER = list(OBJECT_TYPES.values())

# XML element -> AL permission letter, in RIMDX order.
PERMISSION_FIELDS = [
    ("ReadPermission", "R"),
    ("InsertPermission", "I"),
    ("ModifyPermission", "M"),
    ("DeletePermission", "D"),
    ("ExecutePermission", "X"),
]

MAX_NAME_LENGTH = 30


IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def quote_name(name: str) -> str:
    """AL identifiers need double quotes unless they are a plain word, e.g. Customer vs "G/L Entry"."""
    return name if IDENTIFIER.fullmatch(name) else f'"{name}"'


@dataclass
class Permission:
    object_type: str
    object_id: int
    mask: str
    name: str | None = None

    def to_al(self) -> str:
        target = quote_name(self.name) if self.name else str(self.object_id)
        return f"{self.object_type} {target} = {self.mask}"

    def sort_key(self) -> tuple:
        # Tables first, then other types; 'table X' sits right above its 'tabledata' line.
        group = 0 if self.object_type in ("table", "tabledata") else TYPE_ORDER.index(self.object_type)
        return (group, self.name is None, (self.name or "").lower(), self.object_id, self.object_type != "table")


@dataclass
class PermissionSet:
    role_id: str
    role_name: str
    assignable: bool
    permissions: list[Permission] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def build_mask(element: ET.Element) -> str:
    """Return an AL permission mask: 'Yes' -> upper case (direct), 'Indirect' -> lower case."""
    mask = ""
    for tag, letter in PERMISSION_FIELDS:
        value = (element.findtext(tag) or "").strip().lower()
        if value == "yes":
            mask += letter
        elif value == "indirect":
            mask += letter.lower()
    return mask


def parse_permission(element: ET.Element, warnings: list[str]) -> Permission | None:
    raw_type = (element.findtext("ObjectType") or "").strip()
    raw_id = (element.findtext("ObjectID") or "").strip()
    permission_type = (element.findtext("PermissionType") or "Include").strip()

    object_type = OBJECT_TYPES.get(raw_type.replace(" ", "").lower())
    if object_type is None:
        warnings.append(f"Skipped unsupported object type '{raw_type}' (ID {raw_id}).")
        return None

    if permission_type.lower() == "exclude":
        warnings.append(
            f"Skipped Exclude entry {object_type} {raw_id}; "
            "model it with ExcludedPermissionSets or a separate set."
        )
        return None

    mask = build_mask(element)
    if not mask:
        return None

    return Permission(object_type, int(raw_id), mask)


CSV_PERMISSION_COLUMNS = [f"{tag[:-len('Permission')]} Permission" for tag, _ in PERMISSION_FIELDS]


def parse_csv(csv_path: Path) -> list[PermissionSet]:
    """Parse a permission set exported from the BC Permissions page to Excel/CSV.

    One permission set per file, named after the file. Columns: Object Type, Object ID,
    Object Name, Read/Insert/Modify/Delete/Execute Permission.
    """
    text = csv_path.read_text(encoding="utf-8-sig")
    header = text.splitlines()[0] if text else ""
    delimiter = max([",", ";", "\t"], key=header.count)
    rows = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    rows.fieldnames = [(f or "").strip() for f in rows.fieldnames or []]
    if "Object Type" not in rows.fieldnames or "Object ID" not in rows.fieldnames:
        raise ValueError(f"{csv_path.name} does not look like a permission set export "
                         "(needs 'Object Type' and 'Object ID' columns).")

    name = csv_path.stem.strip()
    permission_set = PermissionSet(role_id=name.upper(), role_name=name, assignable=True)
    for row in rows:
        raw_type = (row.get("Object Type") or "").strip()
        raw_id = (row.get("Object ID") or "").strip()
        if not raw_type and not raw_id:
            continue
        object_type = OBJECT_TYPES.get(raw_type.replace(" ", "").lower())
        if object_type is None or not raw_id.isdigit():
            permission_set.warnings.append(f"Skipped unsupported line '{raw_type} {raw_id}'.")
            continue
        mask = ""
        for column, (_, letter) in zip(CSV_PERMISSION_COLUMNS, PERMISSION_FIELDS):
            value = (row.get(column) or "").strip().lower()
            mask += letter if value == "yes" else letter.lower() if value == "indirect" else ""
        if mask:
            object_name = (row.get("Object Name") or "").strip() or None
            permission_set.permissions.append(Permission(object_type, int(raw_id), mask, object_name))
    return [permission_set]


def parse_file(path: Path) -> list[PermissionSet]:
    return parse_csv(path) if path.suffix.lower() == ".csv" else parse_xml(path)


def parse_xml(xml_path: Path) -> list[PermissionSet]:
    """Parse every PermissionSet / TenantPermissionSet in an exported XML file."""
    root = ET.parse(xml_path).getroot()
    result = []
    for set_element in root.findall("PermissionSet") + root.findall("TenantPermissionSet"):
        permission_set = PermissionSet(
            role_id=(set_element.get("RoleID") or "").strip(),
            role_name=(set_element.get("RoleName") or "").strip(),
            assignable=(set_element.get("Assignable", "Yes").lower() != "no"),
        )
        for element in list(set_element):
            if element.tag in ("Permission", "TenantPermission"):
                permission = parse_permission(element, permission_set.warnings)
                if permission:
                    permission_set.permissions.append(permission)
        result.append(permission_set)
    return result


def escape_al_string(value: str) -> str:
    return value.replace("'", "''")


def to_object_name(role_id: str, prefix: str = "") -> str:
    name = f"{prefix}{role_id}".replace('"', "")
    return name[:MAX_NAME_LENGTH]


def render_al(permission_set: PermissionSet, object_id: int, prefix: str = "") -> str:
    name = to_object_name(permission_set.role_id, prefix)
    lines = [
        f'permissionset {object_id} "{name}"',
        "{",
        f"    Caption = '{escape_al_string(permission_set.role_name or permission_set.role_id)}', Locked = true;",
        f"    Assignable = {str(permission_set.assignable).lower()};",
    ]
    if permission_set.permissions:
        lines.append("    Permissions =")
        body = [f"        {p.to_al()}" for p in permission_set.permissions]
        lines.append(",\n".join(body) + ";")
    lines.append("}")
    return "\n".join(lines) + "\n"


def to_file_name(role_id: str) -> str:
    """Microsoft-style file name, e.g. 'SALES SUPPORT' -> 'SalesSupport.PermissionSet.al'."""
    words = re.split(r"[^A-Za-z0-9]+", role_id)
    stem = "".join(w.capitalize() for w in words if w) or "PermissionSet"
    return f"{stem}.PermissionSet.al"


def parse_ids(value: str) -> list[int]:
    """Parse '50100-50120, 50150' (or '50100..50120') into a list of IDs."""
    ids = []
    for part in filter(None, re.split(r"[,;\s]+", value)):
        match = re.fullmatch(r"(\d+)(?:(?:-|\.\.)(\d+))?", part)
        if not match:
            raise ValueError(f"Invalid table ID or range: '{part}'")
        start, end = int(match[1]), int(match[2] or match[1])
        ids.extend(range(min(start, end), max(start, end) + 1))
    return ids


def apply_options(
    permission_set: PermissionSet,
    custom_tables: list[int],
    custom_mask: str,
    table_execute: bool,
    names: dict[tuple[str, int], str] | None = None,
) -> None:
    """Add custom tables, optionally 'table N = X' for every tabledata entry, and resolve object names."""
    existing = {(p.object_type, p.object_id) for p in permission_set.permissions}

    def add(object_type: str, object_id: int, mask: str, name: str | None = None) -> None:
        if (object_type, object_id) not in existing:
            existing.add((object_type, object_id))
            permission_set.permissions.append(Permission(object_type, object_id, mask, name))

    for table_id in custom_tables:
        add("tabledata", table_id, custom_mask)
    if table_execute:
        for p in [p for p in permission_set.permissions if p.object_type == "tabledata"]:
            add("table", p.object_id, "X", p.name)

    # Symbols win; a name that came with the file (CSV exports) is the fallback.
    names = names or {}
    unresolved = []
    for p in permission_set.permissions:
        p.name = names.get((p.object_type, p.object_id)) or p.name
        if p.name is None and p.object_type != "system":
            unresolved.append(f"{p.object_type} {p.object_id}")
    if unresolved and (names or any(p.name for p in permission_set.permissions)):
        permission_set.warnings.append("No name found, kept as ID: " + ", ".join(unresolved))

    permission_set.permissions.sort(key=Permission.sort_key)


def convert(
    inputs: list[Path],
    output_dir: Path,
    start_id: int = 50000,
    prefix: str = "",
    custom_tables: list[int] | None = None,
    custom_mask: str = "RIMD",
    table_execute: bool = False,
    names: dict[tuple[str, int], str] | None = None,
) -> list[tuple[Path, PermissionSet]]:
    """Convert XML/CSV files to AL files. Returns (written file, permission set) pairs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    next_id = start_id
    for input_path in inputs:
        for permission_set in parse_file(input_path):
            apply_options(permission_set, custom_tables or [], custom_mask, table_execute, names)
            if len(permission_set.role_id) + len(prefix) > MAX_NAME_LENGTH:
                permission_set.warnings.append(
                    f"Object name truncated to {MAX_NAME_LENGTH} characters."
                )
            target = output_dir / to_file_name(permission_set.role_id)
            target.write_text(render_al(permission_set, next_id, prefix), encoding="utf-8")
            written.append((target, permission_set))
            next_id += 1
    return written
