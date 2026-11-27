"""Writer unit tests: determinism, xref validity, wrapping, table
pagination, FlateDecode round-trip."""

import re
import unittest
import zlib

from fencewalk.pdf import Document, TEXT_WIDTH, text_width, wrap_runs


def extract_streams(pdf_bytes):
    """All FlateDecode content streams, decompressed, in order."""
    out = []
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", pdf_bytes, re.S):
        try:
            out.append(zlib.decompress(match.group(1).strip(b"\r\n")))
        except zlib.error:
            continue
    return out


def stream_text(pdf_bytes):
    """Literal strings from the content streams, BT block per line."""
    lines = []
    for stream in extract_streams(pdf_bytes):
        for block in re.finditer(rb"BT(.*?)ET", stream, re.S):
            parts = []
            for sm in re.finditer(rb"\((?:\\.|[^\\()])*\)", block.group(1)):
                s = sm.group(0)[1:-1]
                s = s.replace(b"\\(", b"(").replace(b"\\)", b")").replace(b"\\\\", b"\\")
                parts.append(s)
            lines.append(b"".join(parts).decode("latin-1"))
    return lines


class WriterTest(unittest.TestCase):
    def _doc(self):
        doc = Document("Test", "0" * 64, "Fencewalk engagement report — Test")
        doc.title_block("Title line")
        doc.paragraph([("A short body paragraph.", "helvetica", 10)])
        return doc

    def test_determinism(self):
        self.assertEqual(self._doc().build(), self._doc().build())

    def test_xref_validity(self):
        data = self._doc().build()
        startxref = data.rindex(b"startxref\n") + len(b"startxref\n")
        xref_pos = int(data[startxref : data.index(b"\n%%EOF", startxref)])
        self.assertEqual(data[xref_pos : xref_pos + 4], b"xref")
        header_end = data.index(b"\n", xref_pos + 5)
        _, count = data[xref_pos + 5 : header_end].split()
        count = int(count)
        entries = data[header_end + 1 :].split(b"\n")
        self.assertEqual(len(entries[0]), 19)  # free entry line
        offsets = []
        for line in entries[1 : count]:
            self.assertRegex(line.decode(), r"^\d{10} 00000 [nf] $")
            offsets.append(int(line[:10]))
        self.assertEqual(len(offsets), count - 1)
        for num, offset in enumerate(offsets, start=1):
            self.assertEqual(
                data[offset : offset + len(f"{num} 0 obj")],
                f"{num} 0 obj".encode(),
                f"xref offset for object {num} is wrong",
            )
        trailer = data[data.index(b"trailer", xref_pos) :]
        size = int(re.search(rb"/Size (\d+)", trailer).group(1))
        self.assertEqual(size, count)

    def test_wrapping_long_token_stays_within_width(self):
        token = "A" * 200
        lines = wrap_runs([(token, "courier", 9)], TEXT_WIDTH)
        self.assertGreater(len(lines), 1)
        for line in lines:
            width = sum(
                text_width(text, font, size) for text, font, size in line
            )
            self.assertLessEqual(width, TEXT_WIDTH)

    def test_wrapping_mixed_runs_stay_within_width(self):
        runs = [
            ("The quick brown fox jumps over the lazy dog. " * 6, "helvetica", 10),
            ("R-1.4", "courier", 10),
        ]
        for line in wrap_runs(runs, TEXT_WIDTH):
            width = sum(
                text_width(text, font, size) for text, font, size in line
            )
            self.assertLessEqual(width, TEXT_WIDTH)

    def test_table_pagination_repeats_header(self):
        doc = Document("Test", "0" * 64, "Fencewalk engagement report — Test")
        rows = [
            [(f"R-{n}", "courier", (0.122, 0.122, 0.122)),
             (f"Reasoning for row {n}, short.", "helvetica", (0.122, 0.122, 0.122))]
            for n in range(1, 61)
        ]
        doc.table(["Item", "Reasoning"], rows, [62, 442])
        data = doc.build()
        n_pages = len(re.findall(rb"/Type /Page(?!s)", data))
        self.assertGreater(n_pages, 1)
        header_hits = 0
        for stream in extract_streams(data):
            header_hits += stream.count(b"(Item)")
        self.assertEqual(header_hits, n_pages)

    def test_flate_round_trip_finds_text(self):
        data = self._doc().build()
        streams = extract_streams(data)
        self.assertTrue(streams)
        text = "\n".join(stream_text(data))
        self.assertIn("Title line", text)
        self.assertIn("A short body paragraph.", text)

    def test_header_is_pdf_1_4_letter(self):
        data = self._doc().build()
        self.assertTrue(data.startswith(b"%PDF-1.4\n"))
        self.assertIn(b"/MediaBox [0 0 612 792]", data)
        self.assertTrue(data.rstrip().endswith(b"%%EOF"))
        self.assertNotIn(b"/JavaScript", data)
        self.assertNotIn(b"/Encrypt", data)


if __name__ == "__main__":
    unittest.main()
