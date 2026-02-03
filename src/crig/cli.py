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


# ─────────────────────────────────────────────────────────────
# Normalization (tree / spaces → tabs)
# ─────────────────────────────────────────────────────────────

TREE_PREFIX_RE = re.compile(r"^[│\s]*[├└]──\s*")


def normalize_line(line: str) -> str:
    """
    Нормализует строку: определяет уровень отступа,
    извлекает только валидное имя файла/папки,
    всё остальное (после первого пробела) считает комментарием.
    """
    original_line = line
    line = line.rstrip("\n")

    if line.startswith("\t"):
        indent = len(line) - len(line.lstrip("\t"))
        content = line.strip()
    else:
        level = 0
        for i in range(0, len(line), 4):
            chunk = line[i : i + 4]
            if chunk in ("│   ", "    "):
                level += 1
            else:
                break
        indent = level
        content = TREE_PREFIX_RE.sub("", line).strip()

    if not content:
        return ""

    name = content.split()[0] if content.split() else ""

    invalid_starts = "([-/—!?#*"
    if name.startswith(tuple(invalid_starts)) or name.startswith("//"):
        return ""

    if not all(c.isalnum() or c in "_-./" for c in name):
        return ""

    return "\t" * indent + name


# ─────────────────────────────────────────────────────────────
# Parsing
# ─────────────────────────────────────────────────────────────


