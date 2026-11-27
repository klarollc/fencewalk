"""Minimal, generic PDF 1.4 writer. Standard library only.

No report knowledge lives in this module: pages, text, wrapping,
tables, rules, footers. A caller builds a Document out of flow
elements (title, headings, paragraphs, tables) and calls build() for
the bytes. Output is deterministic: no timestamps anywhere, streams
compressed with zlib at a fixed level, object order fixed.

Fonts are the PDF standard 14, never embedded: Helvetica,
Helvetica-Bold, Courier, Courier-Bold, all in WinAnsiEncoding.
Character widths for the two Helvetica faces come from the Adobe AFM
metrics (phvr8a / phvb8a, as shipped with matplotlib); Courier is
fixed-width at 600 units. Text is measured with those widths, so
wrapping is measured against the real font, not an approximation.

A text run is a (text, font, size) triple; a drawn line carries one
color for all its runs. Tables may color individual cells (the
report uses amber for one status column); paragraphs are ink.
"""

import zlib

PAGE_WIDTH = 612
PAGE_HEIGHT = 792
MARGIN = 54
TEXT_WIDTH = PAGE_WIDTH - 2 * MARGIN  # 504

# DeviceRGB values. Ink #1F1F1F, hairline grey #999999, amber #9A6B1A.
INK = (0.122, 0.122, 0.122)
RULE_GREY = (0.6, 0.6, 0.6)
AMBER = (0.604, 0.420, 0.102)

# WinAnsi byte for each non-ASCII character the report can carry.
_WINANSI_EXTRA = {
    "…": 133,  # ellipsis
    "‘": 145,  # quoteleft
    "’": 146,  # quoteright
    "“": 147,  # quotedblleft
    "”": 148,  # quotedblright
    "•": 149,  # bullet
    "–": 150,  # endash
    "—": 151,  # emdash
    "·": 183,  # periodcentered
}

# Character widths in 1000-unit em space, keyed by WinAnsi byte code.
# Taken from the Adobe AFM metrics (see module docstring).
HELVETICA = {
    32: 278, 33: 278, 34: 355, 35: 556, 36: 556, 37: 889, 38: 667, 39: 222,
    40: 333, 41: 333, 42: 389, 43: 584, 44: 278, 45: 333, 46: 278, 47: 278,
    48: 556, 49: 556, 50: 556, 51: 556, 52: 556, 53: 556, 54: 556, 55: 556,
    56: 556, 57: 556, 58: 278, 59: 278, 60: 584, 61: 584, 62: 584, 63: 556,
    64: 1015, 65: 667, 66: 667, 67: 722, 68: 722, 69: 667, 70: 611, 71: 778,
    72: 722, 73: 278, 74: 500, 75: 667, 76: 556, 77: 833, 78: 722, 79: 778,
    80: 667, 81: 778, 82: 722, 83: 667, 84: 611, 85: 722, 86: 667, 87: 944,
    88: 667, 89: 667, 90: 611, 91: 278, 92: 278, 93: 278, 94: 469, 95: 556,
    96: 222, 97: 556, 98: 556, 99: 500, 100: 556, 101: 556, 102: 278, 103: 556,
    104: 556, 105: 222, 106: 222, 107: 500, 108: 222, 109: 833, 110: 556, 111: 556,
    112: 556, 113: 556, 114: 333, 115: 500, 116: 278, 117: 556, 118: 500, 119: 722,
    120: 500, 121: 500, 122: 500, 123: 334, 124: 260, 125: 334, 126: 584, 133: 1000,
    145: 222, 146: 222, 147: 333, 148: 333, 149: 350, 150: 556, 151: 1000, 183: 278,
}
HELVETICA_BOLD = {
    32: 278, 33: 333, 34: 474, 35: 556, 36: 556, 37: 889, 38: 722, 39: 278,
    40: 333, 41: 333, 42: 389, 43: 584, 44: 278, 45: 333, 46: 278, 47: 278,
    48: 556, 49: 556, 50: 556, 51: 556, 52: 556, 53: 556, 54: 556, 55: 556,
    56: 556, 57: 556, 58: 333, 59: 333, 60: 584, 61: 584, 62: 584, 63: 611,
    64: 975, 65: 722, 66: 722, 67: 722, 68: 722, 69: 667, 70: 611, 71: 778,
    72: 722, 73: 278, 74: 556, 75: 722, 76: 611, 77: 833, 78: 722, 79: 778,
    80: 667, 81: 778, 82: 722, 83: 667, 84: 611, 85: 722, 86: 667, 87: 944,
    88: 667, 89: 667, 90: 611, 91: 333, 92: 278, 93: 333, 94: 584, 95: 556,
    96: 278, 97: 556, 98: 611, 99: 556, 100: 611, 101: 556, 102: 333, 103: 611,
    104: 611, 105: 278, 106: 278, 107: 556, 108: 278, 109: 889, 110: 611, 111: 611,
    112: 611, 113: 611, 114: 389, 115: 556, 116: 333, 117: 611, 118: 556, 119: 778,
    120: 556, 121: 556, 122: 500, 123: 389, 124: 280, 125: 389, 126: 584, 133: 1000,
    145: 278, 146: 278, 147: 500, 148: 500, 149: 350, 150: 556, 151: 1000, 183: 278,
}

