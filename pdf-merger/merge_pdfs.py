"""
Combine every PDF inside a folder (and all of its subfolders) into ONE PDF.

- Double-click "Merge PDFs.bat" (or this file) and pick the top folder,
  or drag a folder onto "Merge PDFs.bat".
- Files are ordered folder by folder, in natural order (2 before 10).
- The output gets bookmarks that mirror the folder tree, so it is easy to
  navigate in Bluebeam Revu (Bookmarks panel).
- Damaged or password-protected files are skipped and listed in a log.
"""

import os
import re
import sys
import time
import traceback
from datetime import datetime

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    print("The 'pypdf' package is missing. Install it with:  pip install pypdf")
    input("Press Enter to close...")
    sys.exit(1)

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
except ImportError:  # running without a GUI toolkit
    tk = None

OUTPUT_TAG = "_COMBINED_"


def natural_key(text):
    """Sort 'Sheet 2' before 'Sheet 10'."""
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", text)]


def collect_pdfs(root):
    """Return PDF paths under root, walking folders in natural order."""
    pdfs = []
    for folder, subdirs, files in os.walk(root):
        subdirs.sort(key=natural_key)
        for name in sorted(files, key=natural_key):
            if name.lower().endswith(".pdf") and OUTPUT_TAG not in name:
                pdfs.append(os.path.join(folder, name))
    return pdfs


def merge(root, output_path, progress=print):
    writer = PdfWriter()
    folder_bookmarks = {}  # relative folder path -> bookmark object
    skipped = []
    total_pages = 0

    pdfs = collect_pdfs(root)
    if not pdfs:
        return 0, 0, skipped

    for index, path in enumerate(pdfs, start=1):
        rel = os.path.relpath(path, root)
        progress(f"[{index}/{len(pdfs)}] {rel}")
        try:
            reader = PdfReader(path)
            if reader.is_encrypted:
                # Many "secured" PDFs open with an empty password.
                if not reader.decrypt(""):
                    raise ValueError("password protected")
            page_count = len(reader.pages)
            if page_count == 0:
                raise ValueError("no pages")
            start_page = len(writer.pages)
            writer.append(reader, import_outline=False)
        except Exception as exc:
            skipped.append(f"{rel}  ->  {exc}")
            continue

        # Build one bookmark per folder level, then one per file.
        parent = None
        parts = os.path.dirname(rel).split(os.sep) if os.path.dirname(rel) else []
        for depth in range(len(parts)):
            key = os.sep.join(parts[:depth + 1])
            if key not in folder_bookmarks:
                folder_bookmarks[key] = writer.add_outline_item(
                    parts[depth], start_page, parent=parent)
            parent = folder_bookmarks[key]
        title = os.path.splitext(os.path.basename(rel))[0]
        writer.add_outline_item(title, start_page, parent=parent)
        total_pages += page_count

    progress("Saving combined file, please wait...")
    writer.page_mode = "/UseOutlines"  # open with the bookmarks panel showing
    with open(output_path, "wb") as handle:
        writer.write(handle)

    merged = len(pdfs) - len(skipped)
    return merged, total_pages, skipped


def pick_folder():
    if tk is None:
        return input("Paste the folder path and press Enter: ").strip().strip('"')
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    folder = filedialog.askdirectory(title="Select the TOP folder that contains the PDFs")
    root.destroy()
    return folder


def notify(title, message, error=False):
    print(f"\n{title}\n{message}")
    if tk is None:
        return
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    (messagebox.showerror if error else messagebox.showinfo)(title, message)
    root.destroy()


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else pick_folder()
    if not folder:
        print("No folder selected. Nothing to do.")
        return
    folder = os.path.abspath(folder)
    if not os.path.isdir(folder):
        notify("Merge PDFs", f"Not a folder:\n{folder}", error=True)
        return

    name = os.path.basename(folder.rstrip("\\/")) or "PDFs"
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    output_path = os.path.join(folder, f"{name}{OUTPUT_TAG}{stamp}.pdf")

    print(f"Folder : {folder}\nOutput : {output_path}\n")
    started = time.time()
    merged, pages, skipped = merge(folder, output_path)

    if merged == 0:
        if os.path.exists(output_path):
            os.remove(output_path)
        notify("Merge PDFs", "No readable PDF files were found in that folder.", error=True)
        return

    message = (f"Combined {merged} PDF(s), {pages} page(s) in "
               f"{time.time() - started:.0f} s.\n\nSaved as:\n{output_path}")
    if skipped:
        log_path = os.path.splitext(output_path)[0] + "_SKIPPED.txt"
        with open(log_path, "w", encoding="utf-8") as log:
            log.write("\n".join(skipped))
        message += f"\n\n{len(skipped)} file(s) skipped - see:\n{log_path}"

    notify("Merge PDFs - Done", message)
    if os.name == "nt":
        os.startfile(output_path)  # opens in the default PDF app (Bluebeam Revu)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        input("\nSomething went wrong. Press Enter to close...")
