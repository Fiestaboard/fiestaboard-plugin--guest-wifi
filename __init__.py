"""Guest WiFi plugin for FiestaBoard.

Displays guest WiFi credentials on your board.
"""

from typing import Any, Dict, List, Optional
import logging

from src.plugins.base import PluginBase, PluginResult
from src.text_to_board import count_tiles, take_tiles

logger = logging.getLogger(__name__)

# The narrowest board a user can own is a Note (15 cols). A credential
# declared longer than that passes config validation but silently clips
# when it lands on a Note -- and a truncated WiFi password is unusable.
# Capping storage here means the raw value always fits every board, on its
# own line, with no wrapping or truncation needed.
MAX_CREDENTIAL_LENGTH = 15


def _wrap_to_width(value: str, width: int) -> List[str]:
    """Split *value* into ``width``-tile chunks without dropping any of it.

    Used only as a defensive fallback for a credential that is wider than
    the current board (e.g. a value saved before ``MAX_CREDENTIAL_LENGTH``
    existed, now rendered on a Note). Wrapping keeps every character on the
    board somewhere instead of clipping it off.
    """
    lines: List[str] = []
    remaining = value
    while remaining:
        head, remaining = take_tiles(remaining, width)
        lines.append(head)
    return lines or [""]


class GuestWifiPlugin(PluginBase):
    """Guest WiFi credentials plugin.

    Displays configured SSID and password for guest access.
    """

    def __init__(self, manifest: Dict[str, Any]):
        """Initialize the guest wifi plugin."""
        super().__init__(manifest)

    @property
    def plugin_id(self) -> str:
        return "guest_wifi"

    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        """Validate guest wifi configuration."""
        errors = []

        if not config.get("ssid"):
            errors.append("SSID is required")
        elif len(config["ssid"]) > MAX_CREDENTIAL_LENGTH:
            errors.append(f"SSID must be {MAX_CREDENTIAL_LENGTH} characters or less")

        if not config.get("password"):
            errors.append("Password is required")
        elif len(config["password"]) > MAX_CREDENTIAL_LENGTH:
            errors.append(f"Password must be {MAX_CREDENTIAL_LENGTH} characters or less")

        return errors

    def fetch_data(self) -> PluginResult:
        """Fetch guest wifi data (from config)."""
        ssid = self.config.get("ssid", "")
        password = self.config.get("password", "")

        if not ssid or not password:
            return PluginResult(
                available=False,
                error="Guest WiFi not configured"
            )

        data = {
            "ssid": ssid,
            "password": password,
        }

        return PluginResult(
            available=True,
            data=data
        )

    @staticmethod
    def _labeled_lines(label: str, value: str, width: int) -> List[str]:
        """Render "LABEL: value" inline if it fits *width* tiles.

        Otherwise the label moves to its own line and the value gets a full
        width-wide line (or lines, via ``_wrap_to_width``) to itself, so the
        credential is never truncated -- only the label placement changes.
        """
        inline = f"{label}: {value}"
        if count_tiles(inline) <= width:
            return [inline]
        value_lines = [value] if count_tiles(value) <= width else _wrap_to_width(value, width)
        return [label, *value_lines]

    def get_formatted_display(self) -> Optional[List[str]]:
        """Return default formatted guest wifi display, adapted to the board.

        Reads ``self.board`` (defaulting to a Flagship 22x6 when unbound) and
        derives every width/height from it -- there is no literal 22 or 6 on
        this path. A label stays inline with its value ("NETWORK: my-ssid")
        when that fits the board's width; when it doesn't, the label moves to
        its own line rather than truncating the SSID or password, which would
        make a clipped password unusable.

        Guest WiFi always has exactly one SSID and one password to show, so
        a taller board doesn't get more *content* -- it gets more room for
        decoration (a title, blank spacers). The most decorated layout that
        still fits ``board.rows`` is used; the credentials themselves are
        never the part that gets dropped.
        """
        result = self.fetch_data()
        if not result.available or not result.data:
            return None

        data = result.data
        board = self.board
        width = board.cols if board else 22
        height = board.rows if board else 6

        ssid = data["ssid"]
        password = data["password"]

        network_lines = self._labeled_lines("NETWORK", ssid, width)
        password_lines = self._labeled_lines("PASSWORD", password, width)
        raw_ssid_lines = [ssid] if count_tiles(ssid) <= width else _wrap_to_width(ssid, width)
        raw_password_lines = [password] if count_tiles(password) <= width else _wrap_to_width(password, width)
        title = "GUEST WIFI".center(width)[:width]

        # Ordered most- to least-decorated. Every line already fits `width`
        # by construction; the first candidate that also fits `height` wins.
        # Decoration (title, blank spacers, labels) is shed under pressure --
        # the credential values are never the part that gets cut.
        candidates: List[List[str]] = [
            [title, "", *network_lines, "", *password_lines, ""],
            [title, *network_lines, "", *password_lines],
            [title, *network_lines, *password_lines],
            [*network_lines, *password_lines],
            [title, *raw_ssid_lines, *raw_password_lines],
            [*raw_ssid_lines, *raw_password_lines],
        ]
        for lines in candidates:
            if len(lines) <= height:
                return lines

        # No candidate fit -- would require a board shorter than 2 rows,
        # which nothing the platform supports today has. Fall back to the
        # smallest layout rather than crashing.
        return candidates[-1][:height]


# Export the plugin class
Plugin = GuestWifiPlugin