_FONTS = {
    "helvetica": ("Helvetica", HELVETICA),
    "helvetica-bold": ("Helvetica-Bold", HELVETICA_BOLD),
    "courier": ("Courier", None),  # fixed 600
    "courier-bold": ("Courier-Bold", None),  # fixed 600
}

_FONT_KEYS = {
    "helvetica": "F1",
    "helvetica-bold": "F2",
    "courier": "F3",
    "courier-bold": "F4",
}


def _winansi_bytes(text):
    """Encode text as WinAnsi bytes for a PDF literal string.

    ASCII passes through; the handful of non-ASCII characters the
    report uses map to their WinAnsi codes; anything else becomes '?'.
    The substitution is never silent: Document counts these
    characters (unrepresentable_count) and the report renderer
    discloses the count in the PDF.
    """
    out = bytearray()
    for ch in text:
        code = ord(ch)
        if 32 <= code <= 126:
            out.append(code)
        elif ch in _WINANSI_EXTRA:
            out.append(_WINANSI_EXTRA[ch])
        else:
            out.append(0x3F)
    return bytes(out)


def unrepresentable_count(text):
    """How many characters of text _winansi_bytes draws as '?'."""
    return sum(
        1 for ch in text
        if not (32 <= ord(ch) <= 126) and ch not in _WINANSI_EXTRA
    )


def _char_width(byte, table):
    if table is None:
        return 600
    return table.get(byte, 500)


def text_width(text, font, size):
    """Width of text in points at the given font and size."""
    table = _FONTS[font][1]
    total = sum(_char_width(b, table) for b in _winansi_bytes(text))
    return total * size / 1000.0


def _break_word(word, font, size, max_width):
    """Split one overlong word into pieces that each fit, by character."""
    pieces = []
    current = ""
    current_w = 0.0
    for ch in word:
        w = text_width(ch, font, size)
        if current and current_w + w > max_width:
            pieces.append(current)
            current, current_w = "", 0.0
        current += ch
        current_w += w
    if current:
        pieces.append(current)
    return pieces


