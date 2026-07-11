"""Non-executing Python AST, XML, and safe-YAML launch parsers."""

import ast
import xml.etree.ElementTree as ET
from typing import Any

import yaml

from ros2_workspace_mcp.models.common import ScanIssue, Severity
from ros2_workspace_mcp.models.launch import (
    LaunchAnalysisResult,
    LaunchArgument,
    LaunchEnvironmentChange,
    LaunchInclude,
    LaunchNode,
    LaunchProcess,
)


def _issue(code: str, message: str, path: str, line: int | None = None) -> ScanIssue:
    return ScanIssue(
        severity=Severity.ERROR,
        code=code,
        message=message,
        path=path,
        line=line,
    )


def _call_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return ""


def _expression(node: ast.AST | None) -> tuple[Any, bool, str | None]:
    if node is None:
        return None, False, None
    try:
        return ast.literal_eval(node), False, None
    except (ValueError, TypeError):
        if (
            isinstance(node, ast.Call)
            and node.args
            and _call_name(node).endswith("LaunchDescriptionSource")
        ):
            try:
                return ast.literal_eval(node.args[0]), False, None
            except (ValueError, TypeError):
                pass
        rendered = ast.unparse(node)
        return rendered, True, rendered


def _keyword(call: ast.Call, name: str) -> ast.AST | None:
    return next((keyword.value for keyword in call.keywords if keyword.arg == name), None)


def parse_python_launch(text: str, relative_path: str) -> LaunchAnalysisResult:
    """Inspect common launch actions using Python AST only."""
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return LaunchAnalysisResult(
            relative_path=relative_path,
            format="python",
            valid=False,
            issues=[
                _issue(
                    "INVALID_PYTHON_LAUNCH", "Python syntax is invalid.", relative_path, exc.lineno
                )
            ],
        )
    result = LaunchAnalysisResult(relative_path=relative_path, format="python", valid=True)
    recognized = {
        "LaunchDescription",
        "Node",
        "ComposableNode",
        "IncludeLaunchDescription",
        "DeclareLaunchArgument",
        "SetEnvironmentVariable",
        "GroupAction",
        "PushRosNamespace",
        "ExecuteProcess",
        "RegisterEventHandler",
    }
    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
        name = _call_name(call)
        if name in recognized:
            result.entities.append(name)
        if name in {"Node", "ComposableNode"}:
            values: dict[str, Any] = {}
            dynamic = False
            for keyword in (
                "package",
                "executable",
                "name",
                "namespace",
                "parameters",
                "remappings",
                "arguments",
                "condition",
            ):
                value, is_dynamic, expression = _expression(_keyword(call, keyword))
                if keyword in {"parameters", "remappings", "arguments"}:
                    if value is None:
                        value = []
                    elif not isinstance(value, list):
                        value = [value]
                values[keyword] = value
                dynamic |= is_dynamic
                if expression:
                    result.dynamic_expressions.append(expression)
            result.nodes.append(LaunchNode(**values, dynamic=dynamic))
        elif name == "DeclareLaunchArgument":
            name_value, name_dynamic, expression = _expression(
                call.args[0] if call.args else _keyword(call, "name")
            )
            default, default_dynamic, default_expression = _expression(
                _keyword(call, "default_value")
            )
            description, description_dynamic, description_expression = _expression(
                _keyword(call, "description")
            )
            result.arguments.append(
                LaunchArgument(
                    name=name_value if isinstance(name_value, str) else None,
                    default=default,
                    description=description if isinstance(description, str) else None,
                    dynamic=name_dynamic or default_dynamic or description_dynamic,
                )
            )
            result.dynamic_expressions.extend(
                item for item in (expression, default_expression, description_expression) if item
            )
        elif name == "IncludeLaunchDescription":
            value, dynamic, expression = _expression(
                call.args[0] if call.args else _keyword(call, "launch_description_source")
            )
            result.includes.append(
                LaunchInclude(path=value if isinstance(value, str) else str(value), dynamic=dynamic)
            )
            if expression:
                result.dynamic_expressions.append(expression)
        elif name == "SetEnvironmentVariable":
            env_name, name_dynamic, name_expression = _expression(
                _keyword(call, "name") or (call.args[0] if call.args else None)
            )
            value, value_dynamic, value_expression = _expression(
                _keyword(call, "value") or (call.args[1] if len(call.args) > 1 else None)
            )
            result.environment_changes.append(
                LaunchEnvironmentChange(
                    name=env_name if isinstance(env_name, str) else None,
                    value=value,
                    dynamic=name_dynamic or value_dynamic,
                )
            )
            result.dynamic_expressions.extend(
                item for item in (name_expression, value_expression) if item
            )
        elif name == "ExecuteProcess":
            command, dynamic, expression = _expression(_keyword(call, "cmd"))
            condition, condition_dynamic, condition_expression = _expression(
                _keyword(call, "condition")
            )
            result.processes.append(
                LaunchProcess(
                    command=command,
                    condition=str(condition) if condition is not None else None,
                    dynamic=dynamic or condition_dynamic,
                )
            )
            result.dynamic_expressions.extend(
                item for item in (expression, condition_expression) if item
            )
    result.entities = sorted(result.entities)
    result.dynamic_expressions = sorted(set(result.dynamic_expressions))
    return result


