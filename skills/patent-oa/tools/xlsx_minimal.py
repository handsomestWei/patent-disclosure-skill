"""对照表 xlsx：多表明细跳转、图例单元格填充、强弱底色。无第三方依赖。"""
from __future__ import annotations

import zipfile
from xml.sax.saxutils import escape
from pathlib import Path
from typing import Any

from highlights import HIGHLIGHT_XF_BASE, PALETTE

S_BODY = 0
S_HEADER = 1
S_TITLE = 2
S_SUB = 3
S_FEATURE = 4
S_CLAIM_NO = 5
S_ZEBRA = 6
S_STRONG = 7
S_MID = 8
S_WEAK = 9
S_NONE = 10
S_Q_STRONG = 11
S_Q_MID = 12
S_Q_WEAK = 13
S_Q_NONE = 14
S_LINK = 15
S_LINK_ZEBRA = 16
S_HM_STRONG = 17
S_HM_MID = 18
S_HM_WEAK = 19
S_HM_NONE = 20
S_LABEL = 21
S_WRAP = 22

STRENGTH_BADGE = {"强": S_STRONG, "中": S_MID, "弱": S_WEAK, "无": S_NONE}
HEATMAP = {"强": S_HM_STRONG, "中": S_HM_MID, "弱": S_HM_WEAK, "无": S_HM_NONE}
QUOTE_TINT = {"强": S_Q_STRONG, "中": S_Q_MID, "弱": S_Q_WEAK, "无": S_Q_NONE}


def _col_letter(index: int) -> str:
    n = index + 1
    out = ""
    while n:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out


def _esc(text: str) -> str:
    cleaned = "".join(ch for ch in (text or "") if ord(ch) >= 32 or ch in "\t\n\r")
    return escape(cleaned)


def _esc_formula(text: str) -> str:
    return _esc((text or "").replace('"', '""'))


# Excel 行高上限 409pt。10pt 微软雅黑换行约 16pt/行。
_ROW_LINE_PT = 16.0
_ROW_PAD_PT = 8.0
_ROW_MAX_PT = 409.0


def _is_wide_char(ch: str) -> bool:
    o = ord(ch)
    return (
        0x1100 <= o <= 0x115F
        or 0x2E80 <= o <= 0xA4CF
        or 0xAC00 <= o <= 0xD7A3
        or 0xF900 <= o <= 0xFAFF
        or 0xFE10 <= o <= 0xFE6F
        or 0xFF00 <= o <= 0xFF60
        or 0xFFE0 <= o <= 0xFFE6
        or 0x3400 <= o <= 0x9FFF
    )


def cell_display_text(cell: Any) -> str:
    if cell is None:
        return ""
    if not isinstance(cell, dict):
        return str(cell)
    if cell.get("loc") or cell.get("link"):
        return str(cell.get("label") or cell.get("v") or "")
    if cell.get("runs"):
        return "".join(str(t) for t, _ in cell["runs"] if t)
    if cell.get("v") is not None:
        return str(cell.get("v"))
    return str(cell.get("text") or "")


def _char_units(ch: str) -> float:
    if ch in "\n\r":
        return 0.0
    return 2.0 if _is_wide_char(ch) else 1.0


def _wrapped_lines(text: str, col_width: float) -> int:
    usable = max(float(col_width) - 1.6, 4.0)
    if not text:
        return 1
    total = 0
    for para in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not para:
            total += 1
            continue
        used = 0.0
        lines = 1
        for ch in para:
            w = _char_units(ch)
            if used + w > usable:
                lines += 1
                used = w
            else:
                used += w
        total += lines
    return max(total, 1)


def estimate_row_height(
    row: list[Any],
    widths: list[float],
    *,
    min_h: float = 22.0,
    max_h: float = _ROW_MAX_PT,
) -> float:
    """按列宽与换行估算行高，避免长摘录被裁切。"""
    texts = [cell_display_text(cell) for cell in row]
    if not any(t.strip() for t in texts):
        return min(max_h, max(min_h, 12.0))
    lines = 1
    for i, text in enumerate(texts):
        col_w = widths[i] if i < len(widths) else 16.0
        lines = max(lines, _wrapped_lines(text, col_w))
    return min(max_h, max(min_h, _ROW_PAD_PT + lines * _ROW_LINE_PT))


