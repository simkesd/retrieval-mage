"""Extract the FOI Code of Practice into the text shape this project chunks.

Pdfplumber geometry, as in the line-and-footnote extractor, with the project's
own cleanup: start at the Foreword, turn bullets into ``-``, and write footnote
markers as ^N with the note after the sentence that cites it.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict, deque
from pathlib import Path

import pdfplumber

# Wrapped body lines sit about 2pt apart; a new paragraph is closer to 15pt.
_LINE_BAND = 4
_PARAGRAPH_GAP_RATIO = 0.9
# Superscripts are several points smaller than the body and sit just above it.
_MARKER_SIZE_DROP = 3
_MARKER_ABOVE = (2, 6)
# The folio sits about 14pt below the lowest footnote label. 0.89 of the page
# height lands in that gap, clear of both.
_PAGE_NUMBER_TOP = 0.89
_LABEL_MARGIN = 0.15

_SENTENCE_END = ".!?"


class _Block:
    def __init__(self, text: str, heading: bool) -> None:
        self.text = text
        self.heading = heading


def extract(file_location: str | Path) -> tuple[Path, Path]:
    """Write ``<stem>-raw.txt`` and ``<stem>-clean.txt`` beside the PDF."""
    source = Path(file_location)
    raw_path = source.with_name(f"{source.stem}-raw.txt")
    clean_path = source.with_name(f"{source.stem}-clean.txt")
    raw, clean = extract_text(source)
    raw_path.write_text(raw, encoding="utf-8")
    clean_path.write_text(clean, encoding="utf-8")
    return raw_path, clean_path


def extract_text(file_location: str | Path) -> tuple[str, str]:
    """Return ``(raw_page_text, cleaned_text)`` for a PDF."""
    source = Path(file_location)
    raw_pages: list[str] = []
    pages: list[list[_Block]] = []
    notes: dict[str, deque[str]] = defaultdict(deque)

    with pdfplumber.open(source) as pdf:
        for page in pdf.pages:
            raw_pages.append(page.extract_text() or "")
            page_blocks, page_notes = _clean_page(page)
            pages.append(page_blocks)
            for number, text in page_notes:
                notes[number].append(text)

    raw = "\n".join(raw_pages)
    clean = _render(pages, notes)
    return raw, clean


def _clean_page(page) -> tuple[list[_Block], list[tuple[str, str]]]:
    words = _words(page)
    if not words:
        return [], []

    body_size = _body_size(words)
    paragraph_gap = body_size * _PARAGRAPH_GAP_RATIO
    marker_size = body_size - _MARKER_SIZE_DROP
    page_number_top = page.height * _PAGE_NUMBER_TOP
    label_margin = page.width * _LABEL_MARGIN

    # A folio is any digit in the footer band. On a sparse page the folio can
    # be the modal "body" size, so size is not a reliable test.
    page_number_ids = {
        id(word)
        for word in words
        if word["top"] > page_number_top and word["text"].isdigit()
    }
    labels = [
        word
        for word in words
        if word["size"] < marker_size
        and word["x0"] < label_margin
        and word["text"].isdigit()
        and id(word) not in page_number_ids
    ]
    markers = [
        word
        for word in words
        if word["size"] < marker_size
        and word["text"].isdigit()
        and word not in labels
        and id(word) not in page_number_ids
    ]
    notes, footnote_ids = _footnotes(words, labels, page_number_ids, marker_size)
    body = [
        word
        for word in words
        if id(word) not in page_number_ids
        and id(word) not in footnote_ids
        and word not in markers
    ]
    return _blocks(body, markers, paragraph_gap), notes


def _words(page) -> list[dict]:
    words = []
    for word in page.extract_words(extra_attrs=["size", "fontname"]) or []:
        text = (
            word["text"]
            .replace("\u200b", "")
            .replace("\xa0", "")
            .replace("\ufeff", "")
            .strip()
        )
        if not text:
            continue
        if text == "●":
            text = "-"
        word["text"] = text
        words.append(word)
    return words


def _body_size(words) -> float:
    """Modal size of body copy. Display faces on a title page are not the mode."""
    bodyish = [
        round(word["size"], 1)
        for word in words
        if 9.0 <= word["size"] <= 16.0
        and len(word["text"]) > 1
        and not word["text"].isdigit()
    ]
    sizes = bodyish or [round(word["size"], 1) for word in words]
    return Counter(sizes).most_common(1)[0][0]


def _footnotes(words, labels, page_number_ids, marker_size) -> tuple[list[tuple[str, str]], set[int]]:
    notes = []
    footnote_ids = {id(label) for label in labels}
    if not labels:
        return notes, footnote_ids

    labels = sorted(labels, key=lambda word: word["top"])
    for index, label in enumerate(labels):
        next_top = labels[index + 1]["top"] if index + 1 < len(labels) else 10**9
        note_words = [
            word
            for word in words
            if label["top"] - 2 <= word["top"] < next_top
            and id(word) not in page_number_ids
            and word is not label
            and not (word["size"] < marker_size and word["text"].isdigit())
        ]
        footnote_ids.update(id(word) for word in note_words)
        text = _join_lines(_line_texts(_lines(note_words)))
        if text:
            notes.append((label["text"], text))
    return notes, footnote_ids


def _blocks(words, markers, paragraph_gap: float) -> list[_Block]:
    lines = _lines(words)
    for marker in markers:
        line = _line_for_marker(lines, marker)
        if line is None:
            continue
        line["words"].append({**marker, "text": f"^{marker['text']}"})
        line["words"].sort(key=lambda word: word["x0"])

    blocks = []
    current = []
    for line in lines:
        starts_new = _starts_new_line(line)
        heading_changed = current and _is_heading_line(line) != _is_heading(current)
        gap = current and line["top"] - current[-1]["bottom"] > paragraph_gap
        if current and (starts_new or heading_changed or gap):
            blocks.append(_block_from(current))
            current = []
        current.append(line)
    if current:
        blocks.append(_block_from(current))
    return [block for block in blocks if block.text and not _is_placeholder(block.text)]


def _lines(words) -> list[dict]:
    lines = []
    for word in sorted(words, key=lambda item: (item["top"], item["x0"])):
        if lines and word["top"] - lines[-1]["top"] <= _LINE_BAND:
            lines[-1]["words"].append(word)
            lines[-1]["bottom"] = max(lines[-1]["bottom"], word["bottom"])
        else:
            lines.append({
                "top": word["top"],
                "bottom": word["bottom"],
                "words": [word],
            })
    for line in lines:
        line["words"].sort(key=lambda word: word["x0"])
    return lines


def _line_for_marker(lines, marker):
    low, high = _MARKER_ABOVE
    for line in lines:
        if low <= line["top"] - marker["top"] <= high:
            return line
    return None


def _starts_new_line(line) -> bool:
    first = line["words"][0]["text"]
    if first == "-":
        return True
    # A section number starts a paragraph. A wrapped "2.12 above" does not.
    if re.fullmatch(r"\d+\.\d+", first) and len(line["words"]) > 1:
        return line["words"][1]["text"][:1].isupper()
    return False


def _is_heading_line(line) -> bool:
    words = [word for word in line["words"] if word["text"] not in {"-", "^"}]
    if not words:
        return False
    if any(word["size"] >= 18 for word in words):
        return True
    return all("Light" not in word["fontname"] for word in words)


def _is_heading(lines) -> bool:
    return any(_is_heading_line(line) for line in lines)


def _block_from(lines) -> _Block:
    return _Block(_join_lines(_line_texts(lines)), _is_heading(lines))


def _line_texts(lines) -> list[str]:
    return [
        _join_tokens(word["text"] for word in line["words"])
        for line in lines
        if line["words"]
    ]


def _join_tokens(tokens) -> str:
    text = ""
    for token in tokens:
        if not text:
            text = token
        elif token.startswith("^") or token[:1] in ",.;:!?)]}":
            text += token
        else:
            text += f" {token}"
    return text


def _join_lines(lines: list[str]) -> str:
    text = ""
    for line in lines:
        if not text:
            text = line
        elif _split_url(text, line):
            text += line
        elif text.endswith("-") and line[:1].islower():
            text = text[:-1] + line
        else:
            text = f"{text} {line}"
    return re.sub(r" {2,}", " ", text).strip()


def _split_url(text: str, line: str) -> bool:
    if not line[:1].islower() or ("http" not in text and "www." not in text):
        return False
    # Join only when the address itself was cut. A normal word after it keeps its space.
    return re.search(r"\s\w+$", text) is None or text[-1] in "/-._~%"


def _is_placeholder(text: str) -> bool:
    return "printed publications" in text


def _render(pages: list[list[_Block]], notes: dict[str, deque[str]]) -> str:
    paragraphs = []
    for block in _merge_pages(pages):
        text = _place_notes(block.text, notes)
        text = re.sub(r"(https?://\S+)]", r"\1", text)
        text = re.sub(r"(\d)\s+\*", r"\1*", text)
        text = re.sub(r" +", " ", text)
        text = re.sub(r" +([,.;:!?])", r"\1", text)
        text = text.strip()
        if text:
            paragraphs.append(text)
    cleaned = "\n\n".join(paragraphs) + "\n"
    return _strip_front_matter(cleaned)


def _merge_pages(pages: list[list[_Block]]) -> list[_Block]:
    merged = []
    for blocks in pages:
        if not blocks:
            continue
        if merged and _continues(merged[-1], blocks[0]):
            merged[-1].text = _join_lines([merged[-1].text, blocks[0].text])
            blocks = blocks[1:]
        merged.extend(blocks)
    return merged


def _continues(previous: _Block, block: _Block) -> bool:
    if previous.heading or block.heading or _ends_sentence(previous.text):
        return False
    return not re.match(r"(\d+\.\d+|- )", block.text)


def _ends_sentence(text: str) -> bool:
    trimmed = text.rstrip(" \t\"'”’)]")
    return trimmed.endswith(tuple(_SENTENCE_END))


def _place_notes(paragraph: str, notes: dict[str, deque[str]]) -> str:
    """Keep ^N on the cited word and put [note N] after that sentence.

    The note is its own paragraph so the chunker can keep it with the citing
    passage, and a following heading still sees a line that ends a sentence.
    """
    paragraph = re.sub(r"([.!?])(\^\d+)", r"\2\1", paragraph)
    parts: list[str] = []
    pending: list[str] = []
    buffer: list[str] = []
    index = 0
    while index < len(paragraph):
        marker = re.match(r"\^(\d+)", paragraph[index:])
        if marker and notes.get(marker.group(1)):
            pending.append(marker.group(1))
            buffer.append(marker.group(0))
            index += marker.end()
            continue
        if marker and not notes.get(marker.group(1)):
            index += marker.end()
            continue
        buffer.append(paragraph[index])
        if paragraph[index] in _SENTENCE_END and pending and _sentence_boundary(paragraph, index):
            _flush(parts, buffer, pending, notes)
        index += 1
    _flush(parts, buffer, pending, notes)
    return "\n\n".join(part for part in parts if part)


def _flush(parts, buffer, pending, notes) -> None:
    sentence = "".join(buffer).strip()
    buffer.clear()
    if sentence:
        parts.append(sentence)
    for number in pending:
        if not notes[number]:
            continue
        parts.append(f"[note {number}] {notes[number].popleft()}")
    pending.clear()


def _sentence_boundary(text: str, index: int) -> bool:
    rest = text[index + 1:]
    return rest.strip() == "" or re.match(r"\s+[A-Z\[“\"(]", rest) is not None


def _strip_front_matter(text: str) -> str:
    """Drop the title pages and contents. Keep the real Foreword onward."""
    match = re.search(
        r"(?m)^Foreword\n\n(?=Freedom of Information is one of the pillars)",
        text,
    )
    if match:
        text = text[match.start():]
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"
