# 本包脚本

| 脚本 | 作用 |
|------|------|
| `classify_distill.py` | 读文件，判断文书与专利类型，够格则文风和思路一起建档 |
| `classify_inputs.py` | 分类函数，供脚本和测试调用 |
| `init_distill.py` | 只建空骨架。正常入口用 `classify_distill.py` |
| `validate_distill.py` | 校验 `profile.yaml`、文风文件、`playbook.yaml` |
| `distill_validate.py` | 校验函数，供脚本和测试调用 |
| `distill_spec.py` | 读取 `references/contract.yaml` |
| `distill_paths.py` | 档案 id 与输出目录 |

整仓：`python skills/patent-distill/tools/validate_distill.py --dir outputs/patent-distill/<档案id>`。