def _run_xml(text: str, rgb: str | None) -> str:
    body = _esc(text)
    if not body:
        return ""
    if rgb == "B":
        rpr = (
            '<rPr><b/><sz val="10"/><color rgb="FF2F2F2F"/>'
            '<rFont val="微软雅黑"/><family val="2"/></rPr>'
        )
    elif rgb:
        color = rgb if rgb.startswith("FF") else "FF" + rgb.replace("#", "")
        rpr = (
            f'<rPr><b/><sz val="10"/><color rgb="{color}"/>'
            f'<rFont val="微软雅黑"/><family val="2"/></rPr>'
        )
    else:
        rpr = '<rPr><sz val="10"/><color rgb="FF2F2F2F"/><rFont val="微软雅黑"/><family val="2"/></rPr>'
    return f'<r>{rpr}<t xml:space="preserve">{body}</t></r>'


def _cell(ref: str, cell: Any, *, style: int = 0) -> str:
    if cell is None:
        cell = ""
    if not isinstance(cell, dict):
        cell = {"v": str(cell)}
    value = str(cell.get("v") if cell.get("v") is not None else cell.get("text") or "")
    style = int(cell.get("s", style))
    runs = cell.get("runs")
    loc = cell.get("loc")
    link = cell.get("link")
    label = str(cell.get("label") or value or "打开")
    if loc:
        target = loc if str(loc).startswith("#") else f"#{loc}"
        return (
            f'<c r="{ref}" s="{style}" t="str">'
            f"<f>HYPERLINK(\"{_esc_formula(target)}\",\"{_esc_formula(label)}\")</f>"
            f"<v>{_esc(label)}</v></c>"
        )
    if link:
        return (
            f'<c r="{ref}" s="{style}" t="str">'
            f"<f>HYPERLINK(\"{_esc_formula(link)}\",\"{_esc_formula(label)}\")</f>"
            f"<v>{_esc(label)}</v></c>"
        )
    if runs:
        is_xml = "".join(_run_xml(str(t), rgb) for t, rgb in runs if t)
        if is_xml:
            return f'<c r="{ref}" s="{style}" t="inlineStr"><is>{is_xml}</is></c>'
    return (
        f'<c r="{ref}" t="inlineStr" s="{style}">'
        f'<is><t xml:space="preserve">{_esc(value)}</t></is></c>'
    )


