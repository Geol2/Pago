import os
import glob
import subprocess
import config
import cache

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a source file from the project. Use relative path from project root.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative file path from project root. e.g. src/kr/co/exsoft/api/DworksResourceHandler.java"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write (overwrite) a file in the project. Use with caution — always read first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative file path from project root."
                    },
                    "content": {
                        "type": "string",
                        "description": "Full file content to write."
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files matching a glob pattern in the project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern relative to project root. e.g. src/**/*.java"
                    }
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": "Search for a keyword or pattern across project source files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Search keyword or regex pattern."
                    },
                    "path": {
                        "type": "string",
                        "description": "Optional: relative path to limit search scope. e.g. src/kr/co/exsoft/api/"
                    }
                },
                "required": ["pattern"]
            }
        }
    }
]


def _resolve_path(path: str) -> str:
    """Java 패키지 점 표기법(co.exsoft.foo/Bar.java)을 슬래시 경로로 변환한다."""
    path = path.replace("\\", "/").strip()
    parts = path.split("/")
    # 디렉토리 부분(마지막 제외)의 점을 슬래시로 변환
    normalized = "/".join(
        p.replace(".", "/") if i < len(parts) - 1 else p
        for i, p in enumerate(parts)
    )
    return normalized


def _find_by_filename(filename: str) -> list[str]:
    """파일명만으로 캐시 전체에서 경로를 검색한다."""
    return [p for p in cache._file_cache if p.endswith("/" + filename) or p == filename]


def read_file(path: str) -> str:
    # 1. 캐시 우선 조회 (원본 경로)
    cached = cache.get_file(path)
    if cached is not None:
        return cached

    # 2. 점 표기법 → 슬래시 변환 후 재시도
    normalized = _resolve_path(path)
    if normalized != path:
        cached = cache.get_file(normalized)
        if cached is not None:
            return f"[resolved: {normalized}]\n" + cached

    # 3. 디스크 직접 읽기 (변환된 경로)
    for try_path in dict.fromkeys([path, normalized]):  # 중복 제거, 순서 유지
        full_path = os.path.join(config.PROJECT_ROOT, try_path.replace("/", os.sep))
        if os.path.exists(full_path):
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                return f"[ERROR] Could not read file: {e}"

    # 4. 파일명만으로 캐시 검색 (경로를 모를 때 최후 수단)
    filename = path.split("/")[-1]
    matches = _find_by_filename(filename)
    if len(matches) == 1:
        return f"[auto-found: {matches[0]}]\n" + cache.get_file(matches[0])
    if len(matches) > 1:
        found_list = "\n".join(f"  - {m}" for m in matches[:10])
        return f"[ERROR] '{filename}' 이름의 파일이 여러 개 있습니다. 정확한 경로를 지정하세요:\n{found_list}"

    return f"[ERROR] File not found: {path}"


def write_file(path: str, content: str) -> str:
    full_path = os.path.join(config.PROJECT_ROOT, path.replace("/", os.sep))
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    try:
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        # 캐시도 갱신
        cache._file_cache[path.replace("\\", "/")] = content
        return f"[OK] Written: {path}"
    except Exception as e:
        return f"[ERROR] Could not write file: {e}"


def list_files(pattern: str) -> str:
    matches = cache.search_files(pattern)
    if not matches:
        return "[EMPTY] No files found."
    return "\n".join(sorted(matches))


def search_code(pattern: str, path: str = None) -> str:
    results = cache.search_content(pattern, path_prefix=path or "")
    if not results:
        return "[EMPTY] No matches found."
    if len(results) > 60:
        results = results[:60] + [f"... ({len(results) - 60} more lines)"]
    return "\n".join(results)


TOOL_MAP = {
    "read_file":   read_file,
    "write_file":  write_file,
    "list_files":  list_files,
    "search_code": search_code,
}


def call_tool(name: str, args: dict) -> str:
    fn = TOOL_MAP.get(name)
    if fn is None:
        return f"[ERROR] Unknown tool: {name}"
    return fn(**args)
