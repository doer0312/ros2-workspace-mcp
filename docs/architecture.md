# Architecture

The CLI validates a workspace path and creates immutable `ServerSettings`. `create_server()` builds
an unstarted `FastMCP` instance and delegates registration to the modules under `tools/`;
`run_server()` is the only stdio start boundary.

All seven tools follow the same layers:

1. `security/paths.py` canonicalizes the root and enforces path containment.
2. `security/files.py` performs bounded UTF-8/UTF-8-BOM reads.
3. `parsers/` performs deterministic XML, AST, CMake-text, interface, and safe-YAML parsing.
4. `analyzers/` combines parser results into package, graph, type, kinematic, or diagnosis results.
5. `tools/` converts Pydantic results with `model_dump(mode="json")` at the MCP boundary.

The analyzer is transport-independent and accepts `ServerSettings`, not CLI arguments. Each server
factory call creates a fresh FastMCP instance and registers each tool once. `diagnose_workspace`
calls pure analyzer functions directly; it never calls its own MCP server.

Package-scoped tools share `resolve_package_selector()`, so name ambiguity and relative-path safety
have one implementation. `ScanIssue` is shared across every analyzer. Diagnosis limits are
centralized in `analyzers/diagnosis.py`: 100 packages, 200 files per analysis kind, and 500 issues.

Resources follow the same separation: `resources/workspace.py` and `resources/package.py` contain
pure payload builders plus thin `FastMCP.resource()` registration functions. Registration captures
immutable settings but performs no scan. The fixed summary calls `analyze_workspace()` only on
read; the package template reuses `resolve_package_selector()` and `inspect_package()`.

`prompts/review.py` is data-free. `FastMCP.prompt()` registers a pure string builder that validates
`focus` and `depth`; prompt retrieval does not scan or read the workspace. Each `create_server()`
call creates independent registrations: seven tools, one fixed resource, one template, one prompt.
