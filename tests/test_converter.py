import io
import json
import zipfile
from pathlib import Path

from bc_permissionset_converter.converter import convert, parse_ids, parse_xml, render_al, to_file_name
from bc_permissionset_converter.symbols import load_symbols

SAMPLE = Path(__file__).parent.parent / "samples" / "input" / "SampleRoles.xml"


def make_app(path: Path, symbols: dict) -> Path:
    """Build a minimal .app: 40-byte NAVX header + zip containing SymbolReference.json."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as package:
        package.writestr("SymbolReference.json", "﻿" + json.dumps(symbols))
    path.write_bytes(b"NAVX" + (40).to_bytes(4, "little") + bytes(32) + buffer.getvalue())
    return path


def test_parses_every_set_in_one_file():
    sets = parse_xml(SAMPLE)
    assert [s.role_id for s in sets] == ["SALES SUPPORT EXT", "WAREHOUSE VIEW"]


def test_masks():
    sales = parse_xml(SAMPLE)[0]
    assert sorted(p.to_al() for p in sales.permissions) == [
        "page 42 = X",
        "tabledata 18 = Rm",
        "tabledata 36 = RIMD",
    ]


def test_exclude_and_menusuite_are_skipped_with_warning():
    sales, warehouse = parse_xml(SAMPLE)
    assert any("Exclude" in w for w in sales.warnings)
    assert any("MenuSuite" in w for w in warehouse.warnings)


def test_render_escapes_caption_and_respects_assignable():
    sales, warehouse = parse_xml(SAMPLE)
    assert "Caption = 'Sales Support''s Ext', Locked = true;" in render_al(sales, 50000)
    assert "Assignable = false;" in render_al(warehouse, 50001)


def test_one_file_per_set(tmp_path):
    written = convert([SAMPLE], tmp_path, start_id=50100)
    assert sorted(p.name for p, _ in written) == [
        "SalesSupportExt.PermissionSet.al",
        "WarehouseView.PermissionSet.al",
    ]
    assert 'permissionset 50101 "WAREHOUSE VIEW"' in (tmp_path / "WarehouseView.PermissionSet.al").read_text()


def test_parse_ids():
    assert parse_ids("50100-50102, 50150") == [50100, 50101, 50102, 50150]
    assert parse_ids("50101..50100") == [50100, 50101]


def test_custom_tables_and_table_execute(tmp_path):
    convert([SAMPLE], tmp_path, custom_tables=[50100, 36], table_execute=True)
    content = (tmp_path / "WarehouseView.PermissionSet.al").read_text()
    assert "tabledata 50100 = RIMD" in content
    assert "table 32 = X" in content and "table 50100 = X" in content
    sales = (tmp_path / "SalesSupportExt.PermissionSet.al").read_text()
    assert sales.count("tabledata 36 =") == 1  # existing XML permission wins


def test_names_from_symbols(tmp_path):
    make_app(tmp_path / "Base.app", {
        "Tables": [{"Id": 18, "Name": "Customer"}],
        "Namespaces": [{"Name": "Microsoft.Sales", "Tables": [{"Id": 36, "Name": "Sales Header"}],
                        "Pages": [{"Id": 42, "Name": "Sales Order"}]}],
    })
    names, errors = load_symbols([tmp_path])
    assert not errors

    out = tmp_path / "out"
    written = convert([SAMPLE], out, table_execute=True, names=names)
    content = (out / "SalesSupportExt.PermissionSet.al").read_text()
    assert content.split("Permissions =\n")[1] == (
        "        table Customer = X,\n"
        "        tabledata Customer = Rm,\n"
        '        table "Sales Header" = X,\n'
        '        tabledata "Sales Header" = RIMD,\n'
        '        page "Sales Order" = X;\n'
        "}\n"
    )
    warehouse = dict((p.name, s) for p, s in written)["WarehouseView.PermissionSet.al"]
    assert any("tabledata 32" in w for w in warehouse.warnings)  # unresolved kept as ID


def test_custom_table_lists(tmp_path):
    (tmp_path / "isv.json").write_text('{"6010079": "PVS Userfield Field Buffer"}')
    (tmp_path / "mine.csv").write_text("50100,My Custom Table\n")
    names, errors = load_symbols([tmp_path])
    assert not errors
    assert names[("tabledata", 6010079)] == "PVS Userfield Field Buffer"
    assert names[("table", 50100)] == "My Custom Table"


def test_file_name():
    assert to_file_name("SALES ORDER-ENTRY") == "SalesOrderEntry.PermissionSet.al"


CSV_SAMPLE = SAMPLE.parent / "Accounts Payable.csv"


def test_csv_export_uses_names_from_file(tmp_path):
    written = convert([CSV_SAMPLE], tmp_path, table_execute=True)
    path, permission_set = written[0]
    assert path.name == "AccountsPayable.PermissionSet.al"
    assert not permission_set.warnings
    body = path.read_text().split("Permissions =\n")[1]
    assert body == (
        "        table Customer = X,\n"
        "        tabledata Customer = R,\n"
        "        table Vendor = X,\n"
        "        tabledata Vendor = RIMD,\n"
        '        table "Vendor Ledger Entry" = X,\n'
        '        tabledata "Vendor Ledger Entry" = Rim,\n'
        '        page "Vendor Card" = X;\n'
        "}\n"
    )


def test_csv_semicolon_and_bad_file(tmp_path):
    good = tmp_path / "Sales.csv"
    good.write_text("Object Type;Object ID;Object Name;Read Permission\nTable Data;36;Sales Header;Yes\n")
    assert "tabledata \"Sales Header\" = R" in convert([good], tmp_path / "o")[0][0].read_text()
    bad = tmp_path / "Other.csv"
    bad.write_text("a,b\n1,2\n")
    try:
        convert([bad], tmp_path / "o2")
        assert False, "expected ValueError"
    except ValueError as error:
        assert "Object Type" in str(error)
