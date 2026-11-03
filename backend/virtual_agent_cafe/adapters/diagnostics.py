"""Bounded test evidence, without command arguments, assertion values or raw output."""

import re


def godot_user_data_failure(output: str) -> bool:
    return "Error attempting to create data dir:" in output


def godot_failure_category(output: str) -> str:
    """Engine ERROR alone does not prove an implementation defect."""
    if godot_user_data_failure(output):
        return "ENVIRONMENT_ERROR"
    if re.search(
        r"(?im)^ERROR:.*(?:does not exist|not found|could not load|failed loading).*", output
    ):
        return "CONFIGURATION_ERROR"
    if re.search(r"(?m)^SCRIPT ERROR:|AssertionError", output):
        return "TEST_FAILURE"
    return "UNCLASSIFIED_ERROR"


def failure_category(label: str, code: object, output: str) -> str:
    """Evidence-based categories; exit status alone is never proof of a code defect."""
    if godot_user_data_failure(output):
        return "ENVIRONMENT_ERROR"
    if code == 0:
        return "PASSED"
    if any(
        term in output
        for term in (
            "ModuleNotFoundError",
            "ImportError",
            "PermissionError",
            "FileNotFoundError",
            "ConnectionRefusedError",
            "bwrap:",
            "No module named",
            "command not found",
        )
    ):
        return "ENVIRONMENT_ERROR"
    if "pytest" in label:
        if code == 2:
            return (
                "COLLECTION_ERROR"
                if re.search(r"collect|ImportError|SyntaxError", output, re.I)
                else "INTERRUPTED"
            )
        if code == 3:
            return "TOOL_ERROR"
        if code in (4, 5):
            return "CONFIGURATION_ERROR"
    if re.search(r"AssertionError|(?m:^FAILED )|SCRIPT ERROR:|(?m:^ERROR:)", output):
        return "TEST_FAILURE"
    return "PASSED" if code == 0 else "UNCLASSIFIED_ERROR"


def test_diagnostic(label: str, code: object, output: str) -> dict:
    code = code if type(code) is int else None
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", output)
    causes = []
    if godot_user_data_failure(text):
        causes.append(
            "Godot cannot create its user data directory; check writable sandbox XDG directories"
        )
    for kind, hint in (
        ("ModuleNotFoundError", "Missing Python dependency or incorrect import path"),
        ("ImportError", "Python import failed"),
        ("SyntaxError", "Invalid Python syntax"),
        ("AssertionError", "An assertion did not match the expected result"),
        ("PermissionError", "Test cannot access a required file or resource"),
        ("FileNotFoundError", "A required file or executable is missing"),
        ("ConnectionRefusedError", "A required service is not reachable"),
    ):
        if re.search(r"\b" + kind + r"\b", text):
            causes.append(f"{kind}: {hint}")
    if "pytest" in label and code != 0:
        meanings = {
            1: "Pytest command returned exit 1",
            2: "Test run interrupted (often a collection/import error)",
            3: "Pytest internal error",
            4: "Invalid pytest invocation or configuration",
            5: "No tests collected",
        }
        causes.insert(0, meanings.get(code, "Test process did not complete successfully"))
    if not causes and code != 0:
        causes.append("No recognized failure detail; inspect test output in the workspace")
    # Pytest node IDs only: exclude parameter values and assertion/error messages.
    nodes = re.findall(
        r"^(?:FAILED|ERROR) ((?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.py"
        r"(?:::[A-Za-z_][A-Za-z0-9_]*)*)",
        text,
        re.MULTILINE,
    )
    return {
        "tool": label,
        "category": failure_category(label, code, text),
        "exit_code": code,
        "passed": code == 0,
        "causes": causes[:5],
        "tests": list(dict.fromkeys(nodes))[:20],
    }
