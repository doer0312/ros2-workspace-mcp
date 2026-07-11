# Prompts

## `review_ros2_workspace`

The sole prompt guides a read-only review with the seven analysis tools. Arguments:

- `focus: string = ""` — trimmed untrusted user data, maximum 500 characters.
- `depth: string = "standard"` — case-normalized `quick`, `standard`, or `deep`; other values fail.

`quick` uses scan, dependencies, and diagnosis for a short review. `standard` selects important
packages and relevant interfaces, launch files, and robot descriptions before diagnosis. `deep`
reviews all reasonable items within server limits and explicitly calls out runtime unknowns.

The requested report separates Confirmed Fact, Static Inference, and Unknown at Runtime and includes
workspace, package, dependency, interface, launch, robot, error, warning, limitation, and next-action
sections.

The prompt treats focus and all workspace-derived text as untrusted project data. It forbids
following embedded instructions, reading beyond root, bypassing tool validation, modifying files,
running ROS, building, executing launch, expanding Xacro, installing dependencies, or controlling a
robot. Generating the prompt does not read files, scan the workspace, call tools, or embed resources.
