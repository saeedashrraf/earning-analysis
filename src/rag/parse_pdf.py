"""Parse an annual report PDF into blocks: one paragraph or one table each.

Usage: python src/rag/parse_pdf.py data/SIEGY/annual-report_2025-12-03.pdf
"""

import argparse
import json
from collections import Counter
from pathlib import Path

import pdfplumber
from pypdf import PdfReader

from parse_10k import save_reports

CORE_SECTIONS = json.loads((Path(__file__).parent / "core_sections.json").read_text())

HEADER_BOTTOM, FOOTER_TOP = 45, 790  # the strips holding page headers and footers
BODY_SHARE = 0.15       # body text is the largest font used by at least this share of lines
PARAGRAPH_GAP = 1.5     # a gap above this many font sizes starts a new paragraph
COLUMN_GAP = 1.0        # a horizontal gap above this many font sizes separates two columns
WORD_GAP = 0.15         # a smaller gap above this is a space between words
TABLE_COLUMNS = 3       # a line with this many columns is a table row at any font size
MIN_CHAPTERS = 3        # a heading size must appear this often to count as the chapter level
SKIP_HEADINGS = ("Table of contents", "Table of reports")


def split_cells(chars: list[dict]) -> list[str]:
    """Split a line into columns, using the horizontal gaps between its characters.

    A gap wider than one font size separates two columns; a small gap is a space.
    """
    cells, last = [""], None
    for char in chars:
        gap = char["x0"] - last["x1"] if last else 0
        if gap > COLUMN_GAP * char["size"]:
            cells.append("")
        elif gap > WORD_GAP * char["size"]:
            cells[-1] += " "
        cells[-1] += char["text"]
        last = char
    return [cell.strip() for cell in cells if cell.strip()]


def pdf_to_lines(file: Path) -> list[dict]:
    """Return every line of text with its font size, position and columns."""
    lines = []
    with pdfplumber.open(file) as pdf:
        for pdf_page, page in enumerate(pdf.pages, start=1):
            for line in page.extract_text_lines():
                # The line's font size is its most common one, so a small
                # footnote mark at the start does not mislead us
                sizes = Counter(round(char["size"], 1) for char in line["chars"])
                cells = split_cells(line["chars"])
                lines.append({
                    "pdf_page": pdf_page,
                    "top": round(line["top"]),  # distance from the top of the page
                    "size": sizes.most_common(1)[0][0],
                    "text": " ".join(cells),
                    "cells": cells,
                })
    return lines


def report_starts(file: Path) -> list[tuple[int, str]]:
    """Return (first page, name) for each report inside the PDF, from its bookmarks."""
    reader = PdfReader(file)
    if reader.is_encrypted:
        reader.decrypt("")
    return [(reader.get_destination_page_number(mark) + 1, mark.title)
            for mark in reader.outline if not isinstance(mark, list)]


def label_sections(lines: list[dict], starts: list[tuple[int, str]]) -> list[dict]:
    """Tag each line with the report it belongs to, and drop page headers and footers."""
    labeled = []
    for line in lines:
        if not HEADER_BOTTOM <= line["top"] < FOOTER_TOP:
            continue
        names = [name for first_page, name in starts if first_page <= line["pdf_page"]]
        labeled.append({**line, "section": names[-1] if names else "Cover"})
    return labeled


def body_sizes(lines: list[dict]) -> dict[str, float]:
    """Return each report's body font size. The reports were typeset separately."""
    counts: dict[str, Counter] = {}
    for line in lines:
        counts.setdefault(line["section"], Counter())[line["size"]] += 1
    return {section: max(size for size, n in sizes.items()
                         if n >= BODY_SHARE * sum(sizes.values()))
            for section, sizes in counts.items()}


def lines_to_blocks(lines: list[dict]) -> list[dict]:
    """Join lines into headings, paragraphs and tables, using font size."""
    body = body_sizes(lines)
    blocks = []
    for line in lines:
        size = line["size"]
        is_row = size < body[line["section"]] or len(line["cells"]) >= TABLE_COLUMNS
        kind = "table" if is_row else "heading" if size > body[line["section"]] else "text"
        text = " | ".join(line["cells"]) if kind == "table" else line["text"]

        last = blocks[-1] if blocks else None
        same_place = (last and last["type"] == kind
                      and last["pdf_page"] == line["pdf_page"])
        close = same_place and line["top"] - last["bottom"] <= PARAGRAPH_GAP * size
        if same_place and (kind == "table" or (close and last["size"] == size)):
            # Table rows stay on their own lines; other lines flow together
            last["text"] += ("\n" if kind == "table" else " ") + text
            last["bottom"] = line["top"]
        else:
            blocks.append({"type": kind, "text": text, "size": size,
                           "section": line["section"], "pdf_page": line["pdf_page"],
                           "bottom": line["top"]})
    return blocks


def chapter_sizes(blocks: list[dict], title_pages: set[int]) -> dict[str, float]:
    """Return each report's chapter heading size: its largest recurring heading size."""
    counts: dict[str, Counter] = {}
    for block in blocks:
        if block["type"] == "heading" and block["pdf_page"] not in title_pages:
            counts.setdefault(block["section"], Counter())[block["size"]] += 1
    return {section: max((size for size, n in sizes.items() if n >= MIN_CHAPTERS), default=0)
            for section, sizes in counts.items()}


def label_blocks(blocks: list[dict], starts: list[tuple[int, str]]) -> list[dict]:
    """Tag each paragraph and table with its chapter, sub-heading and page.

    Headings become labels on the blocks below them and are not returned.
    """
    title_pages = {first_page for first_page, name in starts}
    chapter_size = chapter_sizes(blocks, title_pages)
    section, chapter, sub_heading = None, "", ""
    labeled = []
    for block in blocks:
        if block["section"] != section:  # a new report starts with no headings
            section, chapter, sub_heading = block["section"], "", ""

        if block["type"] == "heading":
            if block["pdf_page"] in title_pages:
                continue  # the report's title page repeats its name in large type
            if block["size"] == chapter_size.get(section):
                chapter, sub_heading = block["text"], ""
            else:
                sub_heading = block["text"]
            continue

        if sub_heading in SKIP_HEADINGS:
            continue  # a table of contents is not content
        labeled.append({"type": block["type"], "text": block["text"],
                        "section": section, "section_title": chapter or section,
                        "sub_heading": sub_heading, "page": str(block["pdf_page"])})
    return labeled


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse an annual report PDF into blocks.")
    parser.add_argument("file", type=Path, help="path to the downloaded PDF")
    file = parser.parse_args().file

    starts = report_starts(file)
    lines = pdf_to_lines(file)
    lines = label_sections(lines, starts)
    blocks = lines_to_blocks(lines)
    blocks = label_blocks(blocks, starts)
    folder = save_reports(blocks, file, CORE_SECTIONS[file.parent.name])
    print(f"Output folder: {folder}")


if __name__ == "__main__":
    main()
