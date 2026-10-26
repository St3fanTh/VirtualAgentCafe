"""Bounded test evidence, without command arguments, assertion values or raw output."""

import re


def test_diagnostic(label: str, code: object, output: str) -> dict:
    code = code if type(code) is int else None
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", output[-65536:])
    causes = []
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
            1: "Tests failed",
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
        "exit_code": code,
        "passed": code == 0,
        "causes": causes[:5],
        "tests": list(dict.fromkeys(nodes))[:20],
    }
