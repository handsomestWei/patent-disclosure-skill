# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG / "tools"))

from classify_distill import main as classify_main
from classify_inputs import classify_file, normalize_patent_text, plan_batch
from distill_paths import normalize_profile_id
from distill_validate import validate_dir, validate_playbook, validate_profile
from init_distill import empty_playbook, init_profile, main as init_main
from validate_distill import main as validate_main


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _profile(**overrides: object) -> dict:
    base = {
        "schema": "patent-distill",
        "version": 1,
        "profile_id": "acme-inv",
        "patent_type": "invention",
        "ownership": "own",
        "suggested_industry": "电池",
        "industry": "",
        "industry_confirmed": False,
        "samples_confirmed": True,
        "tracks": ["strategy"],
        "inputs": [
            {"role": "disclosure", "path": "disclosure.md"},
            {"role": "application", "path": "application.md"},
        ],
        "evidence": {
            "has_disclosure": True,
            "has_application": True,
            "has_publication": False,
            "publication_pair": False,
            "has_family": False,
        },
        "style": {"enabled": False, "kinds": [], "status": "draft"},
        "strategy": {"enabled": True, "strength": "strong", "status": "confirmed", "callable": True},
    }
    base.update(overrides)
    return base


class ProfileIdTests(unittest.TestCase):
    def test_rejects_blank_and_path(self) -> None:
        with self.assertRaises(ValueError):
            normalize_profile_id(" ")
        with self.assertRaises(ValueError):
            normalize_profile_id("a/b")


class ValidateTests(unittest.TestCase):
    def test_strong_confirmed_profile_ok(self) -> None:
        self.assertEqual(validate_profile(_profile()), [])

    def test_third_party_cannot_confirm(self) -> None:
        profile = _profile(
            ownership="third_party",
            inputs=[{"role": "publication", "path": "pub.pdf"}],
            evidence={
                "has_disclosure": False,
                "has_application": False,
                "has_publication": True,
                "publication_pair": False,
                "has_family": False,
            },
            strategy={"enabled": True, "strength": "observe", "status": "confirmed"},
        )
        errors = validate_profile(profile)
        self.assertTrue(any("draft" in item for item in errors))

    def test_strength_must_match_inputs(self) -> None:
        profile = _profile(strategy={"enabled": True, "strength": "weak", "status": "draft"})
        errors = validate_profile(profile)
        self.assertTrue(any("strong" in item for item in errors))

    def test_playbook_rejects_todo_and_long_claim(self) -> None:
        profile = _profile()
        playbook = empty_playbook(profile)
        playbook["status"] = "confirmed"
        playbook["strength"] = "strong"
        errors = validate_playbook(playbook, profile)
        self.assertTrue(any("when_writing_claims" in item for item in errors))
        playbook["apply"] = {
            "when_writing_disclosure": "本案事实只来自当前交底。",
            "when_writing_claims": "独权只收必要特征。",
            "when_writing_spec": "先写够独权支持。",
        }
        playbook["claims"]["independent_grain"] = "x" * 90
        errors = validate_playbook(playbook, profile)
        self.assertTrue(any("过长" in item for item in errors))

    def test_layout_needs_family(self) -> None:
        profile = _profile()
        playbook = empty_playbook(profile)
        playbook["status"] = "confirmed"
        playbook["strength"] = "strong"
        playbook["apply"] = {
            "when_writing_disclosure": "按必要和优选切开。",
            "when_writing_claims": "参数不进独权。",
            "when_writing_spec": "实施例先撑权要。",
        }
        playbook["layout"] = {"enabled": True, "pattern": "core_plus_peripheral"}
        errors = validate_playbook(playbook, profile)
        self.assertTrue(any("layout.enabled" in item for item in errors))


