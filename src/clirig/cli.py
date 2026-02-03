import os
import re
import argparse
from collections import defaultdict

# ─────────────────────────────────────────────────────────────
# Templates
# ─────────────────────────────────────────────────────────────

FILE_TEMPLATES = {
    "main.py": """\
def main():
    print("Hello from main")

if __name__ == "__main__":
    main()
""",
    "__init__.py": """\
\"\"\"Package initialization.\"\"\"
""",
    "README.md": """\
# {project_name}

## Description
Project generated automatically.

## Structure
{structure}
""",
    ".gitignore": """\
__pycache__/
*.pyc
.env
.venv
venv/
dist/
build/
*.egg-info
""",
}

ALLOWED_CHARS = set(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    "._-/"
)

# ─────────────────────────────────────────────────────────────
# Normalization
# ─────────────────────────────────────────────────────────────

TREE_PREFIX_RE = re.compile(r"^[│\s]*[├└]──\s*")


def normalize_line(line: str):
    """
    Normalize a single template line.

    Returns:
        (normalized_line, None) on success
        (None, reason) if the line is dropped
    """
    raw = line.rstrip("\n")

    if not raw.strip():
        return None, "empty line"

    if raw.startswith("\t"):
        indent = len(raw) - len(raw.lstrip("\t"))
        content = raw.strip()
    else:
        level = 0
        for i in range(0, len(raw), 4):
            chunk = raw[i : i + 4]
            if chunk in ("│   ", "    "):
                level += 1
            else:
                break
        indent = level
        content = TREE_PREFIX_RE.sub("", raw).strip()

    if not content:
        return None, "no filename detected"

    name = content.split()[0]

    if name.startswith(("/", "-", "—", "!", "?", "#", "*", "(")) or name.startswith("//"):
        return None, "invalid name prefix"

    if not all(c in ALLOWED_CHARS for c in name):
        return None, "invalid characters in name"

    return "\t" * indent + name, None


# ─────────────────────────────────────────────────────────────
# Parsing
# ─────────────────────────────────────────────────────────────

def parse_template(path, explain=False):
    """
    Parse template file into a list of (lineno, level, name)
    """
    structure = []

    with open(path, "r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            normalized, reason = normalize_line(raw)

            if not normalized:
                if explain:
                    print(
                        f"[drop] line {lineno}: {reason}\n"
                        f"       raw: {raw.rstrip()}"
                    )
                continue

            level = len(normalized) - len(normalized.lstrip("\t"))
            name = normalized.lstrip("\t")
            structure.append((lineno, level, name))

    return structure


# ─────────────────────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────────────────────

def validate_structure(structure):
    errors = []
    stack = []
    seen = defaultdict(set)

    # Hard invariant: no children before first root
    seen_root = False
    for lineno, level, name in structure:
        if level == 0:
            seen_root = True
        elif not seen_root:
            errors.append(
                f"Line {lineno}: entry '{name}' has level {level} "
                f"but no root directory defined above"
            )
            return errors

    roots = [name for _, level, name in structure if level == 0]
    if not roots:
        errors.append("Template must contain at least one root directory (level 0).")
        return errors

    for lineno, level, name in structure:
        if level > len(stack) + 1:
            errors.append(f"Line {lineno}: invalid indentation jump → {name}")
            continue

        if level == len(stack) + 1 and stack:
            parent = stack[-1]
            if not parent.endswith("/"):
                errors.append(f"Line {lineno}: file cannot have children → {parent}")
                continue

        if name in seen[level]:
            # non-fatal: duplicate → drop
            continue

        seen[level].add(name)
        stack = stack[:level]
        stack.append(name)

    return errors


# ─────────────────────────────────────────────────────────────
# Tree rendering
# ─────────────────────────────────────────────────────────────

def render_tree(structure):
    if not structure:
        return ""

    lines = []
    last_at_level = []

    for i, (_, level, name) in enumerate(structure):
        if len(last_at_level) > level:
            last_at_level = last_at_level[:level]

        is_last = i == len(structure) - 1 or structure[i + 1][1] <= level

        if len(last_at_level) == level:
            last_at_level.append(is_last)
        else:
            last_at_level = last_at_level[:level] + [is_last]

        prefix = "".join(
            "│   " if not last_at_level[lvl] else "    "
            for lvl in range(len(last_at_level) - 1)
        )

        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{name}")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# Generation
# ─────────────────────────────────────────────────────────────

def generate(structure, base_path, force=False):
    stack = []

    roots = [name for _, level, name in structure if level == 0]
    if len(roots) > 1:
        base_path = os.path.join(base_path, "crig_root")
        os.makedirs(base_path, exist_ok=True)

    root_name = roots[0].rstrip("/")

    ensured_dirs = 0
    ensured_files = 0

    for _, level, name in structure:
        stack = stack[:level]
        path = os.path.join(base_path, *stack, name.rstrip("/"))

        if name.endswith("/"):
            os.makedirs(path, exist_ok=True)
            ensured_dirs += 1
            stack.append(name.rstrip("/"))
        else:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if force or not os.path.exists(path):
                with open(path, "w", encoding="utf-8") as f:
                    template = FILE_TEMPLATES.get(os.path.basename(path))
                    if template:
                        f.write(
                            template.format(
                                project_name=root_name,
                                structure=render_tree(structure),
                            )
                        )
                ensured_files += 1

    print(f"Ensured directories: {ensured_dirs}")
    print(f"Ensured files: {ensured_files}")


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────

def entry_point():
    parser = argparse.ArgumentParser(
        description="crig — project structure generator from a tree template",
        epilog="Grammar (EBNF) is documented in README.",
        add_help=False,
    )

    parser.add_argument("-h", "--help", action="help", help="show help and exit")
    parser.add_argument("-v", "--version", action="version", version="crig 0.1.0")
    parser.add_argument("-i", "--init", action="store_true", help="create base template")
    parser.add_argument("-f", "--force", action="store_true", help="overwrite files")
    parser.add_argument("-t", "--template", default="template.txt", help="template file")
    parser.add_argument("--dry-run", action="store_true", help="preview only")
    parser.add_argument(
        "-x", "--explain", action="store_true",
        help="explain why template lines are ignored"
    )

    args = parser.parse_args()

    if args.init:
        default = """myproject/
├── src/
│   ├── __init__.py
│   └── main.py
├── tests/
├── README.md
├── requirements.txt
└── .gitignore
"""
        with open(args.template, "w", encoding="utf-8") as f:
            f.write(default.strip() + "\n")
        print("Base template created.")
        return

    if not os.path.exists(args.template):
        print("Template file not found.")
        return

    structure = parse_template(args.template, explain=args.explain)
    errors = validate_structure(structure)

    if errors:
        print("Template errors:")
        for e in errors:
            print("  " + e)
        return

    if args.dry_run:
        print(render_tree(structure))
        return

    generate(structure, os.getcwd(), force=args.force)
    print("Project structure created successfully.")


if __name__ == "__main__":
    entry_point()
