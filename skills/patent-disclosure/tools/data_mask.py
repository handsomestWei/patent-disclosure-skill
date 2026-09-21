import re
import os
import sys
from pathlib import Path

OUT_ROOT = "outputs"

SECRET_PATTERNS = [
    # API Keys (various providers)
    re.compile(r'(?:api[_-]?key|apikey)\s*[=:]\s*["\']?([A-Za-z0-9]{20,})["\']?', re.IGNORECASE),
    re.compile(r'(?:sk|pk)[_-](?:live|test|prod|dev)[_-][A-Za-z0-9]{20,}', re.IGNORECASE),

    # AWS Credentials
    re.compile(r'AKIA[0-9A-Z]{16}', re.IGNORECASE),  # AWS Access Key ID
    re.compile(r'(?:aws[_-]?)?(?:secret[_-]?access[_-]?key|aws[_-]?secret[_-]?key)\s*[=:]\s*["\']?([A-Za-z0-9/+=]{40})["\']?', re.IGNORECASE),

    # Azure Credentials
    re.compile(r'(?:azure|aad)[_-]?(?:client[_-]?secret|tenant[_-]?id)\s*[=:]\s*["\']?[^\s"\'<>]{10,}["\']?', re.IGNORECASE),

    # Google Cloud Credentials
    re.compile(r'"project_id"\s*:\s*"[^"]+"', re.IGNORECASE),
    re.compile(r'"private_key_id"\s*:\s*"[^"]+"', re.IGNORECASE),

    # Alibaba Cloud AccessKey
    re.compile(r'LTAI[A-Za-z0-9]{12,20}'),

    # Tencent Cloud
    re.compile(r'(?:secret[_-]?id|secret[_-]?key)\s*[=:]\s*["\']?[A-Za-z0-9]{20,}["\']?', re.IGNORECASE),

    # Generic API tokens
    re.compile(r'(?:bearer|token|auth)\s+(?:[A-Za-z0-9\-_]{20,})', re.IGNORECASE),
    re.compile(r'(?:x[_-]?api[_-]?key|api[_-]?token)\s*[=:]\s*["\']?([A-Za-z0-9]{16,})["\']?', re.IGNORECASE),

    # Database connection strings
    re.compile(r'(?:mongodb|postgres|mysql|redis|amqp)://[^\s"\'<>]{10,}', re.IGNORECASE),
    re.compile(r'(?:server|host|database)\s*[=:]\s*["\']?[^\s"\'<>]{5,}', re.IGNORECASE),

    # Passwords
    re.compile(r'(?:password|passwd|pwd)\s*[=:]\s*["\']?[^\s"\'<>]{8,}["\']?', re.IGNORECASE),

    # Private keys (PEM format)
    re.compile(r'-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----'),
    re.compile(r'-----BEGIN OPENSSH PRIVATE KEY-----'),
    re.compile(r'-----BEGIN PGP PRIVATE KEY BLOCK-----'),

    # OAuth/Service Account
    re.compile(r'"type"\s*:\s*"service_account"', re.IGNORECASE),
    re.compile(r'(?:oauth|client)[_-]?(?:secret|token)\s*[=:]\s*["\']?[A-Za-z0-9\-_]{16,}["\']?', re.IGNORECASE),

    # GitHub/GitLab tokens
    re.compile(r'ghp_[A-Za-z0-9]{36}'),  # GitHub Personal Access Token
    re.compile(r'glpat-[A-Za-z0-9\-]{20,}'),  # GitLab Personal Access Token
    re.compile(r'github_pat_[A-Za-z0-9]{22}_[A-Za-z0-9]{59}'),  # GitHub Fine-grained PAT

    # Slack tokens
    re.compile(r'xox[baprs]-[0-9]{10,13}-[a-zA-Z0-9-]+'),

    # Stripe payment keys
    re.compile(r'sk_(?:live|test)_[A-Za-z0-9]{24,}'),
    re.compile(r'rk_(?:live|test)_[A-Za-z0-9]{24,}'),

    # Twilio credentials
    re.compile(r'AC[a-f0-9]{32}'),  # Account SID
    re.compile(r'SK[a-f0-9]{32}'),  # API Key

    # SendGrid API key
    re.compile(r'SG\.[A-Za-z0-9_-]{22,}\.[A-Za-z0-9_-]{43,}'),

    # Firebase API Key
    re.compile(r'AIza[0-9A-Za-z_-]{35}'),

    # JWT tokens
    re.compile(r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'),

    # Base64 encoded credentials
    re.compile(r'(?:key|secret|token|password|credential)\s*[=:]\s*["\']?([A-Za-z0-9+/]{40,}={0,2})["\']?', re.IGNORECASE),

    # Webhook URLs with tokens
    re.compile(r'https?://[^\s]*(?:hook|callback|webhook)[^\s]*[?&](?:token|key|secret)=[^\s&]{10,}', re.IGNORECASE),

    # CI/CD credentials
    re.compile(r'(?:docker[_-]?password|registry[_-]?token)\s*[=:]\s*["\']?[^\s"\'<>]{8,}["\']?', re.IGNORECASE),
    re.compile(r'(?:k8s|kube)[_-]?(?:token|secret)\s*[=:]\s*["\']?[A-Za-z0-9._-]{20,}["\']?', re.IGNORECASE),
    re.compile(r'jenkins[_-]?(?:token|password|secret)\s*[=:]\s*["\']?[^\s"\'<>]{10,}["\']?', re.IGNORECASE),

    # Session IDs and cookies
    re.compile(r'(?:session[_-]?id|sid|phpsessid|jsessionid)\s*[=:]\s*["\']?[A-Za-z0-9]{16,}["\']?', re.IGNORECASE),
    re.compile(r'(?:auth[_-]?token|access[_-]?token|refresh[_-]?token)=([A-Za-z0-9._-]{20,})', re.IGNORECASE),

    # Mobile signing keys
    re.compile(r'(?:signing[_-]?key|store[_-]?password|key[_-]?password)\s*[=:]\s*["\']?[^\s"\'<>]{6,}["\']?', re.IGNORECASE),

    # SSH host keys and fingerprints
    re.compile(r'(?:ecdsa-sha2-nistp256|ssh-rsa|ssh-ed25519)\s+[A-Za-z0-9+/=]{20,}'),

    # Windows product keys
    re.compile(r'[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}'),

    # Generic high-entropy assignments (catches custom secret formats)
    re.compile(r'(?:secret|key|token|credential)\s*[=:]\s*["\']([A-Za-z0-9+/=_-]{32,})["\']', re.IGNORECASE),

    # Chinese secret patterns (中文密钥模式)
    re.compile(r'(?:密码|口令|pwd)\s*[=:：]\s*["\']?[^\s"\'<>]{8,}["\']?'),
    re.compile(r'(?:密钥|私钥|公钥|access[_-]?key|secret[_-]?key)\s*[=:：]\s*["\']?[A-Za-z0-9+/=_-]{16,}["\']?'),
    re.compile(r'(?:令牌|token|鉴权码)\s*[=:：]\s*["\']?[A-Za-z0-9._-]{16,}["\']?'),
    re.compile(r'(?:凭证|credential|证书)\s*[=:：]\s*["\']?[^\s"\'<>]{10,}["\']?'),
    re.compile(r'(?:数据库连接|数据库地址|db[_-]?url|conn[_-]?str)\s*[=:：]\s*["\']?[^\s"\'<>]{10,}["\']?'),
    re.compile(r'(?:服务器|主机|host|地址)\s*[=:：]\s*["\']?[^\s"\'<>]{5,}["\']?'),
]
PII_PATTERNS = [
    # Email addresses
    re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),

    # Phone numbers (various formats)
    re.compile(r'(?:\+?86)?1[3-9]\d{9}'),  # Chinese phone numbers
    re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),  # US phone numbers
    re.compile(r'\+\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}'),  # International

    # Chinese ID card numbers (18 digits)
    re.compile(r'\b\d{17}[\dXx]\b'),

    # Social Security Numbers (US)
    re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),

    # Credit card numbers (basic pattern, not validated)
    re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),

    # IP addresses (private/internal)
    re.compile(r'\b(?:10|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.\d{1,3}\.\d{1,3}\b'),

    # MAC addresses
    re.compile(r'(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}'),

    # Internal domain names
    re.compile(r'(?:[\w-]+\.)+(?:internal|local|corp|intranet|private|lan)(?:\.[a-z]{2,})?', re.IGNORECASE),

    # VPN configurations
    re.compile(r'(?:vpn|openvpn|wireguard)[_-]?(?:key|secret|config)\s*[=:]\s*["\']?[^\s"\'<>]{10,}["\']?', re.IGNORECASE),

    # Proxy server credentials
    re.compile(r'(?:proxy|http_proxy|https_proxy)\s*[=:]\s*["\']?http[s]?://[^\s"\'<>:]+:[^\s"\'<>]+@[^\s"\'<>]+["\']?', re.IGNORECASE),

    # Windows credentials
    re.compile(r'(?:windows[_-]?credential|ntlm[_-]?hash|kerberos[_-]?key)\s*[=:]\s*["\']?[^\s"\'<>]{10,}["\']?', re.IGNORECASE),

    # Environment variable references with sensitive names
    re.compile(r'\$\{?(?:SECRET|PASSWORD|TOKEN|API_KEY|PRIVATE_KEY)[_A-Z]*\}?', re.IGNORECASE),

    # Chinese PII patterns (中文个人信息)
    re.compile(r'(?:姓名|名字|真实姓名|联系人)\s*[=:：]\s*[\u4e00-\u9fa5]{2,4}'),
    re.compile(r'(?:地址|住址|家庭住址|详细地址|通讯地址)\s*[=:：]\s*[\u4e00-\u9fa50-9a-zA-Z#\-]{10,}'),
    re.compile(r'(?:身份证|身份证号|身份证号码|证件号)\s*[=:：]\s*\d{17}[\dXx]'),
    re.compile(r'(?:邮箱|电子邮箱|邮件地址)\s*[=:：]\s*[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),
    re.compile(r'(?:手机|手机号|联系电话|联系方式|电话号码)\s*[=:：]\s*(?:\+?86)?1[3-9]\d{9}'),
    re.compile(r'(?:银行卡|银行卡号|银行卡号码|卡号|号码)\s*[=:：]\s*\d{16,19}'),
    re.compile(r'(?:护照|护照号|护照号码)\s*[=:：]\s*[A-Za-z0-9]{8,12}'),
]
SENSITIVE_KEY_PATTERNS = [
    # 匹配 key = value, key: value, key value 等格式
    re.compile(r'((?:api[_-]?key|apikey|secret[_-]?key|access[_-]?key|private[_-]?key|password|passwd|pwd|token|auth[_-]?token|bearer|credential)[\s:=]+)["\']?([^\s"\']{8,})["\']?', re.IGNORECASE),
    # 匹配数据库连接信息
    re.compile(r'((?:connection[_-]?string|conn[_-]?str|database[_-]?url|db[_-]?url)[\s:=]+)["\']?([^\s"\']{10,})["\']?', re.IGNORECASE),
    # 匹配 AWS secret access key
    re.compile(r'((?:aws[\s_-]*)?(?:secret[\s_-]+access[\s_-]+key)[\s:=]+)["\']?([A-Za-z0-9/+=]{20,})["\']?', re.IGNORECASE),
    # 匹配中文密钥格式 (密码 = xxx, 密钥：xxx, 令牌: xxx)
    re.compile(r'((?:密码|密钥|口令|凭证|令牌|鉴权码|私钥|公钥|证书|数据库密码|数据库密钥|访问密钥)[\s:=：]+)["\']?([^\s"\']{8,})["\']?'),
    # 匹配无分隔符的中文密钥格式 (密码xxx)，排除后面跟中文字符的情况（如"密码学"、"密码保护"）
    re.compile(r'((?:密码|密钥|口令|凭证|令牌|鉴权码|私钥|公钥|证书|数据库密码|数据库密钥|访问密钥))(?![\u4e00-\u9fa5\s:=：])["\']?([A-Za-z0-9+/=_-]{8,})["\']?'),
    # 敏感键名后面跟随短字符串值（6-16位）
    re.compile(r'''(['"]?)(?:password|passwd|pwd|secret|api_key|apikey|token|auth|credential|private_key|privatekey|access_key|accesskey|client_secret|admin_key|adminkey)['"]?(?:\s*[:=]\s*|\s+)(?<![\w/+=])['"]?([A-Za-z0-9+/=_\-]{6,16})(?![\w/+=])['"]?''', re.IGNORECASE),
    # 主机地址
    re.compile(r'''(['"]?)(?:host|server|addr)['"]?(?:\s*[:=]\s*|\s+)(?<![\w])['"]?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})['"]?''', re.IGNORECASE),
    # 带后缀的密钥变量名（如 ADMIN_KEY = "xxx"）
    re.compile(r'''([A-Z][A-Z0-9_]*(?:_?KEY|_?SECRET|_?TOKEN|_?PASSWORD|_?CREDENTIAL))\s*(?:=\s*|:?\s*)["']([A-Za-z0-9+/=_\-]{6,16})["']'''),
]

