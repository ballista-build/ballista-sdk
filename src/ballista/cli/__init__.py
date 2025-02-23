import sys

try:
    from .cli import cli
except ImportError:
    print(f"Install 'ballista[cli]' to use the CLI.")
    sys.exit(0)


__all__ = ["cli"]
