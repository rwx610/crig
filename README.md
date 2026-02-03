# Crig
Генератор структуры проекта из текстового дерева.
Одна команда — одна файловая структура.

## Установка
```bash
pip install crig
```

## Использование
Bash
```
# В пустой папке проекта
crig --init          # создаёт базовый template.txt (если нет)
# --force для перезаписи

# Редактируете template.txt под свой проект

crig --dry-run       # посмотреть, что будет создано
crig                 # создать структуру
```

Можно использовать другой файл шаблона:

Bash

```
crig -t my_structure.txt
```

## Формат template.txt

Поддерживается:

- Дерево с ├──/└──
- Отступы пробелами (4 пробела = 1 уровень) или табами
- Комментарии в той же строке после имени
- Заметки в скобках, с тире, TODO и т.д. — игнорируются

Пример:

text

```
game/
├── scenes/
│   ├── MainMenu.tscn       # главное меню
│   ├── GameBoard.tscn      # игровая доска
│   └── Piece.tscn          # фишки
├── scripts/
│   ├── GameManager.gd
│   └── rules/              # правила игры
│       ├── BaseRules.gd
│       └── ClassicRules.gd 
├── assets/                 (текстуры — добавить вручную)
└── project.godot
```

## Возможности

- Валидация отступов, дубликатов и недопустимых детей у файлов
- Автоматическое создание содержимого для:
    - README.md (с названием проекта и деревом)
    - __init__.py
    - main.py
    - .gitignore
- Существующие файлы не перезаписываются
- Ноль внешних зависимостей

## Команды

Bash

```
crig                 # создать структуру по template.txt
crig --init          # создать базовый template.txt (если нет)
crig --init --force  # перезаписать существующий template.txt
crig --dry-run       # показать, что будет создано (без изменений на диске)
crig -t <file>       # использовать другой файл шаблона вместо template.txt
crig -h              # показать справку
crig -v              # показать версию
```

## Лицензия
MIT





# Crig

## Description
Project structure generated automatically by **crig** — a lightweight utility
to create project skeletons from a simple text-based tree template.

You can define your project hierarchy using a plain-text tree, and **crig** will
create all folders and files, optionally filling them with basic templates.

---

## Structure
{structure}

---

## Template Grammar (EBNF)

A simple formal grammar for **crig templates**:

```ebnf
template     ::= entry { newline entry }
entry        ::= indent name newline
indent       ::= { "\t" }         ; 0 or more tab characters
name         ::= valid_filename [ "/" ] ; folder ends with '/'
valid_filename ::= letter { letter | digit | "_" | "-" | "." }
newline      ::= "\n"
Rules
Root folder: There must be exactly one root directory at level 0.

Folders: End with a / to indicate a directory.

Files: Names without a trailing /.

Indentation: Tabs only (each tab = one level). Spaces in indentation are ignored if using tree style (├──, └──).

Allowed characters: letters, digits, _, -, .

Comments / ignored lines: Lines starting with // or empty lines are skipped.

Example:

text
Копировать код
myproject/
├── src/
│   ├── __init__.py
│   └── main.py
├── tests/
├── README.md
├── requirements.txt
└── .gitignore
Usage
bash
Копировать код
# Create a base template
crig --init

# Preview the structure without writing files
crig --dry-run

# Generate files/folders according to template.txt
crig

# Explain which lines are ignored/dropped
crig --explain
Notes
If your template has multiple roots, a folder crig_root/ will be created and all content will be nested inside.

Duplicate file names at the same level are ignored, with explanation if --explain is used.

Strict enforcement: invalid characters or bad indentation → generation stops.