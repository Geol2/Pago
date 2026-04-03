import os
import glob
import subprocess
from config import PROJECT_ROOT
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


def read_file(path: str) -> str:
    # 캐시 우선 조회
    cached = cache.get_file(path)
    if cached is not None:
        return cached
    # 캐시 미스 시 디스크에서 직접 읽기
    full_path = os.path.join(PROJECT_ROOT, path.replace("/", os.sep))
    if not os.path.exists(full_path):
        return f"[ERROR] File not found: {path}"
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"[ERROR] Could not read file: {e}"


def write_file(path: str, content: str) -> str:
    full_path = os.path.join(PROJECT_ROOT, path.replace("/", os.sep))
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