# 大概率无用的目录
SKIP_DIRS = frozenset({
    # ========== 版本控制系统 ==========
    '.git', '.svn', '.hg', '.bzr',

    # ========== IDE和编辑器配置 ==========
    '.idea', '.vscode', '.vs', '.eclipse', '.settings',
    '.project', '.classpath', '.factorypath',

    # ========== Python虚拟环境和缓存 ==========
    '__pycache__', 'venv', 'env', '.venv', '.env', '.conda',
    '.mypy_cache', '.pytest_cache', '.tox', '.nox',
    'eggs', 'wheels', 'dist-info', 'egg-info', '.eggs',
    '.hypothesis',

    # ========== Node.js相关 ==========
    'node_modules', 'bower_components', '.npm', '.yarn',
    '.pnpm-store', '.pnp',

    # ========== Java/Gradle/Maven ==========
    'target', '.gradle', 'gradle', '.mvn', '.m2',

    # ========== C/C++/Rust构建 ==========
    'cmake-build-debug', 'cmake-build-release', '.ccls-cache',
    'build', 'out', 'obj', 'Release', 'Debug',

    # ========== Go ==========
    'vendor',

    # ========== Rust ==========
    'target',

    # ========== 构建产物和分发目录 ==========
    'dist', '.next', '.nuxt', '.output', '.svelte-kit',

    # ========== .NET ==========
    'packages', '.nuget',

    # ========== 文档构建产物 ==========
    '_build', 'docs/_build', '_site',

    # ========== 测试覆盖率报告 ==========
    'htmlcov', '.coverage', '.nyc_output',

    # ========== Docker和容器 ==========
    '.docker',

    # ========== IaC工具 ==========
    '.terraform', '.serverless',

    # ========== 包管理器缓存 ==========
    '.cache', '.parcel-cache', '.vite',

    # ========== 操作系统隐藏文件 ==========
    '.Spotlight-V100', '.Trashes', '.fseventsd',

    # ========== 日志和临时文件 ==========
    'logs', 'tmp', 'temp', '.tmp',

    # ========== 文档和笔记 ==========
    '.obsidian', '.notion',

    # ========== 本技能产生的文件 ==========
    OUT_ROOT,
})

 # 大概率有用的文件扩展名