class DirTests(unittest.TestCase):
    def test_skeleton_is_not_deliverable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = init_profile(
                profile_id="acme-inv",
                patent_type="invention",
                ownership="own",
                tracks=["style", "strategy"],
                root=Path(tmp),
            )
            errors = validate_dir(directory)
            self.assertTrue(errors)

    def test_filled_style_and_strategy_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            disclosure = root / "disclosure.md"
            application = root / "application.md"
            _write(disclosure, "交底")
            _write(application, "申请")
            directory = init_profile(
                profile_id="acme-inv",
                patent_type="invention",
                ownership="own",
                tracks=["style"],
                root=root / "out",
            )
            profile = _profile(
                tracks=["style"],
                inputs=[{"role": "application", "path": application.as_posix()}],
                evidence={
                    "has_disclosure": False,
                    "has_application": True,
                    "has_publication": False,
                    "publication_pair": False,
                    "has_family": False,
                },
                style={"enabled": True, "kinds": ["application"], "status": "confirmed"},
                strategy={"enabled": False, "strength": "none", "status": "draft"},
            )
            (directory / "profile.yaml").write_text(
                yaml.safe_dump(profile, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            _write(directory / "style.md", "# 文风\n\n短句，先问题后结构。\n")
            _write(directory / "sections" / "application.md", "权要用短句。\n")
            _write(
                directory / "samples.md",
                f"# 样本\n\n{application.as_posix()}\n",
            )
            self.assertEqual(validate_dir(directory), [])
            self.assertEqual(validate_main(["--dir", str(directory)]), 0)

    def test_init_rejects_style_from_others(self) -> None:
        code = init_main(
            ["--profile-id", "x", "--patent-type", "invention", "--ownership", "third_party", "--tracks", "style"]
        )
        self.assertEqual(code, 2)


class ClassifyTests(unittest.TestCase):
    def test_disclosure_and_application_default_both(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            disclosure = root / "交底.md"
            application = root / "申请.md"
            _write(disclosure, "# 技术交底书\n\n本发明技术方案\n现有技术存在的缺点\n欲保护点\n")
            _write(application, "权利要求书\n\n1. 一种方法，其特征在于\n技术领域\n")
            files = [classify_file(disclosure), classify_file(application)]
            self.assertEqual([item["role"] for item in files], ["disclosure", "application"])
            planned = plan_batch(files, batch_id="case", ownership="")
            self.assertEqual(planned["patent_type"], "invention")
            self.assertEqual(planned["asks"], [])
            self.assertEqual(planned["style"]["tracks"], ["style"])
            self.assertEqual(planned["style"]["inputs"][0]["role"], "application")
            self.assertEqual(len(planned["cases"]), 1)
            self.assertEqual(planned["cases"][0]["strategy"]["strength"], "strong")
            self.assertEqual(
                [item["role"] for item in planned["cases"][0]["inputs"]],
                ["application", "disclosure"],
            )
            code = classify_main([str(disclosure), str(application), "--out-root", str(root / "out")])
            self.assertEqual(code, 0)
            saved = yaml.safe_load((root / "out" / "交底" / "profile.yaml").read_text(encoding="utf-8"))
            self.assertEqual(saved["tracks"], ["style"])
            case = yaml.safe_load((root / "out" / "交底" / "cases" / "申请" / "profile.yaml").read_text(encoding="utf-8"))
            self.assertEqual(case["tracks"], ["strategy"])

    def test_publication_defaults_to_observe_strategy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pub = Path(tmp) / "CN119961390A.pdf"
            _write(pub, "国家知识产权局\n申请公布号 CN119961390A\n权利要求书\n其特征在于\n")
            item = classify_file(pub)
            self.assertEqual(item["role"], "publication_a")
            self.assertEqual(item["patent_type"], "invention")
            planned = plan_batch([item], batch_id="pub", ownership="")
            self.assertEqual(planned["asks"], [])
            self.assertIsNone(planned["style"])
            self.assertEqual(planned["cases"][0]["tracks"], ["strategy"])
            self.assertEqual(planned["cases"][0]["strategy"]["strength"], "observe")

    def test_type_conflict_asks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            invention = root / "a.md"
            utility = root / "b.md"
            _write(invention, "# 技术交底书\n本发明\n欲保护点\n现有技术存在的缺点\n")
            _write(utility, "# 技术交底书\n本实用新型\n欲保护点\n现有技术存在的缺点\n")
            planned = plan_batch(
                [classify_file(invention), classify_file(utility)],
                batch_id="mix",
                ownership="",
            )
            self.assertTrue(any("patent_type" in ask for ask in planned["asks"]))

    def test_two_applications_merge_style_and_split_cases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "甲申请.md"
            second = root / "乙申请.md"
            text = "权利要求书\n\n1. 一种方法，其特征在于\n本发明\n技术领域\n"
            _write(first, text)
            _write(second, text)
            planned = plan_batch([classify_file(first), classify_file(second)], batch_id="batch", ownership="")
            self.assertEqual(len(planned["style"]["inputs"]), 2)
            self.assertEqual(len(planned["cases"]), 2)
            self.assertEqual(
                {item["profile_id"] for item in planned["cases"]},
                {"甲申请", "乙申请"},
            )

    def test_grant_front_page_is_publication_b(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "CN112540831B.pdf"
            _write(
                path,
                "国家知识产权局\n申请公布号 CN 112540831 A\n授 权 公 告 号 CN 112540831 B\n权利要求书\n其特征在于\n",
            )
            item = classify_file(path)
            self.assertEqual(item["role"], "publication_b")
            self.assertEqual(item["grant_pub"], "CN112540831B")
            self.assertEqual(item["laid_open_pub"], "CN112540831A")
            planned = plan_batch([item], batch_id="grant", ownership="third_party")
            evidence = planned["cases"][0]["evidence"]
            self.assertEqual(evidence["pair_in_batch"], False)
            self.assertEqual(planned["cases"][0]["strategy"]["callable"], False)

    def test_normalize_rejoins_page_break(self) -> None:
        raw = (
            "5.一种神经网络处理器的控制方法，其特征在于，所述方法应用于多核神经网络处理\n"
            "权　利　要　求　书 1/3 页\n"
            "2\n"
            "CN111191777B\n"
            "器中，所述方法包括：\n"
        )
        text = normalize_patent_text(raw)
        self.assertIn("神经网络处理器中，所述方法包括：", text)
        self.assertNotIn("权利要求书", text)
        self.assertNotIn("， ", normalize_patent_text("处理器， 其特征在于"))

    def test_cited_prior_art_number_is_not_own_kind(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec = Path(tmp) / "说明书.md"
            _write(
                spec,
                "## 技术领域\n本发明涉及调度。\n## 背景技术\n中国专利申请（公布号：CN216060518U）公开了结构。\n## 具体实施方式\n",
            )
            item = classify_file(spec)
            self.assertEqual(item["role"], "application")
            self.assertEqual(item["patent_type"], "invention")
            self.assertNotIn("种类码", item.get("type_reason") or "")

    def test_four_piece_application_is_one_case(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            disclosure = root / "交底.md"
            app_dir = root / "example_case_20261126"
            app_dir.mkdir()
            _write(disclosure, "# 技术交底书\n\n本发明技术方案\n现有技术存在的缺点\n欲保护点\n")
            _write(app_dir / "权利要求书.md", "权利要求书\n\n1. 一种方法，其特征在于\n本发明\n")
            _write(
                app_dir / "说明书.md",
                "## 技术领域\n本发明涉及调度。\n## 背景技术\n中国专利申请（公布号：CN119781913A）公开了排序。\n## 发明内容\n## 附图说明\n## 具体实施方式\n",
            )
            _write(app_dir / "说明书摘要.md", "# 说明书摘要\n本发明采集指标并派发。\n")
            _write(app_dir / "说明书附图.md", "# 说明书附图\n图1为系统示意图。\n")
            files = [
                classify_file(disclosure),
                classify_file(app_dir / "权利要求书.md"),
                classify_file(app_dir / "说明书.md"),
                classify_file(app_dir / "说明书摘要.md"),
                classify_file(app_dir / "说明书附图.md"),
            ]
            self.assertEqual(files[0]["role"], "disclosure")
            self.assertEqual({item["role"] for item in files[1:]}, {"application"})
            planned = plan_batch(files, batch_id="batch", ownership="")
            self.assertEqual(planned["asks"], [])
            self.assertEqual(len(planned["cases"]), 1)
            self.assertEqual(planned["cases"][0]["profile_id"], "example_case_20261126")
            roles = [item["role"] for item in planned["cases"][0]["inputs"]]
            self.assertEqual(roles.count("application"), 4)
            self.assertEqual(roles.count("disclosure"), 1)
            self.assertEqual(len(planned["style"]["inputs"]), 4)
            self.assertEqual(validate_profile(planned["cases"][0]), [])
            self.assertEqual(validate_profile(planned["style"]), [])

    def test_unknown_file_asks_role(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            note = Path(tmp) / "note.md"
            _write(note, "今天开会讨论进度。")
            planned = plan_batch([classify_file(note)], batch_id="note", ownership="")
            self.assertTrue(any(ask.startswith("role") for ask in planned["asks"]))


if __name__ == "__main__":
    unittest.main()
