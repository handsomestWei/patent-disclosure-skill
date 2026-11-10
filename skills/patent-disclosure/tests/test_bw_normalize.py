# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SHARED = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(SHARED))

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover - optional dependency
    Image = None

import bw_normalize  # noqa: E402


@unittest.skipIf(Image is None, "Pillow 未安装")
class BwNormalizeTests(unittest.TestCase):
    def _draw(self, path: Path, *, color: str = "black", fill: str | None = None) -> None:
        im = Image.new("RGB", (600, 400), "white")
        d = ImageDraw.Draw(im)
        d.rectangle((200, 100, 400, 300), outline=color, width=4, fill=fill)
        im.save(path)

    def test_binarizes_crops_and_sets_dpi(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "raw.png"
            self._draw(src)
            out = Path(tmp) / "figures" / "图1.png"
            svg = Path(tmp) / "figures" / "图1.svg"
            res = bw_normalize.normalize(src, out, margin=10, dpi=300, svg=svg,
                                         abstract_out=Path(tmp) / "figures" / "摘要附图.png")
            with Image.open(out) as im:
                self.assertEqual(im.mode, "1")
                self.assertEqual(im.size, (201 + 20, 201 + 20))
                self.assertAlmostEqual(im.info["dpi"][0], 300, places=0)
            self.assertIn("%E5%9B%BE1.png", svg.read_text(encoding="utf-8"))
            self.assertTrue((Path(tmp) / "figures" / "摘要附图.png").is_file())
            self.assertEqual(res["color_ratio"], 0.0)

    def test_reports_color(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "raw.png"
            self._draw(src, color="red", fill="blue")
            res = bw_normalize.normalize(src, Path(tmp) / "o.png")
            self.assertGreater(res["color_ratio"], 0.1)

    def test_blank_image_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "blank.png"
            Image.new("RGB", (100, 100), "white").save(src)
            with self.assertRaises(ValueError):
                bw_normalize.normalize(src, Path(tmp) / "o.png")

    def test_flatten_alpha_composites_on_white(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "raw.png"
            im = Image.new("RGBA", (50, 50), (0, 0, 0, 0))
            ImageDraw.Draw(im).rectangle((10, 10, 40, 40), outline=(0, 0, 0, 255), width=3)
            im.save(src)
            self.assertTrue(bw_normalize.flatten_alpha(src))
            with Image.open(src) as out:
                self.assertEqual(out.mode, "RGB")
                self.assertEqual(out.getpixel((0, 0)), (255, 255, 255))
                self.assertEqual(out.getpixel((10, 10)), (0, 0, 0))
            self.assertFalse(bw_normalize.flatten_alpha(src))

    def test_flatten_alpha_ignores_unreadable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "fake.png"
            src.write_bytes(b"not an image")
            self.assertFalse(bw_normalize.flatten_alpha(src))
            self.assertEqual(src.read_bytes(), b"not an image")

    def test_jpeg_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "raw.png"
            self._draw(src)
            out = Path(tmp) / "主视图.jpg"
            bw_normalize.normalize(src, out)
            with Image.open(out) as im:
                self.assertEqual(im.format, "JPEG")


if __name__ == "__main__":
    unittest.main()