def _sheet_xml(sheet: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    headers: list[str] = list(sheet.get("headers") or [])
    rows: list[list[Any]] = list(sheet.get("rows") or [])
    title = str(sheet.get("title") or "")
    subtitle = str(sheet.get("subtitle") or "")
    widths: list[float] = list(sheet.get("widths") or [])
    tab = str(sheet.get("tab") or "1F4E79")
    freeze = bool(sheet.get("freeze", True))
    row_h = float(sheet.get("row_height") or 48)
    ncols = max(len(headers), 1)
    for row in rows:
        ncols = max(ncols, len(row))
    last_col = _col_letter(ncols - 1)
    title_row, sub_row, header_row, data_start = 1, 2, 3, 4
    last_row = max(data_start - 1 + len(rows), header_row)
    cols_xml = ["<cols>"]
    for i in range(ncols):
        w = widths[i] if i < len(widths) else 16
        cols_xml.append(f'<col min="{i + 1}" max="{i + 1}" width="{w}" customWidth="1"/>')
    cols_xml.append("</cols>")
    sheet_rows = ["<sheetData>"]
    title_cells = [_cell(f"A{title_row}", {"v": title, "s": S_TITLE})]
    for i in range(1, ncols):
        title_cells.append(_cell(f"{_col_letter(i)}{title_row}", {"v": "", "s": S_TITLE}))
    sheet_rows.append(f'<row r="{title_row}" ht="26" customHeight="1">{"".join(title_cells)}</row>')
    sub_cells = [_cell(f"A{sub_row}", {"v": subtitle, "s": S_SUB})]
    for i in range(1, ncols):
        sub_cells.append(_cell(f"{_col_letter(i)}{sub_row}", {"v": "", "s": S_SUB}))
    sheet_rows.append(f'<row r="{sub_row}" ht="36" customHeight="1">{"".join(sub_cells)}</row>')
    header_xml = [
        _cell(f"{_col_letter(i)}{header_row}", {"v": h, "s": S_HEADER})
        for i, h in enumerate(headers)
    ]
    while len(header_xml) < ncols:
        header_xml.append(
            _cell(f"{_col_letter(len(header_xml))}{header_row}", {"v": "", "s": S_HEADER})
        )
    sheet_rows.append(
        f'<row r="{header_row}" ht="32" customHeight="1">{"".join(header_xml)}</row>'
    )
    given_heights = list(sheet.get("heights") or [])
    auto_height = bool(sheet.get("auto_height", True))
    notes: list[dict[str, Any]] = []
    for r_i, row in enumerate(rows):
        excel_r = data_start + r_i
        min_h = given_heights[r_i] if r_i < len(given_heights) else row_h
        padded = [(widths[i] if i < len(widths) else 16.0) for i in range(ncols)]
        if auto_height:
            height = estimate_row_height(row, padded, min_h=min_h)
        else:
            height = min_h
        cells = []
        for c_i in range(ncols):
            raw = row[c_i] if c_i < len(row) else ""
            ref = f"{_col_letter(c_i)}{excel_r}"
            cells.append(_cell(ref, raw, style=S_BODY))
            note = raw.get("note") if isinstance(raw, dict) else None
            if note:
                notes.append(
                    {
                        "ref": ref,
                        "row": excel_r - 1,
                        "col": c_i,
                        "text": str(note),
                    }
                )
        sheet_rows.append(
            f'<row r="{excel_r}" ht="{height:.1f}" customHeight="1">{"".join(cells)}</row>'
        )
    sheet_rows.append("</sheetData>")
    pane = ""
    if freeze:
        pane = (
            f'<pane ySplit="{header_row}" topLeftCell="A{data_start}" '
            'activePane="bottomLeft" state="frozen"/>'
        )
    filter_xml = ""
    if rows:
        filter_xml = f'<autoFilter ref="A{header_row}:{last_col}{last_row}"/>'
    merges = (
        f'<mergeCells count="2">'
        f'<mergeCell ref="A{title_row}:{last_col}{title_row}"/>'
        f'<mergeCell ref="A{sub_row}:{last_col}{sub_row}"/>'
        f"</mergeCells>"
    )
    drawing = '<legacyDrawing r:id="rId1"/>' if notes else ""
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
        ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheetPr><tabColor rgb="FF{tab}"/><pageSetUpPr fitToPage="1"/></sheetPr>'
        f'<dimension ref="A1:{last_col}{last_row}"/>'
        "<sheetViews>"
        f'<sheetView workbookViewId="0" showGridLines="0" zoomScale="110">{pane}</sheetView>'
        "</sheetViews>"
        '<sheetFormatPr defaultRowHeight="16" defaultColWidth="12"/>'
        f'{"".join(cols_xml)}'
        f'{"".join(sheet_rows)}'
        f"{filter_xml}"
        f"{merges}"
        '<pageMargins left="0.5" right="0.5" top="0.6" bottom="0.6"'
        ' header="0.3" footer="0.3"/>'
        '<pageSetup orientation="landscape" fitToWidth="1" fitToHeight="0"'
        ' paperSize="9"/>'
        f"{drawing}"
        "</worksheet>"
    )
    return xml, notes


def _comments_xml(notes: list[dict[str, Any]]) -> str:
    items = []
    for note in notes:
        items.append(
            f'<comment ref="{_esc(note["ref"])}" authorId="0">'
            "<text><r>"
            '<rPr><sz val="9"/><color rgb="FF2F2F2F"/><rFont val="微软雅黑"/><family val="2"/></rPr>'
            f'<t xml:space="preserve">{_esc(str(note.get("text") or ""))}</t>'
            "</r></text></comment>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<comments xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<authors><author>对照表</author></authors>"
        f'<commentList>{"".join(items)}</commentList></comments>'
    )


