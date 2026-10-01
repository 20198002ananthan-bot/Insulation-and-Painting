"""
Combine every PDF inside a folder (and all of its subfolders) into ONE PDF.

- Double-click "Merge PDFs.bat" (or this file) and pick the top folder,
  or drag a folder onto "Merge PDFs.bat".
- Built for large jobs (1000+ PDFs): files are merged in batches so Windows
  never runs out of open-file handles or memory.
- Handles long Windows paths (> 260 characters), secured/encrypted PDFs
  (e.g. Bluebeam "Secured" files without an open password) and
  slightly damaged PDFs (auto-repair, with a second PDF engine as fallback).
- Files are ordered folder by folder, in natural order (2 before 10).
- The output gets bookmarks that mirror the folder tree (Bluebeam Bookmarks panel).
- A report (_REPORT.txt) lists every file found, merged or skipped.

Needs:  pip install pikepdf pypdf cryptography   (Merge PDFs.bat does it for you)
"""

import io
import os
import re
import shutil
import sys
import tempfile
import time
import traceback
from datetime import datetime

try:
    import pikepdf
    from pikepdf import OutlineItem
except ImportError:
    print("The 'pikepdf' package is missing. Install it with:\n"
          "    pip install pikepdf pypdf cryptography")
    input("Press Enter to close...")
    sys.exit(1)

try:  # second engine, used only for files pikepdf cannot open
    from pypdf import PdfReader, PdfWriter
except ImportError:
    PdfReader = PdfWriter = None

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
except ImportError:  # running without a GUI toolkit
    tk = None

OUTPUT_TAG = "_COMBINED_"
BATCH_SIZE = 100  # PDFs held open at once; keeps Windows file-handle use low


# ----------------------------------------------------------------- helpers
def long_path(path):
    """Allow Windows paths longer than 260 characters."""
    path = os.path.abspath(path)
    if os.name != "nt" or path.startswith("\\\\?\\"):
        return path
    if path.startswith("\\\\"):  # network share \\server\share
        return "\\\\?\\UNC\\" + path[2:]
    return "\\\\?\\" + path


def natural_key(text):
    """Sort 'Sheet 2' before 'Sheet 10'."""
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", text)]


def collect_pdfs(root, problems):
    """Return (full_path, relative_path) for every PDF under root."""
    pdfs = []

    def on_error(err):  # folders Windows refuses to list are reported, not hidden
        problems.append(f"FOLDER NOT READABLE: {getattr(err, 'filename', '')}  ->  {err}")

    walk_root = long_path(root)
    for folder, subdirs, files in os.walk(walk_root, onerror=on_error):
        subdirs.sort(key=natural_key)
        for name in sorted(files, key=natural_key):
            if name.lower().endswith(".pdf") and OUTPUT_TAG not in name:
                full = os.path.join(folder, name)
                pdfs.append((full, os.path.relpath(full, walk_root)))
    return pdfs


def open_pdf(path):
    """Open a PDF with pikepdf; fall back to pypdf for stubborn files."""
    try:
        return pikepdf.open(path, password="")
    except pikepdf.PasswordError:
        raise ValueError("needs an OPEN password - remove security in Bluebeam first")
    except Exception as first_error:
        if PdfReader is None:
            raise
        try:  # rebuild the file with pypdf, then hand it to pikepdf
            reader = PdfReader(path, strict=False)
            if reader.is_encrypted and not reader.decrypt(""):
                raise ValueError("password protected")
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            buffer = io.BytesIO()
            writer.write(buffer)
            buffer.seek(0)
            return pikepdf.open(buffer)
        except Exception as second_error:
            raise ValueError(f"{first_error} / {second_error}")


