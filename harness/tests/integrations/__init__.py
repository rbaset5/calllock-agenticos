"""Integration package tests.

Extends package resolution so tests/integrations does not shadow src/integrations.
"""

from pathlib import Path
from pkgutil import extend_path
import sys

__path__ = extend_path(__path__, __name__)

src_path = Path(__file__).resolve().parents[2] / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