# 大概率无用的文件
SKIP_FILES = frozenset({
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "Cargo.lock", "poetry.lock", "Gemfile.lock",
    "composer.lock", "go.sum", "go.work.sum",
})
CODE_EXTENSIONS = frozenset({
    '.py', '.pyw', '.pyi', '.pyx',
    '.ts', '.tsx', '.mts', '.cts', '.js', '.jsx', '.mjs', '.cjs', '.ejs', '.ets',
    '.go', '.rs', '.java', '.groovy', '.gradle',
    '.cpp', '.cc', '.cxx', '.c', '.h', '.hpp', '.cu', '.cuh', '.metal',
    '.rb', '.rake', '.swift', '.kt', '.kts', '.cs', '.scala', '.php',
    '.lua', '.luau', '.toc', '.zig', '.ex', '.exs', '.m', '.mm',
    '.ml', '.mli', '.jl', '.vue', '.svelte', '.astro', '.dart', '.v', '.sv', '.svh',
    '.sql', '.r', '.f', '.F', '.f90', '.F90', '.f95', '.F95', '.f03', '.F03', '.f08', '.F08',
    '.pas', '.pp', '.dpr', '.dpk', '.lpr', '.inc', '.dfm', '.lfm', '.lpk',
    '.sh', '.bash', '.zsh', '.fish', '.ash', '.ksh', '.csh',
    '.tf', '.tfvars', '.hcl', '.dm', '.dme', '.dmi', '.dmm', '.dmf',
    '.sln', '.slnx', '.csproj', '.fsproj', '.vbproj', '.xaml', '.razor', '.cshtml', '.cls', '.trigger',
    '.lisp', '.cl', '.lsp', '.scm', '.rkt',
    '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf', '.config',
    '.json', '.jsonc', '.json5', '.jsonnet',
    '.xml', '.xsd', '.xsl', '.xslt',
    '.env', '.envrc', '.env.local', '.env.development', '.env.production',
    '.properties', '.prop', '.opts',
    '.md', '.markdown', '.mdown', '.mkd', '.mkdn',
    '.dockerfile', '.dockerignore',
    '.gitignore', '.gitattributes', '.editorconfig', '.prettierrc', '.eslintrc',
    '.gradle', '.gradle.kts',
    '.bazel', '.bzl', '.BUILD', '.BUILD.bazel',
    '.browserslistrc', '.nvmrc', '.node-version',
    '.gemfile', '.gemspec',
    'Makefile', '.mk', 'CMakeLists.txt', 'cmake',
    'Vagrantfile', 'Ansiblefile',
    '.pls', '.pkb', '.pks', '.fnc', '.trg', '.syn', '.mv', '.vw',
    '.tcl', '.tk',
    '.awk', '.gawk', '.m4',
    '.bat', '.cmd', '.ps1', '.psm1',
    '.reg', '.inf',
    '.ino', '.pde',
    '.nb', '.wb', '.ipynb',
})

