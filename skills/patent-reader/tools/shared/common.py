"""专利解读工具共享入口（兼容）：实现按职责拆在 shared/ 下，外部一律从这里导入。

- paths：包根路径、命令行路径参数、文件名 slug
- obsidian_env：Obsidian 安装与库路径探测、运行配置
- claims：独立 / 从属判断、权要树规范化与校验
- rules：领域路由与 IPC 行业提示（references/*.yaml）
- biblio：全文著录抽取
- text_vocab：全文抽取词表（references/text_vocab.yaml）
"""
from __future__ import annotations

from .biblio import (  # noqa: F401
    extract_application_number,
    extract_assignees,
    extract_cited_pub_numbers,
    extract_filing_date,
    extract_invention_title,
    extract_inventors,
    extract_ipc_codes,
    extract_publication_date,
    organizations_from_assignees,
)
from .claims import (  # noqa: F401
    guess_independent,
    normalize_claim_tree,
    parent_claim_number,
    parent_claim_numbers,
    validate_claim_tree,
)
from .obsidian_env import (  # noqa: F401
    candidate_default_vault_paths,
    detect_obsidian_installed,
    detect_obsidian_vaults,
    persisted_vault_config_path,
    probe_obsidian_environment,
    read_persisted_vault,
    resolve_obsidian_vault,
    runtime_config,
    write_persisted_vault,
)
from .paths import ROOT, optional_path, slugify_pub, slugify_term  # noqa: F401
from .rules import (  # noqa: F401
    load_domain_rules,
    load_ipc_application_hints,
    resolve_domain,
    resolve_ipc_hints,
)
from .text_vocab import DEP_PATTERNS  # noqa: F401
