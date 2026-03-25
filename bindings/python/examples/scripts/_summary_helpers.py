import os
import re
from typing import Optional, Tuple

DB_ALIAS_MAP = {
    "sqlite_native": "sqlite",
}

RUN_LABEL_DB_ALIAS_RE = re.compile(r"(^|_)sqlite_native(?=_|$)", re.IGNORECASE)


MEM_TOKEN_RE = re.compile(
    r"(?:^|[_=])(mem\d+[a-z0-9]*|m\d+[a-z0-9]*)(?=$|[_=])",
    re.IGNORECASE,
)
MEM_EQUALS_RE = re.compile(r"(?:^|[_=])mem=([a-z0-9]+)(?=$|[_=])", re.IGNORECASE)
TRAILING_MEM_TOKEN_RE = re.compile(
    r"_(?:mem\d+[a-z0-9]*|m\d+[a-z0-9]*|memory)$",
    re.IGNORECASE,
)


def normalize_db_label(value: Optional[str]) -> Optional[str]:
    if value in (None, ""):
        return value
    text = str(value).strip()
    return DB_ALIAS_MAP.get(text.lower(), text)


def normalize_run_label_aliases(value: Optional[str]) -> Optional[str]:
    if value in (None, ""):
        return value
    text = str(value).strip()
    return RUN_LABEL_DB_ALIAS_RE.sub(lambda m: f"{m.group(1)}sqlite", text)


def normalize_mem_tag(value: Optional[str]) -> Optional[str]:
    if value in (None, ""):
        return None

    text = re.sub(r"[^a-z0-9]", "", str(value).strip().lower())
    if not text:
        return None

    if text.startswith("mem") and len(text) > 3 and text[3].isdigit():
        suffix = text[3:]
    elif text.startswith("m") and len(text) > 1 and text[1].isdigit():
        suffix = text[1:]
    else:
        suffix = text

    if not suffix:
        return None
    return f"mem{suffix}"


def infer_mem_tag(
    mem_limit: Optional[str] = None,
    run_label: Optional[str] = None,
    run_dir: Optional[str] = None,
) -> Optional[str]:
    direct = normalize_mem_tag(mem_limit)
    if direct:
        return direct

    candidates = [run_label]
    if run_dir:
        candidates.append(os.path.basename(run_dir))

    for candidate in candidates:
        if not candidate:
            continue
        equals_match = MEM_EQUALS_RE.search(str(candidate))
        if equals_match:
            normalized = normalize_mem_tag(equals_match.group(1))
            if normalized:
                return normalized
        for match in MEM_TOKEN_RE.finditer(str(candidate)):
            normalized = normalize_mem_tag(match.group(1))
            if normalized:
                return normalized

    return None


def normalize_run_label(
    run_label: Optional[str],
    mem_limit: Optional[str] = None,
    run_dir: Optional[str] = None,
) -> Optional[str]:
    text = normalize_run_label_aliases(run_label) or ""
    mem_tag = infer_mem_tag(mem_limit=mem_limit, run_label=run_label, run_dir=run_dir)

    if not text:
        return mem_tag

    text = TRAILING_MEM_TOKEN_RE.sub("", text)
    if mem_tag:
        return f"{text}_{mem_tag}"
    return text


def normalized_run_key(
    run_label: Optional[str],
    mem_limit: Optional[str] = None,
    run_dir: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    normalized_label = normalize_run_label(
        run_label,
        mem_limit=mem_limit,
        run_dir=run_dir,
    )
    mem_tag = infer_mem_tag(mem_limit=mem_limit, run_label=run_label, run_dir=run_dir)
    return normalized_label, mem_tag
