#!/usr/bin/env python3
"""
Minimal production hardening patch:
- Fix APP_DIR resolution for PyInstaller frozen builds (DB + logs beside EXE)
- Guard SettingsDialog async callback against destroyed widget
- Remove unused aiofiles from requirements.txt (optional cleanup)
- Ensure assets/icon.ico exists (avoid build warning)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FILES = {
    "db": ROOT / "app" / "storage" / "database.py",
    "log": ROOT / "app" / "utils" / "logging_setup.py",
    "settings": ROOT / "app" / "ui" / "settings_dialog.py",
    "req": ROOT / "requirements.txt",
    "assets_dir": ROOT / "assets",
    "icon": ROOT / "assets" / "icon.ico",
}


def read_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(str(path))
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def patch_app_dir(path: Path) -> bool:
    """
    Replace a brittle APP_DIR assignment based on __file__ parents with a frozen-safe version.

    We look for a line like:
        APP_DIR = Path(__file__).parent.parent.parent
    or similar (with resolve()/parents[]), and replace with:

        import sys
        from pathlib import Path

        if getattr(sys, "frozen", False):
            APP_DIR = Path(sys.executable).parent
        else:
            APP_DIR = Path(__file__).resolve().parents[2]
    """
    s = read_text(path)

    # If already patched, no-op.
    if "getattr(sys, \"frozen\", False)" in s or "Path(sys.executable).parent" in s:
        return False

    # Ensure sys import exists (we'll inject cleanly near imports)
    has_sys_import = re.search(r"^\s*import\s+sys\s*$", s, re.M) is not None
    has_pathlib_import = re.search(r"^\s*from\s+pathlib\s+import\s+Path\s*$", s, re.M) is not None

    # Locate an APP_DIR assignment
    m = re.search(r"^\s*APP_DIR\s*=\s*Path\(__file__\).*?$", s, re.M)
    if not m:
        # Try broader match (some code may use resolve().parents)
        m = re.search(r"^\s*APP_DIR\s*=\s*Path\(__file__\)\.resolve\(\)\.parents\[\d+\]\s*$", s, re.M)
    if not m:
        raise RuntimeError(f"Could not find APP_DIR assignment to patch in {path}")

    # Insert missing imports at the top of file (after shebang/comments/docstring and initial imports)
    lines = s.splitlines(True)

    # Find insertion point: after module docstring if present, else after initial comments
    insert_at = 0
    if lines and lines[0].startswith("#!"):
        insert_at = 1

    # Handle module docstring
    joined = "".join(lines)
    doc_m = re.match(r"^(\s*(?:#!.*\n)?\s*(?:#.*\n)*)\s*([\"']{3})", joined)
    if doc_m:
        # find end of docstring
        q = doc_m.group(2)
        start = joined.find(q)
        end = joined.find(q, start + 3)
        if end != -1:
            end = joined.find("\n", end + 3)
            if end != -1:
                # compute line index
                prefix = joined[: end + 1]
                insert_at = prefix.count("\n")

    import_block = ""
    if not has_sys_import:
        import_block += "import sys\n"
    if not has_pathlib_import:
        import_block += "from pathlib import Path\n"
    if import_block:
        # Insert after any existing imports header; simplest: insert at insert_at
        lines.insert(insert_at, import_block)
        s = "".join(lines)

    # Replace APP_DIR line with frozen-safe block
    replacement = (
        'if getattr(sys, "frozen", False):\n'
        "    APP_DIR = Path(sys.executable).parent\n"
        "else:\n"
        "    APP_DIR = Path(__file__).resolve().parents[2]\n"
    )

    s2 = re.sub(r"^\s*APP_DIR\s*=\s*Path\(__file__\).*?$", replacement, s, flags=re.M)
    if s2 == s:
        # Try other pattern if first didn't match
        s2 = re.sub(r"^\s*APP_DIR\s*=\s*Path\(__file__\)\.resolve\(\)\.parents\[\d+\]\s*$", replacement, s, flags=re.M)

    if s2 == s:
        raise RuntimeError(f"Failed to replace APP_DIR assignment in {path}")

    write_text(path, s2)
    return True


def patch_settings_dialog(path: Path) -> bool:
    """
    Guard self.after(...) calls when dialog might be destroyed.
    We specifically patch the Test Notification failure/success callback pattern.

    We look for:
        self.after(0, lambda: messagebox.showerror(..., parent=self))
    and wrap with winfo_exists() guard.
    """
    s = read_text(path)
    if "winfo_exists" in s and "Test Failed" in s:
        return False

    # Patch both showerror and showinfo using a robust guard.
    def guarded(match: re.Match) -> str:
        inner = match.group(1)
        return (
            "try:\n"
            "            if self.winfo_exists():\n"
            f"                {inner}\n"
            "        except Exception:\n"
            "            pass"
        )

    # Match `self.after(0, lambda: messagebox.showerror(... parent=self))`
    pat = re.compile(r"^\s*self\.after\(\s*0\s*,\s*lambda:\s*(messagebox\.show(?:error|info)\(.*?parent=self.*?\))\s*\)\s*$", re.M)
    matches = list(pat.finditer(s))
    if not matches:
        # If pattern differs, fail loudly so you don't think it's patched.
        raise RuntimeError("Could not find self.after(...messagebox...) pattern in SettingsDialog to guard.")

    # Replace each match line with guarded block at same indentation (8 spaces typical)
    def repl(m: re.Match) -> str:
        indent = re.match(r"^\s*", m.group(0)).group(0)
        inner = m.group(1)
        block = (
            f"{indent}try:\n"
            f"{indent}    if self.winfo_exists():\n"
            f"{indent}        self.after(0, lambda: {inner})\n"
            f"{indent}except Exception:\n"
            f"{indent}    pass"
        )
        return block

    s2 = pat.sub(repl, s)
    write_text(path, s2)
    return True


def patch_requirements(path: Path) -> bool:
    if not path.exists():
        return False
    s = read_text(path)
    lines = [ln.rstrip("\n") for ln in s.splitlines()]
    new_lines = [ln for ln in lines if not ln.strip().lower().startswith("aiofiles")]
    if new_lines == lines:
        return False
    write_text(path, "\n".join(new_lines).rstrip() + "\n")
    return True


def ensure_assets(icon_path: Path) -> bool:
    icon_path.parent.mkdir(parents=True, exist_ok=True)
    if icon_path.exists():
        return False
    # Minimal placeholder (not a real ICO), but avoids missing-path warnings.
    # You can replace it later with a real .ico without code changes.
    icon_path.write_bytes(b"")
    return True


def main() -> int:
    changes = []

    # Critical: APP_DIR patches
    for k in ("db", "log"):
        changed = patch_app_dir(FILES[k])
        changes.append((FILES[k], changed))

    # Moderate: settings dialog guard
    changed = patch_settings_dialog(FILES["settings"])
    changes.append((FILES["settings"], changed))

    # Low: remove unused aiofiles
    changed = patch_requirements(FILES["req"])
    changes.append((FILES["req"], changed))

    # Packaging nicety: assets/icon.ico
    changed = ensure_assets(FILES["icon"])
    changes.append((FILES["icon"], changed))

    print("Production-ready patch results:")
    for p, c in changes:
        print(f"- {p.relative_to(ROOT)}: {'CHANGED' if c else 'no-op'}")

    print("\nNext steps:")
    print("1) Run dev smoke test: python main.py")
    print("2) Build exe:        python build.py")
    print("3) Test exe:         dist/<AppName>/<AppName>.exe (confirm DB + logs beside exe)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())