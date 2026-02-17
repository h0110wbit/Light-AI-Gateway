"""
Settings panel
"""
import wx
import wx.lib.scrolledpanel as scrolled
import sys
from src.gui.theme import *
from src.gui.widgets import *


class SettingsPanel(wx.Panel):
    """Global settings panel"""

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.SetBackgroundColour(BG_PANEL)
        self._build_ui()

    def _build_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Header
        header = SectionHeader(self, "Settings",
                               "Configure global gateway options")
        sizer.Add(header, 0, wx.EXPAND | wx.ALL, PADDING_LG)
        sizer.Add(Divider(self), 0, wx.EXPAND)

        # Scrollable content
        scroll = scrolled.ScrolledPanel(self)
        scroll.SetBackgroundColour(BG_PANEL)
        form = wx.BoxSizer(wx.VERTICAL)

        # ── Server section ───────────────────────────────────────────────────
        self._add_section_label(scroll, form, "SERVER")

        # Host + Port row
        row = wx.Panel(scroll)
        row.SetBackgroundColour(BG_PANEL)
        row_sizer = wx.BoxSizer(wx.HORIZONTAL)

        host_panel = wx.Panel(row)
        host_panel.SetBackgroundColour(BG_PANEL)
        host_sizer = wx.BoxSizer(wx.VERTICAL)

        host_lbl = wx.StaticText(host_panel, label="LISTEN HOST")
        host_lbl.SetFont(make_font(8, bold=True))
        host_lbl.SetForegroundColour(TEXT_SECONDARY)
        host_sizer.Add(host_lbl, 0, wx.BOTTOM, 4)

        self.host_ctrl = wx.TextCtrl(host_panel, value="0.0.0.0")
        style_text_ctrl(self.host_ctrl)
        self.host_ctrl.SetMinSize((-1, 30))
        host_sizer.Add(self.host_ctrl, 0, wx.EXPAND)

        hint = wx.StaticText(
            host_panel,
            label="Use 0.0.0.0 for all interfaces, 127.0.0.1 for local only")
        hint.SetFont(make_font(7))
        hint.SetForegroundColour(TEXT_MUTED)
        host_sizer.Add(hint, 0, wx.TOP, 3)

        host_panel.SetSizer(host_sizer)
        row_sizer.Add(host_panel, 3, wx.EXPAND | wx.RIGHT, PADDING_MD)

        port_panel = wx.Panel(row)
        port_panel.SetBackgroundColour(BG_PANEL)
        port_sizer = wx.BoxSizer(wx.VERTICAL)

        port_lbl = wx.StaticText(port_panel, label="PORT")
        port_lbl.SetFont(make_font(8, bold=True))
        port_lbl.SetForegroundColour(TEXT_SECONDARY)
        port_sizer.Add(port_lbl, 0, wx.BOTTOM, 4)

        self.port_spin = wx.SpinCtrl(port_panel,
                                     value="3000",
                                     min=1024,
                                     max=65535)
        self.port_spin.SetBackgroundColour(BG_INPUT)
        self.port_spin.SetForegroundColour(TEXT_PRIMARY)
        self.port_spin.SetMinSize((-1, 30))
        port_sizer.Add(self.port_spin, 0, wx.EXPAND)

        port_panel.SetSizer(port_sizer)
        row_sizer.Add(port_panel, 1, wx.EXPAND)

        row.SetSizer(row_sizer)
        form.Add(row, 0, wx.EXPAND | wx.ALL, PADDING_MD)

        # Log level
        log_panel = wx.Panel(scroll)
        log_panel.SetBackgroundColour(BG_PANEL)
        log_sizer = wx.BoxSizer(wx.VERTICAL)

        log_lbl = wx.StaticText(log_panel, label="LOG LEVEL")
        log_lbl.SetFont(make_font(8, bold=True))
        log_lbl.SetForegroundColour(TEXT_SECONDARY)
        log_sizer.Add(log_lbl, 0, wx.BOTTOM, 4)

        self.log_level = wx.Choice(
            log_panel, choices=["debug", "info", "warning", "error"])
        self.log_level.SetSelection(1)  # info
        self.log_level.SetFont(make_font(9))
        self.log_level.SetBackgroundColour(BG_INPUT)
        self.log_level.SetMinSize((-1, 30))
        log_sizer.Add(self.log_level, 0)

        log_panel.SetSizer(log_sizer)
        form.Add(log_panel, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, PADDING_MD)

        form.Add(Divider(scroll), 0,
                 wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, PADDING_MD)

        # ── Security section ─────────────────────────────────────────────────
        self._add_section_label(scroll, form, "SECURITY")

        self.require_auth_check = wx.CheckBox(
            scroll, label="Require authentication (API token)")
        self.require_auth_check.SetValue(True)
        self.require_auth_check.SetFont(make_font(9))
        self.require_auth_check.SetForegroundColour(TEXT_PRIMARY)
        self.require_auth_check.SetBackgroundColour(BG_PANEL)
        form.Add(self.require_auth_check, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM,
                 PADDING_MD)

        auth_hint = wx.StaticText(
            scroll,
            label=
            "When enabled, all requests must include a valid Bearer token from the Tokens tab"
        )
        auth_hint.SetFont(make_font(8))
        auth_hint.SetForegroundColour(TEXT_MUTED)
        auth_hint.SetBackgroundColour(BG_PANEL)
        form.Add(auth_hint, 0, wx.LEFT | wx.BOTTOM, PADDING_MD)

        form.Add(Divider(scroll), 0,
                 wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, PADDING_MD)

        # ── Request handling section ──────────────────────────────────────────
        self._add_section_label(scroll, form, "REQUEST HANDLING")

        # Default timeout
        timeout_panel = wx.Panel(scroll)
        timeout_panel.SetBackgroundColour(BG_PANEL)
        timeout_sizer = wx.BoxSizer(wx.VERTICAL)

        timeout_lbl = wx.StaticText(timeout_panel,
                                    label="DEFAULT TIMEOUT (seconds)")
        timeout_lbl.SetFont(make_font(8, bold=True))
        timeout_lbl.SetForegroundColour(TEXT_SECONDARY)
        timeout_sizer.Add(timeout_lbl, 0, wx.BOTTOM, 4)

        self.timeout_spin = wx.SpinCtrl(timeout_panel,
                                        value="120",
                                        min=10,
                                        max=600)
        self.timeout_spin.SetBackgroundColour(BG_INPUT)
        self.timeout_spin.SetForegroundColour(TEXT_PRIMARY)
        self.timeout_spin.SetMinSize((-1, 30))
        timeout_sizer.Add(self.timeout_spin, 0)

        timeout_panel.SetSizer(timeout_sizer)
        form.Add(timeout_panel, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, PADDING_MD)

        self.fallback_check = wx.CheckBox(
            scroll,
            label="Enable channel fallback (try next channel on failure)")
        self.fallback_check.SetValue(True)
        self.fallback_check.SetFont(make_font(9))
        self.fallback_check.SetForegroundColour(TEXT_PRIMARY)
        self.fallback_check.SetBackgroundColour(BG_PANEL)
        form.Add(self.fallback_check, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM,
                 PADDING_MD)

        form.Add(Divider(scroll), 0,
                 wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, PADDING_MD)

        # ── CORS section ─────────────────────────────────────────────────────
        self._add_section_label(scroll, form, "CORS")

        self.cors_check = wx.CheckBox(scroll, label="Enable CORS headers")
        self.cors_check.SetValue(True)
        self.cors_check.SetFont(make_font(9))
        self.cors_check.SetForegroundColour(TEXT_PRIMARY)
        self.cors_check.SetBackgroundColour(BG_PANEL)
        form.Add(self.cors_check, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM,
                 PADDING_MD)

        cors_panel = wx.Panel(scroll)
        cors_panel.SetBackgroundColour(BG_PANEL)
        cors_sizer = wx.BoxSizer(wx.VERTICAL)

        cors_origins_lbl = wx.StaticText(
            cors_panel, label="ALLOWED ORIGINS (comma-separated)")
        cors_origins_lbl.SetFont(make_font(8, bold=True))
        cors_origins_lbl.SetForegroundColour(TEXT_SECONDARY)
        cors_sizer.Add(cors_origins_lbl, 0, wx.BOTTOM, 4)

        self.cors_origins_ctrl = wx.TextCtrl(cors_panel, value="*")
        style_text_ctrl(self.cors_origins_ctrl)
        self.cors_origins_ctrl.SetMinSize((-1, 30))
        cors_sizer.Add(self.cors_origins_ctrl, 0, wx.EXPAND)

        cors_panel.SetSizer(cors_sizer)
        form.Add(cors_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
                 PADDING_MD)

        form.Add(Divider(scroll), 0,
                 wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, PADDING_MD)

        # ── System section ───────────────────────────────────────────────────
        self._add_section_label(scroll, form, "SYSTEM")

        # Auto-start checkbox (Windows only)
        if sys.platform == "win32":
            self.auto_start_check = wx.CheckBox(
                scroll, label="Start with Windows (auto-start on login)")
            self.auto_start_check.SetValue(False)
            self.auto_start_check.SetFont(make_font(9))
            self.auto_start_check.SetForegroundColour(TEXT_PRIMARY)
            self.auto_start_check.SetBackgroundColour(BG_PANEL)
            form.Add(self.auto_start_check, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM,
                     PADDING_MD)

            auto_start_hint = wx.StaticText(
                scroll,
                label=
                "When enabled, AI Gateway will start automatically when you log in to Windows"
            )
            auto_start_hint.SetFont(make_font(8))
            auto_start_hint.SetForegroundColour(TEXT_MUTED)
            auto_start_hint.SetBackgroundColour(BG_PANEL)
            form.Add(auto_start_hint, 0, wx.LEFT | wx.BOTTOM, PADDING_MD)

        # Spacer at bottom
        form.AddSpacer(PADDING_LG)

        scroll.SetSizer(form)
        scroll.SetupScrolling()
        sizer.Add(scroll, 1, wx.EXPAND)

        # Save button
        sizer.Add(Divider(self), 0, wx.EXPAND)

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        btn_row.AddStretchSpacer()

        self.reset_btn = wx.Button(self,
                                   label="Reset Defaults",
                                   size=(120, 34))
        style_button_secondary(self.reset_btn)
        btn_row.Add(self.reset_btn, 0, wx.RIGHT, PADDING_SM)

        self.save_btn = wx.Button(self, label="Save Settings", size=(130, 34))
        style_button_primary(self.save_btn)
        btn_row.Add(self.save_btn, 0)

        sizer.Add(btn_row, 0, wx.ALL, PADDING_MD)

        self.SetSizer(sizer)

        self.save_btn.Bind(wx.EVT_BUTTON, self.on_save)
        self.reset_btn.Bind(wx.EVT_BUTTON, self.on_reset)

        # Initial load
        self.refresh()

    def _add_section_label(self, parent, sizer, text: str):
        lbl = wx.StaticText(parent, label=text)
        lbl.SetFont(make_font(9, bold=True))
        lbl.SetForegroundColour(ACCENT)
        sizer.Add(lbl, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, PADDING_MD)

    def refresh(self):
        config = self.controller.get_config()
        s = config.settings

        self.host_ctrl.SetValue(s.host)
        self.port_spin.SetValue(s.port)

        log_levels = ["debug", "info", "warning", "error"]
        try:
            idx = log_levels.index(s.log_level)
            self.log_level.SetSelection(idx)
        except ValueError:
            self.log_level.SetSelection(1)

        self.require_auth_check.SetValue(s.require_auth)
        self.timeout_spin.SetValue(s.default_timeout)
        self.fallback_check.SetValue(s.enable_fallback)
        self.cors_check.SetValue(s.enable_cors)
        self.cors_origins_ctrl.SetValue(", ".join(s.cors_origins))

        # Auto-start (Windows only)
        if sys.platform == "win32" and hasattr(self, 'auto_start_check'):
            self.auto_start_check.SetValue(s.auto_start)

    def on_save(self, event):
        cors_str = self.cors_origins_ctrl.GetValue().strip()
        cors_origins = [o.strip()
                        for o in cors_str.split(",") if o.strip()] or ["*"]

        log_levels = ["debug", "info", "warning", "error"]
        log_level = log_levels[self.log_level.GetSelection()]

        settings_data = {
            "host":
            self.host_ctrl.GetValue().strip() or "0.0.0.0",
            "port":
            self.port_spin.GetValue(),
            "log_level":
            log_level,
            "require_auth":
            self.require_auth_check.GetValue(),
            "default_timeout":
            self.timeout_spin.GetValue(),
            "enable_fallback":
            self.fallback_check.GetValue(),
            "enable_cors":
            self.cors_check.GetValue(),
            "cors_origins":
            cors_origins,
            "auto_start":
            self.auto_start_check.GetValue() if sys.platform == "win32"
            and hasattr(self, 'auto_start_check') else False,
        }

        self.controller.update_settings(settings_data)
        wx.MessageBox(
            "Settings saved successfully!\nRestart the server to apply changes.",
            "Settings Saved", wx.OK | wx.ICON_INFORMATION)

    def on_reset(self, event):
        result = wx.MessageBox("Reset all settings to defaults?",
                               "Confirm Reset",
                               wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING)
        if result == wx.YES:
            from src.models.config import GatewaySettings
            defaults = GatewaySettings()
            self.host_ctrl.SetValue(defaults.host)
            self.port_spin.SetValue(defaults.port)
            self.log_level.SetSelection(1)
            self.require_auth_check.SetValue(defaults.require_auth)
            self.timeout_spin.SetValue(defaults.default_timeout)
            self.fallback_check.SetValue(defaults.enable_fallback)
            self.cors_check.SetValue(defaults.enable_cors)
            self.cors_origins_ctrl.SetValue("*")
            if sys.platform == "win32" and hasattr(self, 'auto_start_check'):
                self.auto_start_check.SetValue(defaults.auto_start)