def wrap_runs(runs, max_width):
    """Word-wrap a paragraph into lines.

    runs is a list of (text, font, size). Returns a list of lines, each
    a list of (text, font, size) segments. A token longer than the line
    breaks by character; there is no hyphenation. Every produced line
    measures within max_width.
    """
    words = []  # (text, font, size, width incl. trailing space)
    for text, font, size in runs:
        parts = text.split(" ")
        for i, part in enumerate(parts):
            if part == "":
                continue
            trailing = " " if i < len(parts) - 1 else ""
            width = text_width(part, font, size)
            if trailing:
                width += text_width(" ", font, size)
            words.append((part + trailing, font, size, width))
    lines = []
    current = []
    current_w = 0.0
    for word, font, size, width in words:
        if width > max_width:
            if current:
                lines.append(current)
                current, current_w = [], 0.0
            for piece in _break_word(word, font, size, max_width):
                piece_w = text_width(piece, font, size)
                if current and current_w + piece_w > max_width:
                    lines.append(current)
                    current, current_w = [], 0.0
                current.append((piece, font, size))
                current_w += piece_w
            continue
        if current and current_w + width > max_width:
            lines.append(current)
            current, current_w = [], 0.0
        current.append((word, font, size))
        current_w += width
    if current:
        lines.append(current)
    return lines


def _escape_literal(data):
    return data.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _fmt(number):
    return f"{number:.2f}"


def _rgb_command(color, stroke=False):
    op = "RG" if stroke else "rg"
    return f"{color[0]:.3f} {color[1]:.3f} {color[2]:.3f} {op}".encode()


