# Merge PDFs (folder + all subfolders → one PDF)

## One-time setup (Windows)
1. Install Python from https://www.python.org/downloads/ – tick **"Add python.exe to PATH"**.
2. Keep `Merge PDFs.bat` and `merge_pdfs.py` together in the same folder.
   (`pikepdf`, `pypdf` and `cryptography` install themselves the first time you run it.)

## Use
- **Double-click `Merge PDFs.bat`** → pick the top folder → done, **or**
- **Drag a folder onto `Merge PDFs.bat`**.

The result `<FolderName>_COMBINED_<date_time>.pdf` is saved inside the chosen folder
and opens automatically in your default PDF app (Bluebeam Revu).

## What it does
- Walks every subfolder; orders folders/files naturally (`Sheet 2` before `Sheet 10`).
- Adds bookmarks that mirror the folder tree (Bluebeam ▸ Bookmarks panel).
- Handles 1000+ PDFs (merges in batches of 100), Windows paths over 260 characters,
  Bluebeam-secured PDFs without an open password, and repairs slightly damaged files.
- Writes `..._REPORT.txt`: PDFs found vs merged, start page of every file, and any skipped file with the reason.
- Ignores earlier `_COMBINED_` outputs, so re-running never merges the old result in.

Tip: in Bluebeam you can then run **Document ▸ Pages ▸ Page Labels** or **Batch ▸ Flatten** on the combined file if needed.