def content_remove_sensitive(content: str) -> str:
    """
    通用敏感信息脱敏。
    移除密钥/凭证、个人信息（PII）、敏感键值对等。
    """
    if not content:
        return content

    content = re.sub(
        r'-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----',
        '[REDACTED]',
        content,
        flags=re.DOTALL
    )

    for p in SECRET_PATTERNS:
        content = p.sub('[REDACTED]', content)

    for p in PII_PATTERNS:
        content = p.sub('[REDACTED]', content)

    for p in SENSITIVE_KEY_PATTERNS:
        content = p.sub(lambda m: m.group(1) + '[REDACTED]', content)

    return content


def examine_code_file(project_root: str) -> None:
    """
    递归扫描目录下的所有代码文件，检测是否包含敏感信息。
    Args:
        project_root: 项目根目录路径
    """
    sensitive_files = []

    for root, dirs, files in os.walk(project_root):
        # 跳过不需要扫描的目录
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and OUT_ROOT != d]

        for file in files:
            # 跳过不需要扫描的文件
            if file in SKIP_FILES:
                continue

            file_path = Path(root) / file
            file_extension = file_path.suffix.lower()

            # 只检查代码文件
            if file_extension not in CODE_EXTENSIONS:
                continue

            # 尝试读取文件内容
            try:
                for encoding in ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'latin-1']:
                    try:
                        with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                            original_content = f.read()

                        # 调用敏感信息过滤函数
                        cleaned_content = content_remove_sensitive(original_content)

                        # 检查是否包含 [REDACTED] 标记
                        if '[REDACTED]' in cleaned_content:
                            # 找到所有 [REDACTED] 的位置并提取上下文
                            redacted_positions = []
                            start = 0
                            while True:
                                pos = cleaned_content.find('[REDACTED]', start)
                                if pos == -1:
                                    break

                                # 提取前后各50个字符作为上下文
                                context_start = max(0, pos - 50)
                                context_end = min(len(cleaned_content), pos + len('[REDACTED]') + 50)
                                context = cleaned_content[context_start:context_end]

                                # 计算行号
                                line_number = cleaned_content[:pos].count('\n') + 1

                                redacted_positions.append({
                                    'line': line_number,
                                    'context': context.strip()
                                })
                                start = pos + 1

                            sensitive_files.append({
                                'file_path': str(file_path),
                                'relative_path': str(file_path.relative_to(project_root)) if project_root else str(file_path),
                                'encoding': encoding,
                                'redacted_count': len(redacted_positions),
                                'redacted_positions': redacted_positions
                            })

                            rel_path = file_path.relative_to(project_root) if project_root else file_path
                            print(f"\n[警告] {rel_path} ({len(redacted_positions)}处)")
                            for idx, pos_info in enumerate(redacted_positions[:3], 1):
                                ctx = pos_info['context']
                                # 截断过长的上下文
                                if len(ctx) > 80:
                                    ctx = ctx[:77] + '...'
                                print(f"  Line {pos_info['line']}: ...{ctx}")
                            if len(redacted_positions) > 3:
                                print(f"  ...")

                        break
                    except UnicodeDecodeError:
                        continue
                    except Exception as e:
                        print(f"[错误] 读取文件失败 {file_path}: {e}")
                        break

            except Exception as e:
                print(f"[错误] 处理文件失败 {file_path}: {e}")
                continue

    # 打印汇总信息
    if sensitive_files:
        total = sum(f['redacted_count'] for f in sensitive_files)
        print(f"\n[检测完成] {len(sensitive_files)}个文件含敏感信息:")
        for file_info in sensitive_files:
            lines = ', '.join(str(p['line']) for p in file_info['redacted_positions'][:5])
            print(f"  {file_info['relative_path']}: Line {lines}")
    else:
        print(f"\n[检测完成] 未发现敏感信息")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python data_mask.py examine_code_file <project_root>")
        sys.exit(1)

    command = sys.argv[1]

    if command == "examine_code_file":
        if len(sys.argv) < 3:
            print("错误: examine_code_file 需要一个参数: <project_root>")
            sys.exit(1)
        project_root = sys.argv[2]
        print(f"开始扫描敏感信息: {project_root}")
        examine_code_file(project_root)

    else:
        print(f"Unknown command: {command}")
        print("Available commands: examine_code_file")
        sys.exit(1)