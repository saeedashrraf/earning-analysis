"""Parse a 10-K .htm file into blocks: one paragraph or one table each.

Usage: python src/rag/parse_10k.py data/AAPL/10-K_2026-11-03.htm
"""

import argparse
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

# A real section heading on a single line, such as "Item 7. Management's Discussion ..."
# Some companies put it in a one-row table, which reads as "Item 7. | Management's ..."
# Table-of-contents entries never match: they are rows inside one large table.
ITEM_HEADING = re.compile(r"^(Item \d+[A-C]?)\.[\s|]+(.+)$")
CORE_SECTIONS = json.loads((Path(__file__).parent / "core_sections.json").read_text())["10-K"]
PAGE_HEADER = "Table of Contents"  # a link some reports repeat at the top of every page
MAX_FOOTER_WORDS = 12
MAX_HEADING_WORDS = 40  # longer bold or italic text is a paragraph, not a heading


def clean(text: str) -> str:
    """Collapse runs of spaces and odd whitespace into single spaces."""
    return " ".join(text.split())


def merge_symbols(cells: list[str]) -> list[str]:
    """Join a lone "$" to the number after it, and a lone "%" to the number before."""
    merged = []
    prefix = ""
    for cell in cells:
        if cell == "$":
            prefix = "$"
        elif cell == "%" and merged:
            merged[-1] += "%"
        else:
            merged.append(prefix + cell)
            prefix = ""
    return merged


def is_emphasised(tag) -> bool:
    """True if all of the tag's text is bold or italic, which is how headings are styled."""
    styles = [span.get("style", "") for span in tag.find_all("span") if span.get_text().strip()]
    return bool(styles) and all(
        "font-weight:700" in style or "font-style:italic" in style for style in styles
    )


def html_to_blocks(file: Path) -> list[dict]:
    """Return the report's headings, paragraphs and tables, in reading order."""
    soup = BeautifulSoup(file.read_text(encoding="utf-8"), "html.parser")

    # Drop the hidden block of machine-readable metadata
    for hidden in soup.select('[style*="display:none"]'):
        hidden.decompose()

    blocks = []
    for tag in soup.find_all(["div", "table", "hr"]):
        if tag.find_parent("table"):
            continue  # already covered by its table

        if tag.name == "hr":
            if "page-break" in tag.get("style", ""):
                blocks.append({"type": "page_break", "text": ""})
            continue

        if tag.name == "table":
            rows = []
            for tr in tag.find_all("tr"):
                cells = [clean(td.get_text()) for td in tr.find_all("td")]
                cells = merge_symbols([cell for cell in cells if cell])
                if cells:
                    rows.append(" | ".join(cells))
            if rows:
                blocks.append({"type": "table", "text": "\n".join(rows)})

        elif not tag.find(["div", "table"]):  # a div holding text, not other divs
            text = clean(tag.get_text())
            if text:
                is_heading = is_emphasised(tag) and len(text.split()) <= MAX_HEADING_WORDS
                blocks.append({"type": "heading" if is_heading else "text", "text": text})

    return blocks


def label_pages(blocks: list[dict]) -> list[dict]:
    """Tag each block with its page's footer, then drop footers and headers.

    The footer is the last block before a page break, kept exactly as printed,
    such as "Apple Inc. | 2026 Form 10-K | 21" or just "21".
    """
    labeled, page = [], []
    for block in blocks + [{"type": "page_break", "text": ""}]:  # the last page ends too
        if block["type"] != "page_break":
            page.append(block)
            continue

        footer = ""
        if page:
            last = page[-1]["text"]
            if last[-1].isdigit() and len(last.split()) <= MAX_FOOTER_WORDS:
                footer = last
                page = page[:-1]
        if page and page[0]["text"] == PAGE_HEADER:
            page = page[1:]
        labeled += [{**b, "page": footer} for b in page]
        page = []
    return labeled


def label_sections(blocks: list[dict]) -> list[dict]:
    """Tag each paragraph and table with its Item and its nearest sub-heading.

    Headings become labels on the blocks below them and are not returned.
    """
    section, title, sub_heading = "Cover", "Cover page and table of contents", ""
    labeled = []
    for block in blocks:
        # Items are found by their text alone, so they never depend on styling.
        # The pattern must cover the whole block, so the table of contents
        # (many rows in one table) never matches, while a heading laid out as
        # a one-row table does.
        item = ITEM_HEADING.match(block["text"])
        if item:
            section, title = item.groups()
            sub_heading = ""  # a new Item starts with no sub-heading
            continue
        if block["type"] == "heading":
            sub_heading = block["text"]
            continue
        labeled.append({**block, "section": section, "section_title": title,
                        "sub_heading": sub_heading})
    return labeled


def save_reports(blocks: list[dict], file: Path, core_sections: list[str]) -> Path:
    """Write full_report.jsonl (every block) and core_report.jsonl (core sections only)."""
    company = file.parent.name            # data/AAPL/10-K_2026-11-03.htm -> AAPL
    report_date = file.stem.split("_")[-1]  # -> 2026-11-03
    folder = file.parent / f"parsed_{report_date}"
    folder.mkdir(exist_ok=True)

    # Labels first and text last, so each line reads like a citation plus its content
    keys = ["section", "section_title", "sub_heading", "page", "type", "text"]
    blocks = [{"company": company, **{key: block[key] for key in keys}} for block in blocks]
    core = [block for block in blocks if block["section"] in core_sections]
    for name, rows in (("full_report.jsonl", blocks), ("core_report.jsonl", core)):
        lines = [json.dumps(row, ensure_ascii=False) for row in rows]
        (folder / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Saved {len(blocks)} blocks to full_report.jsonl and {len(core)} to core_report.jsonl")
    return folder


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse a 10-K .htm file into blocks.")
    parser.add_argument("file", type=Path, help="path to the downloaded 10-K")
    file = parser.parse_args().file

    blocks = html_to_blocks(file)
    blocks = label_pages(blocks)
    blocks = label_sections(blocks)
    folder = save_reports(blocks, file, CORE_SECTIONS)
    print(f"Output folder: {folder}")


if __name__ == "__main__":
    main()
