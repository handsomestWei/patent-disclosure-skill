# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from emit_chart import (
    DISCLAIMER,
    chart_xlsx_name,
    main,
    normalize_chart,
    render_chart_md,
    write_chart_bundle,
)
from xlsx_minimal import estimate_row_height


def _payload() -> dict:
    return {
        "scene": "invalidity",
        "left": {"pub_number": "CN219812345U", "features_path": "outputs/patent_reader/run/claim_features.json"},
        "features": [
            {"feature_id": "F1", "claim_no": 1, "text": "壳体与端盖围出冷却腔"},
            {"feature_id": "F3", "claim_no": 1, "text": "桥接筋连通两区"},
        ],
        "columns": [
            {
                "id": "D1",
                "label": "CN216600001U",
                "pub_number": "CN216600001U",
                "source_url": "http://epub.cnipa.gov.cn/patent/CN216600001U",
            }
        ],
        "highlights": [
            {"id": "H1", "label": "冷却腔", "claim": "冷却腔", "evidence": "冷却空腔"},
        ],
        "cells": [
            {
                "feature_id": "F1",
                "column_id": "D1",
                "strength": "强",
                "quote": "壳体与端盖形成冷却空腔，并且在周向均布多条加强筋以承受热负荷。" * 2,
                "analysis": "对应：权要的冷却腔对应说明书里的冷却空腔。\n差别：对照未写端盖如何密封。\n依据：说明书 [0021]。",
                "source_url": "http://epub.cnipa.gov.cn/patent/CN216600001U",
                "desc_para": "0021",
                "cite": "对比文件1 · 说明书 [0021]",
                "covered": ["冷却腔", "壳体与端盖"],
                "missing": ["密封结构"],
            },
            {
                "feature_id": "F3",
                "column_id": "D1",
                "strength": "无",
                "quote": "",
                "analysis": "",
                "source_url": "",
                "desc_para": "",
            },
        ],
    }