# ------------------------------------------------------------------- merge
def merge(root, output_path, progress=print):
    problems = []
    pdfs = collect_pdfs(root, problems)
    entries = []  # (relative path, first page index, page count)
    if not pdfs:
        return pdfs, entries, problems

    temp_dir = tempfile.mkdtemp(prefix="merge_pdfs_")
    try:
        # Stage 1: merge in batches into temporary part files.
        part_files = []
        page_offset = 0
        for batch_start in range(0, len(pdfs), BATCH_SIZE):
            batch = pdfs[batch_start:batch_start + BATCH_SIZE]
            part = pikepdf.new()
            opened = []
            for number, (full, rel) in enumerate(batch, start=batch_start + 1):
                progress(f"[{number}/{len(pdfs)}] {rel}")
                try:
                    src = open_pdf(full)
                    count = len(src.pages)
                    if count == 0:
                        src.close()
                        raise ValueError("no pages")
                    part.pages.extend(src.pages)
                    opened.append(src)
                    entries.append((rel, page_offset, count))
                    page_offset += count
                except Exception as exc:
                    problems.append(f"SKIPPED: {rel}  ->  {exc}")
            if len(part.pages):
                part_path = os.path.join(temp_dir, f"part_{len(part_files):04d}.pdf")
                part.save(part_path)
                part_files.append(part_path)
            part.close()
            for src in opened:
                src.close()

        if not entries:
            return pdfs, entries, problems

        # Stage 2: join the parts and add bookmarks.
        progress(f"Joining {len(part_files)} batch file(s)...")
        final = pikepdf.new()
        parts = [pikepdf.open(p) for p in part_files]
        for part in parts:
            final.pages.extend(part.pages)

        progress("Adding bookmarks...")
        with final.open_outline() as outline:
            folder_items = {}
            for rel, first_page, _ in entries:
                folder_path = os.path.dirname(rel)
                parent_list = outline.root
                if folder_path:
                    names = folder_path.split(os.sep)
                    for depth in range(len(names)):
                        key = os.sep.join(names[:depth + 1])
                        if key not in folder_items:
                            item = OutlineItem(names[depth], first_page)
                            parent_list.append(item)
                            folder_items[key] = item
                        parent_list = folder_items[key].children
                title = os.path.splitext(os.path.basename(rel))[0]
                parent_list.append(OutlineItem(title, first_page))

        final.Root.PageMode = pikepdf.Name.UseOutlines  # open with bookmarks shown
        progress("Saving combined file, please wait (large jobs can take a few minutes)...")
        final.save(long_path(output_path),
                   object_stream_mode=pikepdf.ObjectStreamMode.generate)
        final.close()
        for part in parts:
            part.close()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return pdfs, entries, problems


# ---------------------------------------------------------------------- UI
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


def write_report(path, folder, pdfs, entries, problems):
    with open(long_path(path), "w", encoding="utf-8") as rep:
        rep.write(f"Folder        : {folder}\n")
        rep.write(f"PDFs found    : {len(pdfs)}\n")
        rep.write(f"PDFs merged   : {len(entries)}\n")
        rep.write(f"Pages merged  : {sum(e[2] for e in entries)}\n")
        rep.write(f"Problems      : {len(problems)}\n\n")
        if problems:
            rep.write("=== PROBLEMS ===\n" + "\n".join(problems) + "\n\n")
        rep.write("=== MERGED (start page, pages, file) ===\n")
        for rel, first, count in entries:
            rep.write(f"{first + 1:>7}  {count:>5}  {rel}\n")


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else pick_folder()
    if not folder:
        print("No folder selected. Nothing to do.")
        return
    folder = os.path.abspath(folder.strip('"'))
    if not os.path.isdir(long_path(folder)):
        notify("Merge PDFs", f"Not a folder:\n{folder}", error=True)
        return

    name = os.path.basename(folder.rstrip("\\/")) or "PDFs"
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    output_path = os.path.join(folder, f"{name}{OUTPUT_TAG}{stamp}.pdf")
    report_path = os.path.splitext(output_path)[0] + "_REPORT.txt"

    print(f"Folder : {folder}\nOutput : {output_path}\n")
    started = time.time()
    pdfs, entries, problems = merge(folder, output_path)
    write_report(report_path, folder, pdfs, entries, problems)

    if not entries:
        notify("Merge PDFs",
               f"No readable PDF files were merged.\n\nFound: {len(pdfs)}\n"
               f"See report:\n{report_path}", error=True)
        return

    pages = sum(e[2] for e in entries)
    message = (f"PDFs found : {len(pdfs)}\nPDFs merged: {len(entries)}\n"
               f"Pages      : {pages}\nTime       : {time.time() - started:.0f} s\n\n"
               f"Saved as:\n{output_path}\n\nReport:\n{report_path}")
    if problems:
        message += f"\n\n{len(problems)} problem(s) - see the report."
    notify("Merge PDFs - Done", message, error=bool(problems))
    if os.name == "nt":
        os.startfile(output_path)  # opens in the default PDF app (Bluebeam Revu)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        input("\nSomething went wrong. Press Enter to close...")