def _vml_xml(notes: list[dict[str, Any]]) -> str:
    shapes = []
    for i, note in enumerate(notes, start=1025):
        row = int(note["row"])
        col = int(note["col"])
        shapes.append(
            f'<v:shape id="_x0000_s{i}" type="#_x0000_t202" '
            'style="position:absolute;margin-left:50pt;margin-top:2pt;width:220pt;height:90pt;'
            'z-index:1;visibility:hidden" fillcolor="#ffffe1" o:insetmode="auto">'
            '<v:fill color2="#ffffe1"/><v:shadow on="t" color="black" obscured="t"/>'
            '<v:path o:connecttype="none"/>'
            '<v:textbox style="mso-direction-alt:auto"><div style="text-align:left"></div></v:textbox>'
            f'<x:ClientData ObjectType="Note"><x:MoveWithCells/><x:SizeWithCells/>'
            f"<x:AutoFill>False</x:AutoFill><x:Row>{row}</x:Row><x:Column>{col}</x:Column>"
            "</x:ClientData></v:shape>"
        )
    return (
        '<xml xmlns:v="urn:schemas-microsoft-com:vml" '
        'xmlns:o="urn:schemas-microsoft-com:office:office" '
        'xmlns:x="urn:schemas-microsoft-com:office:excel">'
        '<o:shapelayout v:ext="edit"><o:idmap v:ext="edit" data="1"/></o:shapelayout>'
        '<v:shapetype id="_x0000_t202" coordsize="21600,21600" o:spt="202" '
        'path="m,l,21600r21600,l21600,xe">'
        '<v:stroke joinstyle="miter"/><v:path gradientshapeok="t" o:connecttype="rect"/>'
        "</v:shapetype>"
        f'{"".join(shapes)}</xml>'
    )


