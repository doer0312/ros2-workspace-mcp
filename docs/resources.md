# Resources

The server exposes one fixed resource and one resource template, both with MIME type
`application/json`. They are generated only when read, are deterministic for an unchanged
workspace, and do not support subscriptions, notifications, or watching.

## `ros2-workspace://summary`

Name: `workspace-summary`. Returns server identity, layout, the canonical root once, package counts,
up to 100 compact package entries, duplicate names, severity counts, and up to 50 ERROR/WARNING
issues. Truncation sets `truncated=true`, lists `truncation_reason`, and retains original counts.

## `ros2-workspace://package/{package_name}`

Name: `package-context`. `package_name` must match `[a-z][a-z0-9_]*` and be at most 64 characters.
It is never interpreted as a path. Missing and ambiguous packages return public resource errors;
ambiguity includes candidate relative paths and recommends `inspect_package(relative_path=...)`.

The payload contains compact manifest/build metadata, static executables, categorized paths,
severity counts, key issues, and a non-executing `detailed_tool_hint`. Each path category and issues
are limited to 50 entries. Descriptions and executable strings are bounded, and final JSON is capped
at 256 KiB with explicit truncation.

No arbitrary-file resource exists. Raw package.xml, setup.py, launch, Xacro, README, source, mesh,
or binary content is never exposed as a resource.
