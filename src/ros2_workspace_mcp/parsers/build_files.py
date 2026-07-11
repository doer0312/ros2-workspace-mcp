"""Conservative static parsing of Python and CMake build files."""

import ast
import configparser
import re
from pathlib import Path

from ros2_workspace_mcp.models.package import ExecutableSummary
from ros2_workspace_mcp.security.files import read_text_file_with_limit

BUILD_FILE_MAX_BYTES = 1024 * 1024
_CMAKE_EXECUTABLE = re.compile(r"\badd_executable\s*\(\s*([^\s)]+)", re.IGNORECASE)
_CMAKE_INSTALL = re.compile(r"\binstall\s*\(\s*TARGETS\s+([^)]*)\)", re.IGNORECASE | re.DOTALL)


def _literal(node: ast.AST) -> object:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_literal(item) for item in node.elts]
    if isinstance(node, ast.Dict):
        return {
            _literal(key): _literal(value)
            for key, value in zip(node.keys, node.values, strict=True)
        }
    raise ValueError("dynamic expression")


def _entry(name_target: str, source: str) -> ExecutableSummary | None:
    name, separator, target = name_target.partition("=")
    if not separator or not name.strip() or not target.strip():
        return None
    return ExecutableSummary(name=name.strip(), target=target.strip(), source=source)


def parse_setup_py_executables(root: Path, path: Path) -> tuple[list[ExecutableSummary], bool]:
    """Extract literal console_scripts from setup.py without executing it."""
    tree = ast.parse(read_text_file_with_limit(root, path, max_bytes=BUILD_FILE_MAX_BYTES))
    executables: list[ExecutableSummary] = []
    dynamic = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function_name = node.func.id if isinstance(node.func, ast.Name) else None
        if function_name != "setup":
            continue
        for keyword in node.keywords:
            if keyword.arg != "entry_points":
                continue
            try:
                value = _literal(keyword.value)
            except ValueError:
                dynamic = True
                continue
            if not isinstance(value, dict) or not isinstance(value.get("console_scripts"), list):
                dynamic = True
                continue
            for item in value["console_scripts"]:
                if isinstance(item, str) and (entry := _entry(item, "setup.py")):
                    executables.append(entry)
                else:
                    dynamic = True
    return sorted(executables, key=lambda item: item.name), dynamic


def parse_setup_cfg_executables(root: Path, path: Path) -> list[ExecutableSummary]:
    """Extract console_scripts from setup.cfg without importing code."""
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(read_text_file_with_limit(root, path, max_bytes=BUILD_FILE_MAX_BYTES))
    if not parser.has_option("options.entry_points", "console_scripts"):
        return []
    entries = [
        entry
        for line in parser.get("options.entry_points", "console_scripts").splitlines()
        if (entry := _entry(line.strip(), "setup.cfg"))
    ]
    return sorted(entries, key=lambda item: item.name)


def parse_cmake_executables(root: Path, path: Path) -> tuple[list[ExecutableSummary], bool]:
    """Find literal add_executable targets that are installed by CMake."""
    text = read_text_file_with_limit(root, path, max_bytes=BUILD_FILE_MAX_BYTES)
    declared = set(_CMAKE_EXECUTABLE.findall(text))
    installed: set[str] = set()
    dynamic = "${" in text or "$<" in text
    for match in _CMAKE_INSTALL.finditer(text):
        for token in re.split(r"\s+", match.group(1).strip()):
            if token.upper() in {"DESTINATION", "EXPORT", "RUNTIME", "LIBRARY", "ARCHIVE"}:
                break
            installed.add(token)
    targets = sorted(declared & installed)
    return [ExecutableSummary(name=name, source="CMakeLists.txt") for name in targets], dynamic
