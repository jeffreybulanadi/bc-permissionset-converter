# BC Permission Set Converter

Turn the permission sets you built in Business Central into AL code, in about two minutes.

**Use it here:** https://jeffreybulanadi.github.io/bc-permissionset-converter/

Nothing to install. It runs in your browser, and your files never leave your computer.

---

## Why would I need this?

You (or your client) built permission sets by hand in Business Central. Now you want them inside your extension, so they're saved with your code and installed with your app.

Doing that by hand means retyping hundreds of lines. This tool does it for you.

## How to use it

**1. Export your permission sets from Business Central**

Search for **Permission Sets**, select the ones you want, and choose **Export Permission Sets**. You'll get an XML file.

Got them in Excel instead? That works too. Open a permission set, export its permissions to Excel, and save it as a `.csv` file. Each CSV becomes one permission set, named after the file, so name the file the way you want the permission set to be called.

**2. Drop the XML or CSV files into the tool**

**3. Drop in your `.alpackages` files** *(optional, but you'll want this)*

These are the `.app` files in your AL project's `.alpackages` folder. With them, the tool writes real table names instead of numbers:

```al
tabledata 17 = RIMD              // without
tabledata "G/L Entry" = RIMD     // with
```

Some add-on apps don't include their names. If you see numbers left over, add a simple list like this as a `.csv` file:

```
50100,My Custom Table
50101,Another Table
```

**4. Pick your options and click Download**

- **First object ID**: the number your first permission set should get, for example 50100.
- **Name prefix**: optional, for example your company's 3-letter prefix.
- **Also give Execute on the table**: leave it ticked unless you know you don't need it.
- **Custom tables**: your own table numbers, like `50100-50120`, if you want them added to every permission set.

Copy the downloaded `.al` files into your project, and you're done.

## What you get

```al
permissionset 50100 "SALES SUPPORT"
{
    Caption = 'Sales Support', Locked = true;
    Assignable = true;
    Permissions =
        table Customer = X,
        tabledata Customer = R,
        table "Sales Header" = X,
        tabledata "Sales Header" = RIMD,
        page "Sales Order" = X;
}
```

## Things the tool will warn you about

The tool doesn't hide problems. It tells you when:

- **A line said "Exclude".** AL handles that differently, so the tool skips it and you'll need to set it up yourself.
- **A line was a MenuSuite.** Those don't exist in AL anymore, so it's safely skipped.
- **A name was too long.** AL allows 30 characters, so the name was shortened.
- **A table name couldn't be found.** It stays as a number. Add that app's `.app` file or a `.csv` list to fix it.

---

## For developers

Prefer the command line? There's a Python version with the same features. It needs Python 3.9 or newer and nothing else.

```bash
pip install .
bc-permissionset-converter my-exports/ --symbols .alpackages --table-execute --start-id 50100
```

Run `bc-permissionset-converter --help` to see every option. To run the tests: `pip install pytest`, then `pytest`.

## Coming soon

A VS Code extension: right-click an XML file and choose **Convert to AL Permission Set**.

## License

MIT. Free to use, change and share.
