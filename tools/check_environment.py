"""Inspect local dependencies without changing the environment."""
import importlib.util
import sys

print(sys.version)
for name in ("PySide6", "numpy", "pandas", "scipy", "matplotlib", "PIL"):
    print(f"{name}: {importlib.util.find_spec(name) is not None}")
