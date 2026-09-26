"""Board-geometry conformance for the guest_wifi plugin.

Guest WiFi always has exactly one SSID and one password to show -- there is
no list or feed that should grow with a taller board, so `strict_growth` is
deliberately omitted here (a clock has the same exception: more rows don't
give it more to say). What the plugin must still get right on every shape is
the bug this suite guards against: the SSID and password must never be
clipped, from a 15-wide Note up to a 120-wide panel.
"""

import json
from pathlib import Path

from src.plugins.geometry_conformance import assert_board_conformance

from plugins.guest_wifi import GuestWifiPlugin

MANIFEST_PATH = Path(__file__).parent.parent / "manifest.json"
MANIFEST = json.loads(MANIFEST_PATH.read_text())


def make_plugin() -> GuestWifiPlugin:
    """Fresh, configured plugin. Guest WiFi makes no network calls to stub."""
    plugin = GuestWifiPlugin(MANIFEST)
    plugin.config = {
        "enabled": True,
        "ssid": "ALOHA-GUEST-5G",
        "password": "MAHALO2026",
    }
    return plugin


def test_renders_on_every_board_shape():
    assert_board_conformance(
        make_plugin,
        manifest=MANIFEST,
        require_note_array_preview=True,
    )
