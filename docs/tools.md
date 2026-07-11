# Tools

Every tool is read-only, constrained to the root selected at server startup, and returns a JSON
object. No tool accepts a replacement workspace root.

## `scan_workspace`

Input: `{}`. Discovers package candidates and basic manifest/build metadata. Returns workspace
layout, sorted packages, counts, duplicate names, and issues. It is the lightweight discovery tool.

## `inspect_package`

Input: `package_name?: string`, `relative_path?: string`; exactly one is required. Returns detailed
manifest people/URLs/groups, build-system evidence, literal Python console scripts, installed CMake
targets, and classified launch/config/interface/robot/test/resource files. `setup.py` is AST-only;
dynamic expressions are reported, never evaluated.

## `analyze_dependencies`

Input: `package_name?: string`, `relative_path?: string`. With neither selector, analyzes the whole
workspace; with one, analyzes that package and reachable workspace dependencies. Returns original
dependency tags and conditions, internal/external names, edges, deterministic topological order,
cycles, and issues. It does not run rosdep or treat every external dependency as missing.

## `inspect_interfaces`

Input: exactly one of `package_name?: string` or `relative_path?: string`, plus optional
`interface_name?: string`. Parses Msg/Srv/Action sections, fields, constants, defaults, arrays,
bounds, and comments. Types are classified as builtin, workspace, external, or unresolved local.
`interface_name` is a simple name, not a path.

## `analyze_launch_file`

Input: required `relative_path: string` ending in `.launch.py`, `.launch.xml`, `.launch.yaml`, or
`.launch.yml`. Returns nodes, includes, arguments, environment changes, processes, recognized
entities, and dynamic expressions. Python uses AST, XML uses safe static parsing, and YAML uses
`safe_load`. Includes are listed but not recursively analyzed; processes are never executed.

## `inspect_robot_description`

Input: required `relative_path: string` ending in `.urdf` or `.xacro`. URDF returns links, joints,
roots/leaves, limits, kinematic errors, transmissions, Gazebo presence, and mesh references. Xacro
returns `expanded=false` with properties, macros, arguments, calls, includes, direct include cycles,
and dynamic expressions. Xacro is never expanded.

## `diagnose_workspace`

Input: `{}`. Reuses all internal analyzers and returns compact section counts, dependency counts,
severity totals, deduplicated issues, analyzed/skipped files, and `status` (`error`, `warning`, or
`ok`). Limits are 100 packages, 200 files per kind, and 500 issues; any limit produces an explicit
warning.

Package selectors never choose arbitrarily: duplicate names return `AMBIGUOUS_PACKAGE_NAME` with
candidate relative paths, after which callers can select one with `relative_path`.

Tools perform explicit analysis requested by the model. Resources instead provide bounded context
for clients to read, while the prompt supplies a review workflow but performs no analysis. See
`resources.md` and `prompts.md`.
