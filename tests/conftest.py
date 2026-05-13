from __future__ import annotations
import sys
from unittest.mock import MagicMock

# Stub out google.genai so tests that import main/orchestrator don't fail
# in environments where google-cloud packages aren't installed.
_google = MagicMock()
_google.genai = MagicMock()
sys.modules.setdefault("google", _google)
sys.modules.setdefault("google.genai", _google.genai)