class Document:
    """One PDF document, built from flow elements, laid out on demand."""

    # Footer sits below this line; content never goes below it.
    _CONTENT_BOTTOM = 60
    _FOOTER_RULE_Y = 48
    _FOOTER_TEXT_Y = 36

    def __init__(self, title, doc_id, footer_left):
        self.title = title
        self.doc_id = doc_id  # 64-hex string, content-bound by the caller
        self.footer_left = footer_left
        self._pages = [[]]  # list of op lists, one per page
        self._top = PAGE_HEIGHT - MARGIN  # top edge of the next block
        # Characters drawn as "?" (see _winansi_bytes), counted once per
        # flow element as it is added: a repeated table header or the
        # per-page footer is not counted again. The footer repeats the
        # title, which the caller also lays out as its title block.
        self.substitutions = 0

    # -- flow elements ---------------------------------------------------

    def title_block(self, text):
        self._flow_text([(text, "helvetica-bold", 16)], gap_after=10)

    def heading(self, text, level=1):
        if level == 1:
            self._top -= 12
            self._flow_text([(text, "helvetica-bold", 13)], gap_after=5)
        else:
            self._top -= 10
            self._flow_text([(text, "helvetica-bold", 11)], gap_after=4)

    def paragraph(self, runs, size=10, gap_after=4):
        self._flow_text(runs, size=size, gap_after=gap_after)

    def rule(self):
        self._top -= 3
        if self._top < self._CONTENT_BOTTOM:
            self._new_page()
            self._top -= 3
        self._pages[-1].append(
            ("line", MARGIN, self._top, MARGIN + TEXT_WIDTH, self._top, 0.5, RULE_GREY)
        )
        self._top -= 6

    def table(self, headers, rows, col_widths, size=9):
        """A table: headers and rows are lists of cells.

        A cell is (text, font, color) or a plain string (Helvetica, ink).
        The header row repeats on every page the table spans; a row that
        does not fit moves to the next page whole; a single row taller
        than one page may split.
        """
        leading = size * 1.2
        pad = 3
        xs = [MARGIN]
        for w in col_widths[:-1]:
            xs.append(xs[-1] + w)

        def cell_lines(cell, width):
            if isinstance(cell, str):
                text, font, color = cell, "helvetica", INK
            else:
                text, font, color = cell
            lines = wrap_runs([(text, font, size)], width - 4)
            return (lines, color)

        def row_height(cells, widths):
            wrapped = [cell_lines(c, w) for c, w in zip(cells, widths)]
            n = max(len(w[0]) for w in wrapped)
            return n * leading + 2 * pad, wrapped

        for cell in list(headers) + [c for row in rows for c in row]:
            text = cell if isinstance(cell, str) else cell[0]
            self.substitutions += unrepresentable_count(text)

        header_cells = [(h, "helvetica-bold", INK) for h in headers]
        header_h, header_wrapped = row_height(header_cells, col_widths)

        def draw_header():
            self._draw_row(header_wrapped, header_h, xs, leading, pad, size)
            rule_y = self._top
            self._pages[-1].append(
                ("line", MARGIN, rule_y, MARGIN + TEXT_WIDTH, rule_y, 0.5, RULE_GREY)
            )
            self._top -= 1

        # The header must fit on the current page (or the next one).
        if self._top - header_h < self._CONTENT_BOTTOM:
            self._new_page()
        draw_header()
        for row in rows:
            height, wrapped = row_height(row, col_widths)
            if height <= PAGE_HEIGHT - MARGIN - self._CONTENT_BOTTOM:
                if self._top - height < self._CONTENT_BOTTOM:
                    self._new_page()
                    draw_header()
                self._draw_row(wrapped, height, xs, leading, pad, size)
            else:
                # One row taller than a page: split it line by line.
                self._draw_split_row(wrapped, xs, leading, pad, size, draw_header)
        self._top -= 4

    # -- layout internals ------------------------------------------------

    def _new_page(self):
        self._pages.append([])
        self._top = PAGE_HEIGHT - MARGIN

    def _flow_text(self, runs, size=10, gap_after=4):
        self.substitutions += sum(
            unrepresentable_count(text) for text, _, _ in runs
        )
        block_size = max((s for _, _, s in runs), default=size)
        leading = block_size * 1.2
        lines = wrap_runs(runs, TEXT_WIDTH)
        for line in lines:
            if self._top - block_size < self._CONTENT_BOTTOM:
                self._new_page()
            baseline = self._top - block_size
            self._pages[-1].append(("text", MARGIN, baseline, line, INK))
            self._top -= leading
        self._top -= gap_after

    def _draw_row(self, wrapped, height, xs, leading, pad, size):
        # wrapped: per cell (lines, color); lines are run lists.
        top = self._top
        for (lines, color), x in zip(wrapped, xs):
            baseline = top - pad - size
            for line in lines:
                self._pages[-1].append(("text", x + 2, baseline, line, color))
                baseline -= leading
        self._top -= height

    def _draw_split_row(self, wrapped, xs, leading, pad, size, draw_header):
        # Draw the row's lines across pages, repeating the header.
        remaining = [list(w[0]) for w in wrapped]  # per-cell line queues
        colors = [w[1] for w in wrapped]
        while any(remaining):
            available = self._top - self._CONTENT_BOTTOM
            lines_fit = max(0, int((available - 2 * pad) // leading))
            if lines_fit == 0:
                self._new_page()
                draw_header()
                continue
            take = min(lines_fit, max(len(r) for r in remaining))
            for line_idx in range(take):
                baseline = self._top - pad - size - line_idx * leading
                for cell_idx, queue in enumerate(remaining):
                    if not queue:
                        continue
                    line = queue.pop(0)
                    self._pages[-1].append(
                        ("text", xs[cell_idx] + 2, baseline, line, colors[cell_idx])
                    )
            self._top -= take * leading + 2 * pad
            if any(remaining):
                self._new_page()
                draw_header()

    # -- serialization -----------------------------------------------------

    def _page_stream(self, ops, page_number):
        parts = []
        for op in ops:
            if op[0] == "text":
                _, x, baseline, line, color = op
                block = [b"BT"]
                cursor = x
                for text, font, size in line:
                    font_key = _FONT_KEYS[font]
                    encoded = _escape_literal(_winansi_bytes(text))
                    block.append(
                        f"/{font_key} {size} Tf ".encode()
                        + _rgb_command(color)
                        + f" 1 0 0 1 {_fmt(cursor)} {_fmt(baseline)} Tm ".encode()
                        + b"("
                        + encoded
                        + b") Tj"
                    )
                    cursor += text_width(text, font, size)
                block.append(b"ET")
                parts.append(b" ".join(block))
            elif op[0] == "line":
                _, x1, y1, x2, y2, width, color = op
                parts.append(
                    _rgb_command(color, stroke=True)
                    + f" {width} w {_fmt(x1)} {_fmt(y1)} m {_fmt(x2)} {_fmt(y2)} l S".encode()
                )
        # Footer: rule and text, on every page including the first.
        parts.append(
            _rgb_command(RULE_GREY, stroke=True)
            + f" 0.5 w {_fmt(MARGIN)} {_fmt(self._FOOTER_RULE_Y)} m {_fmt(MARGIN + TEXT_WIDTH)} {_fmt(self._FOOTER_RULE_Y)} l S".encode()
        )
        left = _escape_literal(_winansi_bytes(self.footer_left))
        right_text = f"Page {page_number}"
        right = _escape_literal(_winansi_bytes(right_text))
        right_w = text_width(right_text, "courier", 8)
        parts.append(
            b"BT /F3 8 Tf "
            + _rgb_command(INK)
            + f" 1 0 0 1 {_fmt(MARGIN)} {_fmt(self._FOOTER_TEXT_Y)} Tm ".encode()
            + b"("
            + left
            + b") Tj ET"
        )
        parts.append(
            b"BT /F3 8 Tf "
            + _rgb_command(INK)
            + f" 1 0 0 1 {_fmt(MARGIN + TEXT_WIDTH - right_w)} {_fmt(self._FOOTER_TEXT_Y)} Tm ".encode()
            + b"("
            + right
            + b") Tj ET"
        )
        return b"\n".join(parts)

    def build(self):
        """Serialize the document to PDF bytes."""
        n_pages = len(self._pages)
        # Object numbers: 1 catalog, 2 pages, 3-6 fonts, 7 info,
        # then per page: page object, content object.
        first_page_obj = 8
        page_obj = lambda i: first_page_obj + 2 * i
        content_obj = lambda i: first_page_obj + 2 * i + 1
        total_objects = first_page_obj + 2 * n_pages - 1

        kids = " ".join(f"{page_obj(i)} 0 R" for i in range(n_pages))
        objects = {}
        objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
        objects[2] = f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode()
        for num, base in (
            (3, "Helvetica"),
            (4, "Helvetica-Bold"),
            (5, "Courier"),
            (6, "Courier-Bold"),
        ):
            objects[num] = (
                f"<< /Type /Font /Subtype /Type1 /BaseFont /{base} "
                f"/Encoding /WinAnsiEncoding >>".encode()
            )
        title_esc = _escape_literal(_winansi_bytes(self.title))
        objects[7] = b"<< /Title (" + title_esc + b") /Producer (Fencewalk) >>"
        for i in range(n_pages):
            stream = self._page_stream(self._pages[i], i + 1)
            compressed = zlib.compress(stream, 9)
            objects[page_obj(i)] = (
                f"<< /Type /Page /Parent 2 0 R "
                f"/MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
                f"/Resources << /Font << /F1 3 0 R /F2 4 0 R "
                f"/F3 5 0 R /F4 6 0 R >> >> "
                f"/Contents {content_obj(i)} 0 R >>".encode()
            )
            objects[content_obj(i)] = (
                f"<< /Length {len(compressed)} /Filter /FlateDecode >>\n"
                f"stream\n".encode()
                + compressed
                + b"\nendstream"
            )

        out = bytearray()
        out += b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
        offsets = {}
        for num in range(1, total_objects + 1):
            offsets[num] = len(out)
            out += f"{num} 0 obj\n".encode()
            out += objects[num]
            out += b"\nendobj\n"
        xref_pos = len(out)
        out += f"xref\n0 {total_objects + 1}\n".encode()
        out += b"0000000000 65535 f \n"
        for num in range(1, total_objects + 1):
            out += f"{offsets[num]:010d} 00000 n \n".encode()
        out += (
            f"trailer\n<< /Size {total_objects + 1} /Root 1 0 R "
            f"/Info 7 0 R /ID [<{self.doc_id}> <{self.doc_id}>] >>\n"
            f"startxref\n{xref_pos}\n%%EOF\n".encode()
        )
        return bytes(out)