def write_workbook(path: Path, sheets: list[dict[str, Any]]) -> Path:
    if not sheets:
        raise ValueError("至少一张表")
    path.parent.mkdir(parents=True, exist_ok=True)
    built = [_sheet_xml(sheet) for sheet in sheets]
    names = []
    used: set[str] = set()
    for i, sheet in enumerate(sheets, start=1):
        name = str(sheet.get("name") or f"表{i}")[:31]
        base = name
        n = 2
        while name in used:
            name = (base[:28] + f"_{n}")[:31]
            n += 1
        used.add(name)
        names.append(name)
    sheet_els = "".join(
        f'<sheet name="{_esc(name)}" sheetId="{i}" r:id="rId{i}"/>'
        for i, name in enumerate(names, start=1)
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
        ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{sheet_els}</sheets></workbook>"
    )
    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        + "".join(
            f'<Relationship Id="rId{i}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{i}.xml"/>'
            for i in range(1, len(sheets) + 1)
        )
        + f'<Relationship Id="rId{len(sheets) + 1}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
        "</Relationships>"
    )
    comment_overrides = []
    for i, (_xml, notes) in enumerate(built, start=1):
        if notes:
            comment_overrides.append(
                f'<Override PartName="/xl/comments{i}.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.comments+xml"/>'
            )
    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, len(sheets) + 1)
    ) + "".join(comment_overrides)
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="vml" ContentType="application/vnd.openxmlformats-officedocument.vmlDrawing"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        f"{overrides}"
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        "</Types>"
    )
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>
"""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        for i, (xml, notes) in enumerate(built, start=1):
            zf.writestr(f"xl/worksheets/sheet{i}.xml", xml)
            if notes:
                zf.writestr(
                    f"xl/worksheets/_rels/sheet{i}.xml.rels",
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<Relationships xmlns="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                    f'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/vmlDrawing" Target="../drawings/vmlDrawing{i}.vml"/>'
                    f'<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments" Target="../comments{i}.xml"/>'
                    "</Relationships>",
                )
                zf.writestr(f"xl/comments{i}.xml", _comments_xml(notes))
                zf.writestr(f"xl/drawings/vmlDrawing{i}.vml", _vml_xml(notes))
        zf.writestr("xl/styles.xml", _styles_xml())
    return path


def write_xlsx(
    path: Path,
    headers: list[str],
    rows: list[list[str]],
    *,
    fill_col: int | None = None,
    title: str = "权利要求对照表",
    subtitle: str = "",
    evidence_strengths: list[list[str]] | None = None,
) -> Path:
    """单表兼容入口。新对照请走 write_workbook。"""
    del fill_col, evidence_strengths
    return write_workbook(
        path,
        [
            {
                "name": "对照表",
                "title": title,
                "subtitle": subtitle,
                "headers": headers,
                "rows": rows,
                "tab": "1F4E79",
            }
        ],
    )


def _styles_xml() -> str:
    extra_fills = "".join(
        (
            '<fill><patternFill patternType="solid">'
            f'<fgColor rgb="FF{item["bg"]}"/><bgColor indexed="64"/>'
            "</patternFill></fill>"
        )
        for item in PALETTE
    )
    extra_xfs = "".join(
        (
            f'<xf numFmtId="0" fontId="0" fillId="{14 + i}" borderId="1" xfId="0" '
            'applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">'
            '<alignment horizontal="left" vertical="center" wrapText="1"/></xf>'
        )
        for i in range(len(PALETTE))
    )
    fill_count = 14 + len(PALETTE)
    xf_count = HIGHLIGHT_XF_BASE + len(PALETTE)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="10">
    <font><sz val="10"/><color rgb="FF2F2F2F"/><name val="微软雅黑"/><family val="2"/></font>
    <font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="微软雅黑"/><family val="2"/></font>
    <font><b/><sz val="10"/><color rgb="FF1F4E79"/><name val="微软雅黑"/><family val="2"/></font>
    <font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="微软雅黑"/><family val="2"/></font>
    <font><b/><sz val="10"/><color rgb="FF422006"/><name val="微软雅黑"/><family val="2"/></font>
    <font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="微软雅黑"/><family val="2"/></font>
    <font><b/><sz val="10"/><color rgb="FF334155"/><name val="微软雅黑"/><family val="2"/></font>
    <font><u/><sz val="10"/><color rgb="FF0563C1"/><name val="微软雅黑"/><family val="2"/></font>
    <font><b/><sz val="16"/><color rgb="FFFFFFFF"/><name val="微软雅黑"/><family val="2"/></font>
    <font><i/><sz val="9"/><color rgb="FF5B6B7A"/><name val="微软雅黑"/><family val="2"/></font>
  </fonts>
  <fills count="{fill_count}">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF1F4E79"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFE8EEF4"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFF7F9FC"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF1D4ED8"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFDE047"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFB91C1C"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFCBD5E1"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFEEF3F8"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFDBEAFE"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFEF9C3"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFECACA"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFF1F5F9"/><bgColor indexed="64"/></patternFill></fill>
    {extra_fills}
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border>
      <left style="thin"><color rgb="FFC9D3DE"/></left>
      <right style="thin"><color rgb="FFC9D3DE"/></right>
      <top style="thin"><color rgb="FFC9D3DE"/></top>
      <bottom style="thin"><color rgb="FFC9D3DE"/></bottom>
      <diagonal/>
    </border>
  </borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="{xf_count}">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="8" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment horizontal="left" vertical="center"/></xf>
    <xf numFmtId="0" fontId="9" fillId="9" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment horizontal="left" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="2" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
    <xf numFmtId="0" fontId="0" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
    <xf numFmtId="0" fontId="0" fillId="4" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="3" fillId="5" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="6" fillId="6" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="5" fillId="7" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="6" fillId="8" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="10" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="top" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="11" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="top" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="12" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="top" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="6" fillId="13" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="top" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="7" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="7" fillId="4" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="3" fillId="5" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="6" fillId="6" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="5" fillId="7" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="6" fillId="8" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="2" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="top" wrapText="1"/></xf>
    {extra_xfs}
  </cellXfs>
</styleSheet>
"""
