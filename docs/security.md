# Security boundary

The project is local-first and read-only. Its inspection scope is the canonical directory configured
with `--root`.

## Root sandbox

The root must exist and be a directory. Relative components, `..`, and the root's own symlinks are
resolved at configuration time. Every selected file is resolved again and checked with
`Path.is_relative_to()` against that canonical root; similar string prefixes do not pass. Absolute
paths are accepted internally only when they remain inside the root. Security errors do not expose
the escaped target path or its contents.

Directory symlinks are never traversed, including links that point back into the workspace. This
prevents cycles and keeps traversal predictable. A file symlink may be read only when its resolved
target remains inside the root. Escaping or broken symlinks are skipped and reported when they are
relevant to the scan. On systems where creating symlinks requires extra privileges, the same
canonical containment checks still apply to existing links.

## Files examined

Text reads use one sandboxed helper, default to UTF-8/UTF-8-BOM, and reject oversized or undecodable
files before parsing. Manifests, build files, interfaces, selected launch files, and selected
URDF/Xacro are read only for their corresponding tools. Mesh files are never read; only their paths
and safe resolution status are recorded. `package://` URIs are preserved without network or package
index access.

Directories named `.git`, `.github`, `.idea`, `.vscode`, `build`, `install`, `log`, `__pycache__`,
`.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `.venv`, `venv`, `env`, `node_modules`, or `dist` are
ignored everywhere. This global policy is deliberately conservative, so a genuine package nested
under a directory with one of those names is not discovered. Directories containing
`COLCON_IGNORE`, `AMENT_IGNORE`, or `CATKIN_IGNORE` are skipped with their complete subtree.

## Read-only and non-execution guarantee

The server does not execute shell commands, `ros2`, `colcon`, launch files, or workspace Python;
does not dynamically import workspace modules; does not invoke topics, services, or actions; and
does not modify files. It exposes only stdio, not an HTTP transport. Malformed manifests and most
per-path access errors become structured issues so other packages can still be reported.

- `setup.py` and Python launch files are parsed with `ast`; they are never imported or evaluated.
- CMake is recognized with conservative text patterns; CMake is never configured or executed.
- XML uses `ElementTree`; external entities and network lookup are not performed.
- YAML launch files use `yaml.safe_load`, never `yaml.load` or custom object construction.
- `ExecuteProcess` is returned as static metadata and is never invoked.
- Xacro properties, macros, calls, includes, and dynamic expressions are summarized without Xacro
  expansion or command execution.
- External dependencies are reported but never queried, installed, or assumed missing.

Workspace diagnosis is bounded to 100 packages, 200 files per category, and 500 unique issues.
Every truncation produces `ANALYSIS_LIMIT_REACHED`; nothing is silently truncated.

## Resource and prompt boundary

The two resources return derived JSON metadata only. They never return manifest XML, setup or
launch source, Xacro, README text, arbitrary source files, binary data, or meshes. This avoids
turning the server into a general filesystem service and reduces prompt-injection exposure. The
package template parameter is a lowercase ROS package name, not a path; slash, backslash, dot,
percent encoding, uppercase characters, and names longer than 64 characters are rejected.

The review prompt labels `focus`, filenames, manifest descriptions, and workspace content as
untrusted data. It tells the model not to follow embedded instructions, escape the root, or bypass
tool arguments. Prompt generation itself does not call tools, analyzers, or file APIs.

Resources are generated synchronously on read. There are no subscriptions, update notifications,
watchers, cache threads, sampling, elicitation, or embedded raw resources.