class EmitChartTests(unittest.TestCase):
    def test_md_has_disclaimer_and_pending(self) -> None:
        text = render_chart_md(normalize_chart(_payload()))
        self.assertIn("不构成法律意见", text)
        self.assertIn("F3 × D1", text)
        self.assertIn("| F1 |", text)
        self.assertIn("很强", text)
        self.assertIn("对照表-{场景}-{时间戳}.xlsx", text)
        self.assertNotIn("应当无效", text)
        self.assertIn(DISCLAIMER[:12], text)
        self.assertIn("冷却空腔，并且在周向均布多条加强筋", text)
        self.assertIn("对应：", text)
        self.assertNotIn("对上了", text)

    def test_md_optional_via_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = Path(tmp) / "p.json"
            payload.write_text(json.dumps(_payload()), encoding="utf-8")
            out = Path(tmp) / "预览.md"
            code = main(
                [
                    "--json",
                    str(payload),
                    "--into",
                    str(Path(tmp) / "sess"),
                    "--md",
                    str(out),
                ]
            )
            self.assertEqual(code, 0)
            text = out.read_text(encoding="utf-8")
            self.assertIn("不构成法律意见", text)
            self.assertIn("F3 × D1", text)
            self.assertNotIn("应当无效", text)

    def test_bundle_xlsx_drilldown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_chart_bundle(_payload(), output_dir=Path(tmp), case_id="demo")
            self.assertTrue(paths["xlsx"].is_file())
            self.assertTrue(paths["json"].is_file())
            self.assertFalse((paths["dir"] / "chart.md").exists())
            self.assertFalse((paths["dir"] / "chart.yaml").exists())
            self.assertFalse(list(paths["dir"].glob("*.docx")))
            self.assertFalse(list(paths["dir"].glob("*.html")))
            with zipfile.ZipFile(paths["xlsx"]) as zf:
                names = set(zf.namelist())
                wb = zf.read("xl/workbook.xml").decode("utf-8")
                sheet1 = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
                sheet2 = zf.read("xl/worksheets/sheet2.xml").decode("utf-8")
                sheet3 = zf.read("xl/worksheets/sheet3.xml").decode("utf-8")
                sheet4 = zf.read("xl/worksheets/sheet4.xml").decode("utf-8")
                sheet5 = zf.read("xl/worksheets/sheet5.xml").decode("utf-8")
                styles = zf.read("xl/styles.xml").decode("utf-8")
            self.assertIn("xl/worksheets/sheet4.xml", names)
            self.assertIn("xl/worksheets/sheet5.xml", names)
            self.assertIn('name="总览"', wb)
            self.assertIn('name="对照表"', wb)
            self.assertIn('name="明细"', wb)
            self.assertIn('name="路径备忘"', wb)
            self.assertIn('name="图例"', wb)
            self.assertIn("F1", sheet1)
            self.assertIn("HYPERLINK", sheet1)
            self.assertIn("#'明细'", sheet1)
            self.assertNotIn("&apos;", sheet1)
            self.assertIn("冷却空腔", sheet2)
            self.assertIn("FF2563EB", sheet2)
            self.assertIn("对应：权要的冷却腔对应说明书里的冷却空腔。\n差别：", sheet2)
            self.assertIn("查看摘录", sheet2)
            self.assertNotIn("Very Strong", sheet2 + sheet3 + sheet4 + sheet5)
            self.assertIn('min="7" max="7" width="18"', sheet2)
            self.assertIn("返回总览", sheet3)
            self.assertIn("#'总览'!D4", sheet3)
            self.assertIn("#'总览'!D5", sheet3)
            self.assertNotIn("#'总览'!A4", sheet3)
            self.assertIn("返回对照表", sheet3)
            self.assertIn("#'对照表'", sheet3)
            self.assertNotIn("对上了", sheet3)
            self.assertNotIn("没写到", sheet3)
            self.assertIn("FF1D4ED8", styles)
            self.assertNotIn("FF047857", styles)
            self.assertIn("FFFDE047", styles)
            self.assertNotIn("FFEA580C", styles)
            self.assertIn("FFB91C1C", styles)
            self.assertIn("已覆盖", sheet4)
            self.assertIn("未覆盖", sheet4)
            self.assertIn("很强", sheet4)
            self.assertIn("未见", sheet4)
            self.assertIn("HYPERLINK", sheet4)
            self.assertNotIn("应当无效", sheet4)
            self.assertIn("FF2563EB", sheet5)
            self.assertIn("<b/>", sheet5)
            self.assertIn("微软雅黑", styles)
            self.assertIn("FF1F4E79", styles)
            self.assertIn("wrapText", styles)
            self.assertIn('state="frozen"', sheet1)
            self.assertIn("打开公布页", sheet2 + sheet3)

    def test_row_height_grows_with_quote(self) -> None:
        short = estimate_row_height([{"v": "短摘录"}], [80], min_h=22)
        long = estimate_row_height([{"v": "壳体与端盖形成冷却空腔。" * 40}], [80], min_h=22)
        self.assertGreater(long, short)
        self.assertGreater(long, 100)
        self.assertLessEqual(long, 409)
        raw = _payload()
        raw["cells"][0]["quote"] = "壳体与端盖形成冷却空腔，并且在周向均布多条加强筋以承受热负荷。" * 18
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_chart_bundle(raw, output_dir=Path(tmp), case_id="tall")
            with zipfile.ZipFile(paths["xlsx"]) as zf:
                sheet3 = zf.read("xl/worksheets/sheet3.xml").decode("utf-8")
        pairs = [(int(a), float(b)) for a, b in re.findall(r'<row r="(\d+)" ht="([^"]+)"', sheet3)]
        by_row = {r: h for r, h in pairs}
        # 明细每格 9 行，对照摘录是块内第 5 行 → Excel 第 8 行
        self.assertGreater(by_row.get(8, 0), 88)

    def test_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "in.json"
            src.write_text(json.dumps(_payload(), ensure_ascii=False), encoding="utf-8")
            out = Path(tmp) / "out"
            self.assertEqual(
                main(["--json", str(src), "--output-dir", str(out), "--case-id", "demo"]),
                0,
            )
            self.assertTrue(list(out.glob("demo_*/对照表-无效对照-*.xlsx")))
            self.assertTrue(list(out.glob("demo_*/chart.json")))
            self.assertFalse(list(out.glob("demo_*/chart.md")))
            self.assertFalse(list(out.glob("demo_*/chart.yaml")))

    def test_cjk_wrap_spaces_tidied(self) -> None:
        raw = _payload()
        raw["cells"][0]["quote"] = "以及皮肤固定 座，所述外壳"
        chart = normalize_chart(raw)
        self.assertIn("皮肤固定座", chart["cells"][0]["quote"])
        self.assertNotIn("固定 座", chart["cells"][0]["quote"])

    def test_chart_clips_and_dedupes_quote(self) -> None:
        para = (
            "一种持续血糖监测装置，包括外壳、置于所述外壳内的助针组件，以及皮肤固定座，"
            "所述外壳的一端设有开口，所述监测装置还包括设置于所述助针组件一端的触发罩，"
            "所述触发罩具有用于与皮肤接触的抵顶部，所述助针组件能够朝向所述开口运动。"
        )
        raw = _payload()
        raw["features"] = [
            {"feature_id": "F1", "claim_no": 1, "text": "所述壳体组件包括外壳"},
            {"feature_id": "F2", "claim_no": 1, "text": "所述外壳的一端设有开口"},
            {"feature_id": "F3", "claim_no": 1, "text": "所述壳体组件包括外壳"},
        ]
        raw["highlights"] = []
        raw["cells"] = [
            {
                "feature_id": "F1",
                "column_id": "D1",
                "strength": "中",
                "quote": para,
                "analysis": "对应：外壳。\n差别：无壳体组件名称。\n依据：说明书 [0009]。",
                "desc_para": "0009",
                "cite": "对比文件1 · 说明书 [0009]",
                "covered": ["外壳"],
            },
            {
                "feature_id": "F2",
                "column_id": "D1",
                "strength": "中",
                "quote": para,
                "analysis": "对应：开口。\n差别：无。\n依据：说明书 [0009]。",
                "desc_para": "0009",
                "cite": "对比文件1 · 说明书 [0009]",
                "covered": ["开口"],
            },
            {
                "feature_id": "F3",
                "column_id": "D1",
                "strength": "中",
                "quote": para,
                "analysis": "对应：外壳。\n差别：无。\n依据：说明书 [0009]。",
                "desc_para": "0009",
                "cite": "对比文件1 · 说明书 [0009]",
                "covered": ["外壳"],
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_chart_bundle(raw, output_dir=Path(tmp), case_id="clip")
            with zipfile.ZipFile(paths["xlsx"]) as zf:
                names = set(zf.namelist())
                sheet2 = zf.read("xl/worksheets/sheet2.xml").decode("utf-8")
                sheet3 = zf.read("xl/worksheets/sheet3.xml").decode("utf-8")
                comments = zf.read("xl/comments2.xml").decode("utf-8")
        self.assertIn("同 F1", sheet2)
        self.assertIn("[0009]", sheet2)
        self.assertIn("开口", sheet2)
        self.assertIn("xl/comments2.xml", names)
        self.assertIn("[0009]", comments)
        self.assertGreater(sheet3.count("一种持续血糖监测装置"), 2)

    def test_into_session_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp) / "20260929-120000"
            session.mkdir()
            (session / "intake.json").write_text("{}", encoding="utf-8")
            src = Path(tmp) / "in.json"
            src.write_text(json.dumps(_payload(), ensure_ascii=False), encoding="utf-8")
            self.assertEqual(main(["--json", str(src), "--into", str(session)]), 0)
            self.assertTrue((session / "对照表-无效对照-20260929-120000.xlsx").is_file())
            self.assertTrue((session / "intake.json").is_file())
            self.assertFalse((session / "chart.xlsx").exists())
            self.assertFalse(list(Path(tmp).glob("demo_*")))

    def test_xlsx_named_with_scene_and_stamp(self) -> None:
        self.assertEqual(
            chart_xlsx_name({"scene": "patentability"}, "20260929-232749"),
            "对照表-可专利性-20260929-232749.xlsx",
        )
        self.assertEqual(
            chart_xlsx_name({"scene": "infringement"}, "20260929-232749-2"),
            "对照表-侵权对照-20260929-232749-2.xlsx",
        )
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp) / "20260929-232749"
            paths = write_chart_bundle(_payload(), into=session)
            self.assertEqual(paths["xlsx"].name, "对照表-无效对照-20260929-232749.xlsx")
            raw = _payload()
            raw["scene"] = "fto"
            paths = write_chart_bundle(raw, into=session)
            self.assertEqual(paths["xlsx"].name, "对照表-FTO初筛-20260929-232749.xlsx")

    def test_oa_rejection_sheet(self) -> None:
        raw = _payload()
        raw["scene"] = "oa"
        raw["rejections"] = [
            {
                "id": "R1",
                "item": "第1条",
                "statute": "专利法第22条第3款",
                "examiner_view": "审查员认为权利要求1相对于对比文件1不具备创造性。",
                "feature_ids": ["F1", "F3"],
                "column_ids": ["D1"],
            }
        ]
        chart = normalize_chart(raw)
        self.assertEqual(chart["rejections"][0]["item"], "第1条")
        self.assertEqual(
            chart_xlsx_name(chart, "20260930-093000"),
            "对照表-审查答复-20260930-093000.xlsx",
        )
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp) / "20260930-093000"
            paths = write_chart_bundle(raw, into=session)
            with zipfile.ZipFile(paths["xlsx"]) as zf:
                wb = zf.read("xl/workbook.xml").decode("utf-8")
                sheet4 = zf.read("xl/worksheets/sheet4.xml").decode("utf-8")
        self.assertEqual(paths["xlsx"].name, "对照表-审查答复-20260930-093000.xlsx")
        self.assertIn('name="驳回映射"', wb)
        self.assertNotIn('name="路径备忘"', wb)
        self.assertIn("第1条", sheet4)
        self.assertIn("专利法第22条第3款", sheet4)
        self.assertIn("待核", sheet4)
        self.assertIn(">F3</t>", sheet4)
        self.assertLess(sheet4.find(">F3</t>"), sheet4.find(">F1</t>"))
        self.assertNotIn("应当无效", sheet4)
        self.assertNotIn("可以自由实施", sheet4)

    def test_fto_risk_sheet_needs_review(self) -> None:
        raw = _payload()
        raw["scene"] = "fto"
        chart = normalize_chart(raw)
        self.assertEqual(chart["cells"][0]["risk"], "高")
        self.assertTrue(chart["cells"][0]["review_required"])
        self.assertEqual(chart["cells"][1]["risk"], "未见")
        self.assertFalse(chart["cells"][1]["review_required"])
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_chart_bundle(raw, output_dir=Path(tmp), case_id="fto")
            with zipfile.ZipFile(paths["xlsx"]) as zf:
                wb = zf.read("xl/workbook.xml").decode("utf-8")
                sheet1 = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
                sheet4 = zf.read("xl/worksheets/sheet4.xml").decode("utf-8")
                sheet5 = zf.read("xl/worksheets/sheet5.xml").decode("utf-8")
        self.assertIn('name="风险清单"', wb)
        self.assertIn('name="图例"', wb)
        self.assertNotIn('name="路径备忘"', wb)
        self.assertIn("须人审", sheet1)
        self.assertIn("须人审", sheet4)
        self.assertIn("高", sheet4)
        self.assertNotIn("可以自由实施", sheet4)
        self.assertNotIn("构成侵权", sheet4)
        self.assertIn("高", sheet5)

    def test_infringement_gap_sheet_sorts_weak_first(self) -> None:
        raw = _payload()
        raw["scene"] = "infringement"
        raw["features"].insert(
            1,
            {"feature_id": "F2", "claim_no": 1, "text": "密封圈压紧端盖"},
        )
        raw["cells"].insert(
            1,
            {
                "feature_id": "F2",
                "column_id": "D1",
                "strength": "弱",
                "quote": "周向均布加强筋。",
                "analysis": "对应：仅加强筋片段。\n差别：未见密封圈。\n依据：说明书 [0021]。",
                "source_url": "http://epub.cnipa.gov.cn/patent/CN216600001U",
                "desc_para": "0021",
                "covered": ["加强筋"],
                "missing": ["密封圈"],
            },
        )
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_chart_bundle(raw, output_dir=Path(tmp), case_id="eou")
            with zipfile.ZipFile(paths["xlsx"]) as zf:
                wb = zf.read("xl/workbook.xml").decode("utf-8")
                sheet4 = zf.read("xl/worksheets/sheet4.xml").decode("utf-8")
        self.assertIn('name="证据缺口"', wb)
        self.assertNotIn('name="风险清单"', wb)
        self.assertIn("待补证据", sheet4)
        self.assertIn("密封圈", sheet4)
        self.assertNotIn("构成侵权", sheet4)
        f3 = sheet4.find('>F3</t>')
        f2 = sheet4.find('>F2</t>')
        f1 = sheet4.find('>F1</t>')
        self.assertGreater(f3, 0)
        self.assertGreater(f2, f3)
        self.assertGreater(f1, f2)

    def test_patentability_has_no_scene_sheet(self) -> None:
        raw = _payload()
        raw["scene"] = "patentability"
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_chart_bundle(raw, output_dir=Path(tmp), case_id="pat")
            with zipfile.ZipFile(paths["xlsx"]) as zf:
                names = set(zf.namelist())
                wb = zf.read("xl/workbook.xml").decode("utf-8")
                sheet4 = zf.read("xl/worksheets/sheet4.xml").decode("utf-8")
        self.assertNotIn("xl/worksheets/sheet5.xml", names)
        self.assertNotIn('name="路径备忘"', wb)
        self.assertNotIn('name="风险清单"', wb)
        self.assertNotIn('name="证据缺口"', wb)
        self.assertIn('name="图例"', wb)
        self.assertIn("FF2563EB", sheet4)


if __name__ == "__main__":
    unittest.main()
