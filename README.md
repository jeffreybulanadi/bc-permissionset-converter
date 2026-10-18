# bc-permissionset-converter

Convert Business Central **XML permission set exports** (`PermissionSet` / `TenantPermissionSet`) into **AL `permissionset` objects** you can ship in an extension.

Useful when migrating from C/AL or user-defined permission sets to code-based permissions.

## For consultants: no install needed

**Use it online:** https://jeffreybulanadi.github.io/bc-permissionset-converter/ (runs in your browser, files never leave your computer)

Or offline:

1. Open `web/index.html` in your browser (double-click it).
2. Drag in your exported XML files.
3. Drag in the `.app` files from your project's `.alpackages` folder, so the output uses **object names** (`tabledata "G/L Entry"`) instead of IDs. For apps without symbols, add a `.csv` (`50100,My Table`) or `.json` table list.
4. Set the first object ID, tick the options you want, and click **Download all**.

Your files never leave your computer.

## Features

- One `.al` file per permission set (handles multiple sets per XML file)
- Direct and indirect permissions (`Yes` → `R`, `Indirect` → `r`) in RIMDX order
- Respects `Assignable`, escapes captions, sorts permissions by object type and ID
- Configurable start object ID and name prefix
- Warns, instead of silently mis-converting, on `Exclude` entries, unsupported types (e.g. MenuSuite) and names longer than 30 characters
- No dependencies, Python 3.9+

## Usage

```bash
pip install .
bc-permissionset-converter samples/input -o output --start-id 50100 --prefix "ABC "
bc-permissionset-converter samples/input --table-execute --custom-tables "50100-50120,50150" --custom-mask RIMD
bc-permissionset-converter exports/ --table-execute --symbols .alpackages --symbols isv-tables.json
# or without installing
python -m bc_permissionset_converter samples/input -o output   # run from src/
```

## Example

Input:

```xml
<TenantPermissionSet RoleID="SALES SUPPORT EXT" RoleName="Sales Support's Ext" Assignable="Yes">
  <TenantPermission>
    <ObjectType>Table Data</ObjectType>
    <ObjectID>18</ObjectID>
    <ReadPermission>Yes</ReadPermission>
    <ModifyPermission>Indirect</ModifyPermission>
  </TenantPermission>
  ...
```

Output (`SalesSupportExt.PermissionSet.al`):

```al
permissionset 50000 "SALES SUPPORT EXT"
{
    Caption = 'Sales Support''s Ext';
    Assignable = true;
    Permissions =
        tabledata 18 = Rm,
        tabledata 36 = RIMD,
        page 42 = X;
}
```

## Tests

```bash
pip install pytest
pytest
```

## Roadmap

- VS Code extension: right-click an XML file → *Convert to AL Permission Set*

## License

MIT