def parse_template(path):
    """
    Returns list of (level, name)
    """
    structure = []

    with open(path, "r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            if not raw.strip():
                continue

            normalized = normalize_line(raw.rstrip("\n"))
            if not normalized:
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

    for lineno, level, name in structure:
        if level > len(stack):
            errors.append(f"Line {lineno}: invalid indentation jump → {name}")

        if stack and level > len(stack):
            parent = stack[-1]
            if not parent.endswith("/"):
                errors.append(f"Line {lineno}: файл не может иметь детей → {parent}")

        if name in seen[level]:
            errors.append(f"Line {lineno}: duplicate entry at same level → {name}")

        seen[level].add(name)
        stack = stack[:level]
        stack.append(name)

    return errors


# ─────────────────────────────────────────────────────────────
# Tree rendering (for README)
# ─────────────────────────────────────────────────────────────


def render_tree(structure):
    if not structure:
        return ""

    lines = []
    # Стек для отслеживания, является ли узел последним на своём уровне
    last_at_level = []

    for i, (_, level, name) in enumerate(structure):
        # Обновляем стек: обрезаем до текущего уровня
        if len(last_at_level) > level:
            last_at_level = last_at_level[:level]

        # Определяем, последний ли это элемент на своём уровне
        is_last = (i == len(structure) - 1) or (structure[i + 1][1] < level + 1)

        # Добавляем флаг последнего для текущего уровня
        if len(last_at_level) == level:
            last_at_level.append(is_last)
        else:
            last_at_level = last_at_level[:level] + [is_last]

        # Строим префикс
        prefix_parts = []
        for lvl in range(level):
            if lvl < len(last_at_level) - 1:
                prefix_parts.append("│   " if not last_at_level[lvl] else "    ")
            # Для последнего уровня префикс не нужен
        prefix = "".join(prefix_parts)

        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{name}")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# Generation
# ─────────────────────────────────────────────────────────────


def generate(structure, base_path, force=False):
    """
    Создаёт структуру файлов и папок на основе распарсенного шаблона.
    
    Args:
        structure: список кортежей (lineno, level, name)
        base_path: корневая директория для создания
        force: перезаписывать существующие файлы
    """
    stack = []  # Текущий путь (только папки)
    root_name = structure[0][2].rstrip("/") if structure else "project"
    
    # Статистика
    created_dirs = 0
    created_files = 0
    skipped_files = 0
    
    for lineno, level, name in structure:
        # Обрезаем стек до текущего уровня (убираем детей)
        stack = stack[:level]
        
        # Строим полный путь
        path_parts = [base_path] + stack + [name.rstrip("/")]
        path = os.path.join(*path_parts)
        
        is_dir = name.endswith("/")
        
        if is_dir:
            # Создаём папку
            try:
                os.makedirs(path, exist_ok=True)
                created_dirs += 1
                # Добавляем папку в стек для её возможных детей
                stack.append(name.rstrip("/"))
            except OSError as e:
                print(f"⚠️  Строка {lineno}: не удалось создать папку '{path}': {e}")
                
        else:
            # Создаём файл
            parent_dir = os.path.dirname(path)
            if parent_dir:  # На случай, если файл в корне
                try:
                    os.makedirs(parent_dir, exist_ok=True)
                except OSError as e:
                    print(f"⚠️  Строка {lineno}: не удалось создать родительскую папку для '{path}': {e}")
                    continue
            
            # Проверяем, нужно ли перезаписывать
            file_exists = os.path.exists(path)
            
            if force or not file_exists:
                try:
                    filename = os.path.basename(path)
                    template = FILE_TEMPLATES.get(filename)
                    
                    if template:
                        content = template.format(
                            project_name=root_name,
                            structure=render_tree(structure),
                        )
                        with open(path, "w", encoding="utf-8") as f:
                            f.write(content)
                    else:
                        # Пустой файл
                        with open(path, "w", encoding="utf-8") as f:
                            pass
                    
                    created_files += 1
                    if file_exists:
                        print(f"    Overwritten: {path}")
                        
                except OSError as e:
                    print(f"    Row {lineno}: error writing file '{path}': {e}")
            else:
                skipped_files += 1
                print(f"    Skipped (already exists): {path}")
    
    # Итоговая статистика
    print(f"    Created folders: {created_dirs}")
    print(f"    Created files: {created_files}")
    if skipped_files > 0:
        print(f"    Skipped files: {skipped_files}")

# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────


def entry_point():
    parser = argparse.ArgumentParser(
        description="crig — генератор структуры проекта из текстового дерева",
        epilog="Пример: crig --init → (редактируешь template.txt) → crig → готово!",
        add_help=False,  # отключаем стандартный -h/--help, чтобы добавить свой ниже
    )

    # Добавляем свой --help (чтобы он отображался красиво и не конфликтовал)
    parser.add_argument(
        "-h", "--help", action="help", help="показать эту справку и выйти"
    )

    # Добавляем --version
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version="crig 0.1.0",  # замени на свою актуальную версию
        help="показать версию программы и выйти",
    )

    parser.add_argument(
        "-i",
        "--init",
        action="store_true",
        help="создать базовый template.txt (если его нет)",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="перезаписывать существующие файлы и template.txt (при --init)",
    )
    parser.add_argument(
        "-t",
        "--template",
        default="template.txt",
        help="указать другой файл шаблона (по умолчанию: template.txt)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="показать, что будет создано, без реальных изменений на диске",
    )

    args = parser.parse_args()
    template_path = args.template

    # 1. Режим --init
    if args.init:
        if os.path.exists(template_path) and not args.force:
            print(
                f"⚠️  {template_path} уже существует. Используйте --force для перезаписи."
            )
            return

        # Базовый универсальный шаблон — подходит почти под любой проект
        default_template = """myproject/
├── src/
│   ├── __init__.py
│   └── main.py
├── tests/
├── README.md
├── requirements.txt
└── .gitignore
"""

        with open(template_path, "w", encoding="utf-8") as f:
            f.write(default_template.strip() + "\n")

        print(f"✅ Базовый {template_path} создан!")
        print("   Теперь просто запустите: crig")
        return

    # 2. Проверка наличия шаблона
    if not os.path.exists(template_path):
        print(f"❌ Файл {template_path} не найден.")
        print("   Запустите `crig --init` для создания базового шаблона.")
        return

    # 3. Парсинг и валидация
    structure = parse_template(template_path)
    errors = validate_structure(structure)
    if errors:
        print("❌ Ошибки в шаблоне:\n")
        for err in errors:
            print("   " + err)
        return

    # 4. Dry-run или реальное создание
    if args.dry_run:
        print("🩻 Dry run — ничего не будет создано на диске\n")
        print("Будет создано:")
        print(render_tree(structure))
        print("\nФайлы, которые получат содержимое:")
        for _, _, name in structure:
            filename = os.path.basename(name.rstrip("/"))
            if filename in FILE_TEMPLATES:
                print(f"  - {name}")
        print("\nЗапустите без --dry-run для реального создания.")
        return

    # 5. Реальная генерация
    BASE_DIR = os.getcwd()
    generate(structure, BASE_DIR, force=args.force)
    print("✅ Структура проекта успешно создана!")


if __name__ == "__main__":
    entry_point()
