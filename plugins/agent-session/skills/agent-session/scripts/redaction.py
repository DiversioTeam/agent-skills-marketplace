"""Local redaction for agent session transcripts.

Layer 1 of 2: this runs on the developer's machine before anything is uploaded.
Courage re-runs its own redaction over the published page (layer 2). The secret
shapes mirror Courage's `SECRET_SHAPES` (src/workspace-tools.ts) and both repos
test against the same synthetic fixtures, so keep them in step.

Redaction is best effort. It replaces values, never prints them, and counts what
it replaced by kind so the developer can review the summary before publishing.
"""

from __future__ import annotations

import os
import re
import shlex
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

REDACTED = "[redacted]"

# Staff and tooling domains whose addresses are not customer data.
DEFAULT_ALLOWED_EMAIL_DOMAINS = (
    "diversio.com",
    "optimoteams.com",
    "users.noreply.github.com",
    "noreply.github.com",
    "anthropic.com",
    "openai.com",
    "example.com",
    "example.org",
    "example.net",
)

_NOT_SECRET_ENV_NAME = re.compile(r"(?:_ID|_FILE|_SOCK|_PATH|_DIR|_HOME)$", re.IGNORECASE)
_SECRET_ENV_NAME = re.compile(
    r"(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|PASS|CREDENTIAL|AUTH|COOKIE|SESSION|DSN|PRIVATE)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Rule:
    kind: str
    pattern: re.Pattern[str]
    # Groups named `keep` (or `keep2`) survive; everything else in the match is replaced.
    replacement: str = REDACTED


def _rule(kind: str, pattern: str, flags: int = 0, replacement: str = REDACTED) -> Rule:
    return Rule(kind, re.compile(pattern, flags), replacement)


SECRET_RULES: tuple[Rule, ...] = (
    _rule("private_key", r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----[\s\S]*?-----END (?:[A-Z0-9]+ )*PRIVATE KEY-----"),
    _rule("github_token", r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    _rule("slack_token", r"\b(?:xox[abprs]-|xapp-)[A-Za-z0-9-]{10,}\b"),
    _rule("courage_token", r"\bdvo_(?:courage|mcp)_[A-Za-z0-9_-]{16,}"),
    _rule("courage_token", r"\bcmcp_(?:at|rt)_[A-Za-z0-9_-]{43}"),
    _rule("aws_key_id", r"\b(?:AKIA|ASIA|ABIA|ACCA)[A-Z0-9]{16}\b"),
    _rule(
        "aws_secret",
        r"(?P<keep>\"?(?:SecretAccessKey|SessionToken|aws_secret_access_key|aws_session_token|AWS_SECRET_ACCESS_KEY"
        r"|AWS_SESSION_TOKEN|secret_access_key|session_token)\"?\s*[:=]\s*\"?)[A-Za-z0-9/+=]{16,}",
    ),
    _rule("aws_secret", r"\b(?:IQoJb3JpZ2lu|FwoGZXIvYXdz)[A-Za-z0-9/+=]{40,}"),
    # A bare 40-character AWS secret key standing alone, as Courage matches it. Lowercase-hex SHAs never match.
    _rule(
        "aws_secret",
        r"(?:(?<=^)|(?<=[\s\"'=:,(\[]))(?!/)(?=[A-Za-z0-9/+=]{0,39}[A-Z])(?=[A-Za-z0-9/+=]{0,39}[a-z])"
        r"[A-Za-z0-9/+=]{40}(?=$|[\s\"',)\]])",
        re.MULTILINE,
    ),
    _rule("api_key", r"\b(?:sk-[A-Za-z0-9_-]{16,}|(?:sk|rk|pk)_(?:live|test)_[A-Za-z0-9]{16,}|ops_[A-Za-z0-9_-]{20,})\b"),
    _rule("api_key", r"\bAIza[0-9A-Za-z_-]{35}\b"),
    _rule("api_key", r"\bnpm_[A-Za-z0-9]{36}\b"),
    _rule("jwt", r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
    _rule("auth_header", r"(?P<keep>\b(?:Bearer|Basic|Token)\s+)[A-Za-z0-9._~+/=-]{16,}", re.IGNORECASE),
    _rule("auth_header", r"(?P<keep>\b(?:authorization|x-api-key|api-key|x-auth-token)[\"']?\s*[:=]\s*[\"']?)[^\s\"'\n][^\"'\n]*", re.IGNORECASE),
    _rule("cookie", r"(?P<keep>\b(?:set-)?cookie[\"']?\s*[:=]\s*[\"']?)[^\"'\n]+", re.IGNORECASE),
    _rule("url_credentials", r"(?P<keep>\b[a-z][a-z0-9+.-]*://[^\s/@:]+:)[^\s/@]+(?P<keep2>@)", re.IGNORECASE),
    _rule("url_credentials", r"(?P<keep>\bhttps?://)[0-9a-f]{32}(?P<keep2>@)", re.IGNORECASE),
    _rule(
        "oauth_param",
        r"(?P<keep>[?&#;](?:code|state|access_token|refresh_token|id_token|token|client_secret|code_verifier|sig|signature"
        r"|X-Amz-Signature|X-Amz-Credential|X-Amz-Security-Token|password|api_key|apikey)=)[^&\s\"'#<>]+",
        re.IGNORECASE,
    ),
    # Named assignments whose value looks like a credential (letters and digits, no call syntax).
    _rule(
        "named_secret",
        r"(?P<keep>\b[A-Za-z0-9_]*(?:password|passwd|secret|token|api_?key|access_?key|private_?key|client_?secret)"
        r"[\"']?\s*[:=]\s*[\"']?)(?=[A-Za-z0-9_\-./+=~]*\d)(?=[A-Za-z0-9_\-./+=~]*[A-Za-z])[A-Za-z0-9_\-./+=~]{8,}",
        re.IGNORECASE,
    ),
)

EMAIL = re.compile(r"(?<![\w.+-])[A-Za-z0-9._%+-]{1,64}@(?P<domain>[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})\b")
PHONE = re.compile(r"(?<![\w/.-])(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?![\w/-])")

# Keys that mark a tool output as rows of personal data (a query result, a CSV, a JSON dump).
PERSONAL_KEYS = re.compile(
    r"\b(?:e-?mail(?:_address)?|first_?name|last_?name|full_?name|phone(?:_number)?|date_of_birth|dob|"
    r"home_address|street_address|postal_code|zip_code|ssn|sin_number)\b",
    re.IGNORECASE,
)


@dataclass
class Redactor:
    known_secrets: tuple[str, ...] = ()
    allowed_email_domains: tuple[str, ...] = DEFAULT_ALLOWED_EMAIL_DOMAINS
    counts: Counter[str] = field(default_factory=Counter)

    def text(self, value: str) -> str:
        if not value:
            return value
        result = value
        for secret in self.known_secrets:
            if secret in result:
                self.counts["known_secret"] += result.count(secret)
                result = result.replace(secret, REDACTED)
        for rule in SECRET_RULES:
            result = rule.pattern.sub(self._replacer(rule), result)
        result = EMAIL.sub(self._email, result)
        result = PHONE.sub(self._phone, result)
        return result

    def _replacer(self, rule: Rule) -> Callable[[re.Match[str]], str]:
        def replace(match: re.Match[str]) -> str:
            groups = match.groupdict()
            if REDACTED in match.group(0) and match.group(0).strip(" \"'") == REDACTED:
                return match.group(0)
            self.counts[rule.kind] += 1
            return f"{groups.get('keep') or ''}{rule.replacement}{groups.get('keep2') or ''}"

        return replace

    def _email(self, match: re.Match[str]) -> str:
        domain = match.group("domain").lower()
        if any(domain == allowed or domain.endswith(f".{allowed}") for allowed in self.allowed_email_domains):
            return match.group(0)
        self.counts["email"] += 1
        return "[email]"

    def _phone(self, match: re.Match[str]) -> str:
        self.counts["phone"] += 1
        return "[phone]"


def looks_like_personal_rows(text: str) -> bool:
    """True when an output looks like rows of people: several personal keys repeated."""
    hits = PERSONAL_KEYS.findall(text)
    if len(hits) < 3:
        return False
    distinct = {hit.lower().replace("_", "").replace("-", "") for hit in hits}
    return len(distinct) >= 2 or len(hits) >= 6


# ---- Known secret values ---------------------------------------------------------------------------------------------

_ENV_LINE = re.compile(r"^\s*(?:export\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_.-]*)\s*=\s*(?P<value>.*)$")


def _env_file_values(path: Path) -> Iterable[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    for line in text.splitlines():
        match = _ENV_LINE.match(line)
        if not match:
            continue
        value = match.group("value").strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        yield value


def collect_known_secrets(roots: Iterable[Path], environ: dict[str, str] | None = None) -> tuple[str, ...]:
    """Secret values to replace by exact match: .env* files under each root and secret-named environment variables.

    Values are kept in memory only. Short or trivial values are skipped so common words are not redacted.
    """
    values: set[str] = set()
    for root in roots:
        try:
            candidates = [entry for entry in root.iterdir() if entry.is_file() and (entry.name == ".env" or entry.name.startswith(".env."))]
        except OSError:
            continue
        for candidate in candidates:
            if candidate.name.endswith((".example", ".sample", ".template")):
                continue
            values.update(_env_file_values(candidate))
    for name, value in (os.environ if environ is None else environ).items():
        # Ids, paths, and sockets name where a secret lives, not the secret, and would redact ordinary paths.
        if _SECRET_ENV_NAME.search(name) and not _NOT_SECRET_ENV_NAME.search(name) and not value.startswith(("/", "~")):
            values.add(value)
    meaningful = {value for value in values if len(value) >= 8 and not value.isdigit() and value.lower() not in {"true", "false", "none", "null"}}
    # Longest first, so a secret that contains another is replaced whole.
    return tuple(sorted(meaningful, key=len, reverse=True))


# ---- Structural withholding ------------------------------------------------------------------------------------------

_CREDENTIAL_DIRECTORIES = {".ssh", ".aws", ".azure", ".kube", ".gnupg", ".docker"}
_CREDENTIAL_FILES = {
    ".npmrc", ".pypirc", ".netrc", "_netrc", ".git-credentials", "auth.json", "credentials", "credentials.json",
    "credentials.yaml", "credentials.yml", "secrets.json", "secrets.yaml", "secrets.yml", "id_rsa", "id_dsa",
    "id_ecdsa", "id_ed25519", "cookies", "cookies.txt", "cookies.sqlite",
}


# `secrets-prod.json`, `credentials.local`: data files named for credentials, but not source code about them.
_CREDENTIAL_PREFIXES = ("secrets", "credentials", ".secrets", "service-account", "service_account")
_SOURCE_SUFFIXES = (".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".rb", ".go", ".rs", ".java", ".kt", ".md", ".html", ".css")


def is_credential_path(path: str) -> bool:
    parts = path.lower().replace("\\", "/").split("/")
    filename = parts[-1]
    return (
        any(part in _CREDENTIAL_DIRECTORIES for part in parts)
        or filename in _CREDENTIAL_FILES
        or (filename.startswith(_CREDENTIAL_PREFIXES) and not filename.endswith(_SOURCE_SUFFIXES))
        or filename == ".env"
        or (filename.startswith(".env.") and not filename.endswith((".example", ".sample", ".template")))
        or re.search(r"\.(?:pem|key|p12|pfx|jks|keystore)$", filename) is not None
    )


_SECRET_COMMANDS = re.compile(
    r"(?:^|[;&|(\s])(?:env|printenv|set|export\s+-p)\s*(?:$|[;&|)])"
    r"|\bop\s+(?:read|inject|run|item\s+get|document\s+get)\b"
    r"|\bsecurity\s+find-(?:generic|internet)-password\b"
    r"|\bgh\s+auth\s+(?:token|status\s+(?:-t|--show-token))\b"
    r"|\baws\s+(?:configure\s+(?:export-credentials|get)|sts\s+get-session-token|secretsmanager\s+get-secret-value|ssm\s+get-parameters?)\b"
    r"|\bkubectl\s+get\s+secrets?\b"
    r"|\bcloudflared\s+access\s+token\b"
    r"|\bgcloud\s+auth\s+print-(?:access|identity)-token\b"
    r"|\b(?:cat|less|more|head|tail|bat|sed|awk|grep|rg|source|\.)\s+[^\n;|&]*(?:\.env\b(?!\.(?:example|sample|template))|\.pem\b|id_(?:rsa|ed25519|ecdsa)\b|\.netrc\b|\.npmrc\b|credentials\b|\.git-credentials\b)",
    re.MULTILINE,
)

# Commands that reach a database, a shell, or Django on another host.
_DATA_COMMANDS = re.compile(
    r"\b(?:ssh|scp|psql|pg_dump|pg_restore|mysql|mysqldump|mongo(?:sh)?|redis-cli|heroku|kubectl|manage\.py|django-admin"
    r"|ecs\s+execute-command|ssm\s+start-session|aws\s+rds|aws\s+dynamodb|curl|wget|http|httpie)\b",
)
_PROD_OR_STAGING = re.compile(
    r"\b(?:prod|production|staging|stage|stg|live)\b|[\w.-]*(?:prod|staging)[\w-]*\.[\w.-]+"
    r"|DJANGO_SETTINGS_MODULE=\S*(?:prod|staging)|--settings[= ]\S*(?:prod|staging)",
    re.IGNORECASE,
)
_DATA_TOOL_NAMES = re.compile(r"(?:django|database|sql|query|postgres|mysql|mongo|redis|bigquery|snowflake)", re.IGNORECASE)


def _path_tokens(command: str) -> list[str]:
    """Path-like words in a shell command (`cat ~/.docker/config.json`, `source .env`), for the shared path classifier."""
    try:
        words = shlex.split(command, posix=True)
    except ValueError:
        words = command.split()
    tokens = []
    for word in words:
        for part in re.split(r"[;&|<>()=,\s]+", word):
            part = part.strip("'\"`")
            if "/" in part or part.startswith(".") or "." in part:
                tokens.append(part)
    return tokens


def withheld_reason(tool_name: str, tool_input: dict[str, object]) -> str | None:
    """Why a tool call's output must not be published at all, or None."""
    for key in ("file_path", "path", "notebook_path"):
        value = tool_input.get(key)
        if isinstance(value, str) and is_credential_path(value):
            return "credential file"
    command = tool_input.get("command") or tool_input.get("cmd")
    if isinstance(command, list):
        command = " ".join(str(part) for part in command)
    if isinstance(command, str):
        if any(is_credential_path(token) for token in _path_tokens(command)):
            return "credential file"
        if _SECRET_COMMANDS.search(command):
            return "command prints credentials"
        if _DATA_COMMANDS.search(command) and _PROD_OR_STAGING.search(command):
            return "prod or staging data access"
    if _DATA_TOOL_NAMES.search(tool_name):
        flat = " ".join(str(value) for value in tool_input.values())
        if _PROD_OR_STAGING.search(flat) or tool_name.startswith("mcp__"):
            return "prod or staging data access"
    return None