def _xml_node(element: ET.Element) -> LaunchNode:
    remappings = [
        {"from": item.get("from"), "to": item.get("to")} for item in element.findall("remap")
    ]
    parameters = [dict(item.attrib) for item in element.findall("param")]
    return LaunchNode(
        package=element.get("pkg"),
        executable=element.get("exec") or element.get("executable"),
        name=element.get("name"),
        namespace=element.get("namespace") or element.get("ns"),
        parameters=parameters,
        remappings=remappings,
        arguments=element.get("args", "").split() if element.get("args") else [],
        condition=element.get("if") or element.get("unless"),
        dynamic=any("$(" in value or "${" in value for value in element.attrib.values()),
    )


def parse_xml_launch(text: str, relative_path: str) -> LaunchAnalysisResult:
    """Parse XML launch declarations without entity or include expansion."""
    try:
        document = ET.fromstring(text)
    except ET.ParseError:
        return LaunchAnalysisResult(
            relative_path=relative_path,
            format="xml",
            valid=False,
            issues=[_issue("INVALID_XML_LAUNCH", "Launch XML is invalid.", relative_path)],
        )
    if document.tag != "launch":
        return LaunchAnalysisResult(
            relative_path=relative_path,
            format="xml",
            valid=False,
            issues=[_issue("INVALID_XML_LAUNCH", "XML root must be <launch>.", relative_path)],
        )
    result = LaunchAnalysisResult(relative_path=relative_path, format="xml", valid=True)
    result.nodes = [_xml_node(item) for item in document.iter("node")]
    result.includes = [
        LaunchInclude(
            path=item.get("file"),
            dynamic=bool(
                item.get("file") and ("$(" in item.get("file", "") or "${" in item.get("file", ""))
            ),
            condition=item.get("if") or item.get("unless"),
        )
        for item in document.iter("include")
    ]
    result.arguments = [
        LaunchArgument(
            name=item.get("name"),
            default=item.get("default") or item.get("value"),
            dynamic=any("$(" in value or "${" in value for value in item.attrib.values()),
        )
        for item in document.iter("arg")
    ]
    result.environment_changes = [
        LaunchEnvironmentChange(
            name=item.get("name"),
            value=item.get("value"),
            dynamic=any("$(" in value or "${" in value for value in item.attrib.values()),
        )
        for item in document.iter("set_env")
    ]
    result.processes = [
        LaunchProcess(command=item.get("cmd") or item.get("executable"), dynamic=False)
        for tag in ("executable", "exec")
        for item in document.iter(tag)
    ]
    result.entities = sorted({item.tag for item in document.iter()})
    return result


def parse_yaml_launch(text: str, relative_path: str) -> LaunchAnalysisResult:
    """Parse YAML with SafeLoader and conservatively recognize common entities."""
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError:
        return LaunchAnalysisResult(
            relative_path=relative_path,
            format="yaml",
            valid=False,
            issues=[_issue("INVALID_YAML_LAUNCH", "Launch YAML is invalid.", relative_path)],
        )
    if not isinstance(document, (dict, list)):
        return LaunchAnalysisResult(
            relative_path=relative_path,
            format="yaml",
            valid=False,
            issues=[
                _issue(
                    "INVALID_YAML_LAUNCH", "Launch YAML must be a mapping or list.", relative_path
                )
            ],
        )
    result = LaunchAnalysisResult(relative_path=relative_path, format="yaml", valid=True)

    def walk(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            for key, item in value.items():
                if key == "node" and isinstance(item, dict):
                    parameters = item.get("param", item.get("parameters", []))
                    remappings = item.get("remap", item.get("remappings", []))
                    arguments = item.get("args", item.get("arguments", []))
                    result.nodes.append(
                        LaunchNode(
                            package=item.get("pkg") or item.get("package"),
                            executable=item.get("exec") or item.get("executable"),
                            name=item.get("name"),
                            namespace=item.get("namespace"),
                            parameters=parameters if isinstance(parameters, list) else [parameters],
                            remappings=remappings if isinstance(remappings, list) else [remappings],
                            arguments=arguments if isinstance(arguments, list) else [arguments],
                            condition=item.get("if") or item.get("unless"),
                        )
                    )
                elif key in {"arg", "argument"} and isinstance(item, dict):
                    result.arguments.append(
                        LaunchArgument(name=item.get("name"), default=item.get("default"))
                    )
                elif key == "include" and isinstance(item, dict):
                    result.includes.append(LaunchInclude(path=item.get("file")))
                elif key in {"set_env", "set_environment_variable"} and isinstance(item, dict):
                    result.environment_changes.append(
                        LaunchEnvironmentChange(name=item.get("name"), value=item.get("value"))
                    )
                elif key in {"executable", "execute_process"}:
                    command = item.get("cmd") if isinstance(item, dict) else item
                    result.processes.append(LaunchProcess(command=command))
                result.entities.append(str(key))
                walk(item)

    walk(document)
    result.entities = sorted(set(result.entities))
    return result
