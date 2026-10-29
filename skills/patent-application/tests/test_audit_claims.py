# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
if str(PKG / "tools") not in sys.path:
    sys.path.insert(0, str(PKG / "tools"))

from audit_claims import audit, summarize


GOOD = """
1. 一种壳体装配方法，包括提供电机腔壳体；其特征在于，将减速器腔与电机腔隔开，并使电机沿花键轴向抽拔。
2. 根据权利要求1所述的方法，其特征在于，冷却水套仅布置于电机腔外壁。
"""

INDEPENDENT_REF = """
1. 一种装置，根据权利要求2所述的装置，其特征在于包括壳体。
2. 一种装置，其特征在于包括盖板。
"""

SKIP_NUMBERS = """
1. 一种方法，其特征在于包括采集步骤以及处理步骤。
3. 根据权利要求1所述的方法，其特征在于处理步骤输出缺陷检测结果。
"""

PROMO = """
1. 一种方法，其特征在于采用新算法从而显著提高检测精度并得到缺陷检测结果。
"""


class AuditClaimsTests(unittest.TestCase):
    def test_good_claims_pass(self) -> None:
        findings = audit(GOOD)
        errors, _warnings = summarize(findings)
        self.assertEqual(errors, 0)

    def test_independent_cannot_reference(self) -> None:
        codes = {item.code for item in audit(INDEPENDENT_REF) if item.level == "ERROR"}
        self.assertIn("INDEPENDENT_REFERENCE", codes)
        self.assertIn("FORWARD_REFERENCE", codes)

    def test_number_sequence(self) -> None:
        codes = {item.code for item in audit(SKIP_NUMBERS) if item.level == "ERROR"}
        self.assertIn("NUMBER_SEQUENCE", codes)

    def test_promo_is_warning_only(self) -> None:
        findings = audit(PROMO)
        errors, warnings = summarize(findings)
        self.assertEqual(errors, 0)
        self.assertGreaterEqual(warnings, 1)
        self.assertTrue(any(item.code == "RESULT_LANGUAGE" for item in findings))

    def test_placeholder_is_error(self) -> None:
        text = "1. 一种方法，其特征在于[待确认：步骤未写]包括采集。\n"
        codes = {item.code for item in audit(text) if item.level == "ERROR"}
        self.assertIn("PLACEHOLDER", codes)

    def test_second_independent_system_skips_no_reference(self) -> None:
        text = """
1. 一种调度方法，其特征在于包括以下步骤：步骤一，采集节点指标。
2. 一种调度系统，其特征在于包括配置中心和调度器。
"""
        findings = audit(text)
        self.assertFalse(
            any(item.code == "NO_REFERENCE" for item in findings),
            msg=[(item.claim, item.code) for item in findings],
        )

    def test_dependent_without_reference_still_warns(self) -> None:
        text = """
1. 一种调度方法，其特征在于包括以下步骤：步骤一，采集节点指标。
2. 进一步，冷却水套仅布置于电机腔外壁并完成装配。
"""
        self.assertTrue(any(item.code == "NO_REFERENCE" for item in audit(text)))


MULTI_REF = """
1. 一种方法，其特征在于包括采集。
2. 根据权利要求1所述的方法，其特征在于所述采集为周期采集。
3. 根据权利要求1或2所述的方法，其特征在于还包括去噪。
4. 根据权利要求1、2或3所述的方法，其特征在于输出CSV。
5. 根据权利要求1至4中任一项所述的方法，其特征在于按批次写盘。
"""


class ReferenceParsingTests(unittest.TestCase):
    def test_multi_reference_expands(self) -> None:
        claims = dict.fromkeys(range(1, 6))
        codes_texts = audit(MULTI_REF)
        forward = [item for item in codes_texts if item.code == "FORWARD_REFERENCE"]
        self.assertEqual(forward, [], msg=[(item.claim, item.message) for item in forward])
        missing = [item for item in codes_texts if item.code == "MISSING_REFERENCE"]
        self.assertEqual(missing, [])

    def test_multi_reference_forward_detected(self) -> None:
        text = (
            "1. 一种方法，其特征在于包括采集。\n"
            "2. 根据权利要求1或3所述的方法，其特征在于还包括去噪。\n"
        )
        codes = {item.code for item in audit(text)}
        self.assertIn("FORWARD_REFERENCE", codes)


if __name__ == "__main__":
    unittest.main()
