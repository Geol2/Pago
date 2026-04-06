"""
프로젝트 파일을 시작 시 메모리에 로드하여 빠른 조회를 지원한다.
"""
import os
import re
import fnmatch
import time
import config

# 캐시할 확장자
INCLUDE_EXTS = {".java", ".xml", ".jsp", ".js", ".properties", ".md", ".gradle"}
# 제외 경로 (빌드 산출물 등)
EXCLUDE_DIRS = {"bin", "build", ".git", ".gradle", "node_modules"}

# 메모리 캐시: { 상대경로 → 내용 }
_file_cache: dict[str, str] = {}
# 패키지별 클래스 인덱스: { 패키지 → [클래스명, ...] }
_class_index: dict[str, list] = {}
# 파일 목록 (상대경로 리스트)
_file_list: list[str] = []


# ──────────────────────────────────────────────
# 내부 유틸
# ──────────────────────────────────────────────

def _should_include(rel_path: str) -> bool:
    parts = rel_path.replace("\\", "/").split("/")
    if any(p in EXCLUDE_DIRS for p in parts):
        return False
    _, ext = os.path.splitext(rel_path)
    return ext in INCLUDE_EXTS


def _extract_java_info(content: str) -> tuple:
    """(package, class_name, method_names) 추출"""
    pkg_match   = re.search(r"^\s*package\s+([\w.]+)\s*;", content, re.MULTILINE)
    cls_match   = re.search(r"\b(?:class|interface|enum)\s+(\w+)", content)
    method_matches = re.findall(
        r"(?:public|protected|private)\s+[\w<>\[\]]+\s+(\w+)\s*\(", content
    )
    pkg  = pkg_match.group(1)  if pkg_match  else ""
    cls  = cls_match.group(1)  if cls_match  else ""
    return pkg, cls, method_matches


# ──────────────────────────────────────────────
# 공개 API
# ──────────────────────────────────────────────

def load(verbose: bool = True) -> None:
    """프로젝트 전체를 스캔해 메모리에 로드한다."""
    global _file_cache, _class_index, _file_list

    _file_cache.clear()
    _class_index.clear()
    _file_list.clear()

    start = time.time()
    skipped = 0

    for dirpath, dirnames, filenames in os.walk(config.PROJECT_ROOT):
        # 제외 디렉터리는 탐색하지 않음
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]

        for fname in filenames:
            abs_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(abs_path, config.PROJECT_ROOT).replace("\\", "/")

            if not _should_include(rel_path):
                skipped += 1
                continue

            try:
                with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except Exception:
                skipped += 1
                continue

            _file_cache[rel_path] = content
            _file_list.append(rel_path)

            if rel_path.endswith(".java"):
                pkg, cls, _ = _extract_java_info(content)
                if pkg and cls:
                    _class_index.setdefault(pkg, []).append(cls)

    elapsed = time.time() - start
    if verbose:
        print(f"  캐시 완료: {len(_file_cache)}개 파일 ({elapsed:.1f}s)")


def get_file(rel_path: str) -> str | None:
    """캐시에서 파일 내용을 반환한다. 없으면 None."""
    # 슬래시 정규화
    key = rel_path.replace("\\", "/")
    return _file_cache.get(key)


def search_files(pattern: str) -> list[str]:
    """glob 패턴으로 파일 목록을 반환한다."""
    pattern = pattern.replace("\\", "/")
    return [p for p in _file_list if fnmatch.fnmatch(p, pattern)]


def search_content(keyword: str, path_prefix: str = "") -> list[str]:
    """키워드를 포함하는 줄을 '파일:줄번호: 내용' 형식으로 반환한다."""
    results = []
    prefix  = path_prefix.replace("\\", "/")
    for rel_path, content in _file_cache.items():
        if prefix and not rel_path.startswith(prefix):
            continue
        for lineno, line in enumerate(content.splitlines(), 1):
            if keyword in line:
                results.append(f"{rel_path}:{lineno}: {line.rstrip()}")
    return results


def build_index_summary() -> str:
    """시스템 프롬프트에 주입할 프로젝트 인덱스 요약을 반환한다.
    파일 경로 목록은 포함하지 않음 — 컨텍스트 크기 최소화."""
    lines = [
        "## Pre-loaded Project Index",
        f"Total cached files: {len(_file_cache)} "
        "(Java, XML, JSP, JS, properties, md, gradle)",
        "",
        "### Java Classes by Package",
    ]
    for pkg in sorted(_class_index):
        classes = ", ".join(sorted(_class_index[pkg]))
        lines.append(f"- `{pkg}`: {classes}")

    lines += [
        "",
        "### MyBatis Mappers",
        ", ".join(
            p.split("/")[-1] for p in sorted(_file_list) if p.endswith(".xml")
        ),
        "",
        "> Files are pre-loaded. Use list_files/search_code/read_file to explore.",
    ]
    return "\n".join(lines)
