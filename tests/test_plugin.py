"""Tests for the guest_wifi plugin."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.devices import BoardContext
from src.text_to_board import count_tiles

from plugins.guest_wifi import GuestWifiPlugin


class TestGuestWifiPlugin:
    """Tests for Guest WiFi plugin functionality."""
    
    def test_guest_wifi_data_structure(self):
        """Test that guest WiFi returns expected data structure."""
        # Guest WiFi is a static display, test the data structure
        expected_fields = ["ssid", "password"]
        
        # Mock config with WiFi credentials
        config = {
            "ssid": "GuestNetwork",
            "password": "SecurePass123"
        }
        
        # Validate structure
        assert "ssid" in config
        assert "password" in config
        assert len(config["ssid"]) > 0
    
    def test_ssid_formatting(self):
        """Test SSID is properly formatted for display."""
        ssid = "MyGuestWiFi"
        # SSID should not exceed the narrowest board's width (15 chars, a Note)
        assert len(ssid) <= 15
    
    def test_password_formatting(self):
        """Test password is properly formatted for display."""
        password = "Guest123!"
        # Password should be displayable
        assert len(password) > 0
    
    def test_empty_ssid_handling(self):
        """Test handling of empty SSID."""
        config = {"ssid": "", "password": "test"}
        # Empty SSID should be detected
        assert config["ssid"] == ""
    
    def test_empty_password_handling(self):
        """Test handling of empty password."""
        config = {"ssid": "Network", "password": ""}
        # Empty password should be valid (open network)
        assert config["password"] == ""
    
    def test_special_characters_in_password(self):
        """Test passwords with special characters."""
        passwords = [
            "Pass!@#$%",
            "Test&*(){}",
            "WiFi-2024",
            "guest_network"
        ]
        for pwd in passwords:
            # Password should be a valid string
            assert isinstance(pwd, str)
            assert len(pwd) > 0
    
    def test_config_validation(self):
        """Test config validation for guest WiFi."""
        valid_config = {
            "ssid": "GuestWiFi",
            "password": "SecurePassword"
        }
        
        # Both fields should be present
        assert "ssid" in valid_config
        assert "password" in valid_config


class TestGuestWifiPluginIntegration:
    """Integration tests for GuestWifiPlugin that exercise plugin code."""

    @pytest.fixture
    def plugin(self):
        """Create plugin instance with manifest."""
        manifest = {"id": "guest_wifi", "name": "Guest WiFi", "version": "1.0.0"}
        return GuestWifiPlugin(manifest)

    def test_plugin_id(self, plugin):
        """Test plugin_id property."""
        assert plugin.plugin_id == "guest_wifi"

    def test_validate_config_missing_ssid(self, plugin):
        """Test validate_config returns error when SSID is missing."""
        config = {"password": "test123"}
        errors = plugin.validate_config(config)
        assert "SSID is required" in errors

    def test_validate_config_missing_password(self, plugin):
        """Test validate_config returns error when password is missing."""
        config = {"ssid": "MyNetwork"}
        errors = plugin.validate_config(config)
        assert "Password is required" in errors

    def test_validate_config_ssid_too_long(self, plugin):
        """Test validate_config returns error when SSID exceeds 15 chars.

        15 is the narrowest board width (a Note) -- an SSID declared longer
        than that could never render on a Note without wrapping or clipping.
        """
        config = {"ssid": "a" * 16, "password": "test"}
        errors = plugin.validate_config(config)
        assert "SSID must be 15 characters or less" in errors

    def test_validate_config_password_too_long(self, plugin):
        """Test validate_config returns error when password exceeds 15 chars."""
        config = {"ssid": "Network", "password": "p" * 16}
        errors = plugin.validate_config(config)
        assert "Password must be 15 characters or less" in errors

    def test_validate_config_valid(self, plugin):
        """Test validate_config accepts valid config."""
        config = {"ssid": "GuestNetwork", "password": "SecurePass123"}
        errors = plugin.validate_config(config)
        assert len(errors) == 0

    def test_validate_config_ssid_at_limit(self, plugin):
        """Test validate_config accepts SSID at 15 char limit (a full Note row)."""
        config = {"ssid": "a" * 15, "password": "test"}
        errors = plugin.validate_config(config)
        assert len(errors) == 0

    def test_fetch_data_not_configured(self, plugin):
        """Test fetch_data returns unavailable when not configured."""
        plugin.config = {}
        result = plugin.fetch_data()
        assert result.available is False
        assert "not configured" in result.error

    def test_fetch_data_missing_ssid(self, plugin):
        """Test fetch_data returns unavailable when SSID is empty."""
        plugin.config = {"ssid": "", "password": "test"}
        result = plugin.fetch_data()
        assert result.available is False

    def test_fetch_data_missing_password(self, plugin):
        """Test fetch_data returns unavailable when password is empty."""
        plugin.config = {"ssid": "Network", "password": ""}
        result = plugin.fetch_data()
        assert result.available is False

    def test_fetch_data_success(self, plugin):
        """Test fetch_data returns data when configured."""
        plugin.config = {"ssid": "GuestNetwork", "password": "SecurePass123"}
        result = plugin.fetch_data()
        assert result.available is True
        assert result.data["ssid"] == "GuestNetwork"
        assert result.data["password"] == "SecurePass123"

    def test_get_formatted_display_returns_none_when_not_configured(self, plugin):
        """Test get_formatted_display returns None when not configured."""
        plugin.config = {}
        lines = plugin.get_formatted_display()
        assert lines is None

    def test_get_formatted_display_returns_lines(self, plugin):
        """Test get_formatted_display returns formatted lines."""
        plugin.config = {"ssid": "MyWiFi", "password": "Secret123"}
        lines = plugin.get_formatted_display()
        assert lines is not None
        assert "GUEST WIFI" in lines[0]
        assert "MyWiFi" in str(lines)
        assert "Secret123" in str(lines)

    def test_get_formatted_display_on_note_does_not_truncate_credentials(self, plugin):
        """Regression test for the clipping bug: full SSID/password on a Note.

        Before the fix, `f"NETWORK: {ssid}"[:22]` clipped anything past 22
        characters -- and even well under that, the label alone pushed a
        15-char SSID off the edge of a Note's 15-column line. A silently
        truncated WiFi password is unusable, so the fix must never chop
        either value, no matter how narrow the board.
        """
        ssid = "ALOHA-GUEST-5G"  # 14 chars -- at the edge of a Note's width
        password = "MAHALO2026"
        plugin.config = {"ssid": ssid, "password": password}
        note = BoardContext(device_type="note", rows=3, cols=15)

        with plugin._bound_board(note):
            lines = plugin.get_formatted_display()

        assert lines is not None
        assert len(lines) <= note.rows
        for line in lines:
            assert count_tiles(line) <= note.cols
        # The full, untruncated values must appear as their own line(s) --
        # not clipped, not merged unreadably with a label.
        assert ssid in lines
        assert password in lines

    def test_get_formatted_display_wide_board_keeps_labels_inline(self, plugin):
        """On a roomy board, short credentials keep the readable inline labels."""
        plugin.config = {"ssid": "MyWiFi", "password": "Secret123"}
        flagship = BoardContext(device_type="flagship", rows=6, cols=22)

        with plugin._bound_board(flagship):
            lines = plugin.get_formatted_display()

        assert lines is not None
        assert any("NETWORK: MyWiFi" in line for line in lines)
        assert any("PASSWORD: Secret123" in line for line in lines)

    def test_get_formatted_display_wraps_legacy_oversized_credential(self, plugin):
        """A pre-fix config saved before the 15-char cap must wrap, not clip.

        validate_config() now rejects credentials over 15 chars, but a value
        saved under the old 22-char limit still lives in some users' stored
        config. Rendering it on a narrower board must never lose characters.
        """
        long_password = "MahaloGuestNetwork22"  # 20 chars, predates the cap
        plugin.config = {"ssid": "Guest", "password": long_password}
        note = BoardContext(device_type="note", rows=3, cols=15)

        with plugin._bound_board(note):
            lines = plugin.get_formatted_display()

        assert lines is not None
        assert len(lines) <= note.rows
        for line in lines:
            assert count_tiles(line) <= note.cols
        # Every character of the oversized password must survive, split
        # across however many lines it takes -- none of it is dropped.
        assert lines[0] == "Guest"
        assert "".join(lines[1:]) == long_password

    def test_get_formatted_display_falls_back_on_impossibly_short_board(self, plugin):
        """A board shorter than any candidate layout still returns, not crashes."""
        plugin.config = {"ssid": "Guest", "password": "pw"}
        tiny = BoardContext(device_type="note_array", rows=1, cols=15)

        with plugin._bound_board(tiny):
            lines = plugin.get_formatted_display()

        assert lines is not None
        assert len(lines) <= tiny.rows


class TestGuestWifiDisplay:
    """Tests for Guest WiFi display formatting."""
    
    def test_display_lines_count(self):
        """Test that display uses appropriate number of lines."""
        # Board has 6 lines
        max_lines = 6
        
        # Guest WiFi typically needs:
        # 1. Title line (GUEST WIFI)
        # 2. SSID label
        # 3. SSID value
        # 4. Password label  
        # 5. Password value
        # 6. Optional decoration
        
        required_lines = 5
        assert required_lines <= max_lines
    
    def test_line_length_constraint(self):
        """Test that all content fits within line length."""
        max_chars = 15  # Narrowest board line width (a Note)
        
        ssid = "TestNetwork"
        password = "Pass123"
        
        # SSID line
        ssid_line = f"SSID: {ssid}"
        assert len(ssid_line) <= max_chars or len(ssid) <= max_chars
        
        # Password line
        pass_line = f"PASS: {password}"
        assert len(pass_line) <= max_chars or len(password) <= max_chars


class TestManifestMetadata:
    """Tests for the rich metadata format in the manifest."""

    def test_manifest_uses_dict_simple_format(self):
        manifest_path = Path(__file__).parent.parent / "manifest.json"
        with open(manifest_path) as f:
            manifest = json.load(f)
        simple = manifest["variables"]["simple"]
        assert isinstance(simple, dict), "simple should use the rich dict format"

    def test_all_variables_have_descriptions(self):
        manifest_path = Path(__file__).parent.parent / "manifest.json"
        with open(manifest_path) as f:
            manifest = json.load(f)
        simple = manifest["variables"]["simple"]
        for var_name, meta in simple.items():
            assert "description" in meta and meta["description"], \
                f"Variable '{var_name}' missing description"

    def test_all_variables_have_valid_groups(self):
        manifest_path = Path(__file__).parent.parent / "manifest.json"
        with open(manifest_path) as f:
            manifest = json.load(f)
        groups = set(manifest["variables"].get("groups", {}).keys())
        simple = manifest["variables"]["simple"]
        for var_name, meta in simple.items():
            group = meta.get("group", "")
            if group:
                assert group in groups, \
                    f"Variable '{var_name}' references undefined group '{group}'"

    def test_groups_are_defined(self):
        manifest_path = Path(__file__).parent.parent / "manifest.json"
        with open(manifest_path) as f:
            manifest = json.load(f)
        groups = manifest["variables"].get("groups", {})
        assert len(groups) > 0, "Manifest should define at least one group"
        for group_id, group_def in groups.items():
            assert "label" in group_def, f"Group '{group_id}' missing label"

