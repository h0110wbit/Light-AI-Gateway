"""
Dashboard panel - shows server status and quick stats
"""
import wx
import wx.lib.agw.hyperlink as hl
from src.gui.theme import *
from src.gui.widgets import *


def dip(window: wx.Window, size: int) -> int:
    """将逻辑尺寸转换为物理像素尺寸（DPI感知）。"""
    try:
        return window.FromDIP(size)
    except AttributeError:
        return size


def dip_size(window: wx.Window, width: int, height: int) -> tuple:
    """将逻辑尺寸元组转换为物理像素尺寸（DPI感知）。"""
    return (dip(window, width), dip(window, height))


class DashboardPanel(wx.Panel):
    """Main dashboard panel showing server status"""

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.SetBackgroundColour(BG_PANEL)
        self._build_ui()
        self._bind_events()

    def _build_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # ── Header ──────────────────────────────────────────────────────────
        header = wx.Panel(self)
        header.SetBackgroundColour(BG_DARK)
        header_sizer = wx.BoxSizer(wx.VERTICAL)

        # Logo / title area
        title_row = wx.BoxSizer(wx.HORIZONTAL)

        title_lbl = wx.StaticText(header, label="AI GATEWAY")
        title_lbl.SetFont(make_font(20, bold=True, family=FONT_TITLE))
        title_lbl.SetForegroundColour(ACCENT)
        title_row.Add(title_lbl, 0, wx.ALIGN_CENTER_VERTICAL)

        title_row.AddStretchSpacer()

        ver_lbl = wx.StaticText(header, label="v1.0.0")
        ver_lbl.SetFont(make_font(8))
        ver_lbl.SetForegroundColour(TEXT_MUTED)
        title_row.Add(ver_lbl, 0, wx.ALIGN_CENTER_VERTICAL)

        header_sizer.Add(title_row, 0, wx.EXPAND | wx.ALL, PADDING_LG)

        sub_lbl = wx.StaticText(header,
                                label="Personal Lightweight LLM API Gateway")
        sub_lbl.SetFont(make_font(9))
        sub_lbl.SetForegroundColour(TEXT_SECONDARY)
        header_sizer.Add(sub_lbl, 0, wx.LEFT | wx.BOTTOM, PADDING_LG)

        header.SetSizer(header_sizer)
        main_sizer.Add(header, 0, wx.EXPAND)

        # ── Status card ──────────────────────────────────────────────────────
        content = wx.Panel(self)
        content.SetBackgroundColour(BG_PANEL)
        content_sizer = wx.BoxSizer(wx.VERTICAL)

        status_card = wx.Panel(content)
        status_card.SetBackgroundColour(BG_CARD)
        status_sizer = wx.BoxSizer(wx.VERTICAL)

        # Status header row
        status_title_row = wx.BoxSizer(wx.HORIZONTAL)

        status_title = wx.StaticText(status_card, label="Server Status")
        status_title.SetFont(make_font(11, bold=True, family=FONT_TITLE))
        status_title.SetForegroundColour(TEXT_PRIMARY)
        status_title_row.Add(status_title, 0, wx.ALIGN_CENTER_VERTICAL)

        status_title_row.AddStretchSpacer()

        self.status_badge = StatusBadge(status_card, "stopped", "STOPPED")
        status_title_row.Add(self.status_badge, 0, wx.ALIGN_CENTER_VERTICAL)

        status_sizer.Add(status_title_row, 0, wx.EXPAND | wx.ALL, PADDING_MD)
        status_sizer.Add(Divider(status_card), 0,
                         wx.EXPAND | wx.LEFT | wx.RIGHT, PADDING_MD)

        # Server info grid
        info_grid = wx.FlexGridSizer(3, 2, 8, PADDING_XL)
        info_grid.AddGrowableCol(1, 1)

        def add_info_row(label: str, default: str, attr_name: str):
            lbl = wx.StaticText(status_card, label=label)
            lbl.SetFont(make_font(9))
            lbl.SetForegroundColour(TEXT_SECONDARY)

            val = wx.StaticText(status_card, label=default)
            val.SetFont(make_font(9, bold=True, family=FONT_MONO))
            val.SetForegroundColour(TEXT_PRIMARY)

            info_grid.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL)
            info_grid.Add(val, 0, wx.ALIGN_CENTER_VERTICAL)
            setattr(self, attr_name, val)

        add_info_row("Listen Address:", "—", "addr_label")
        add_info_row("Channels Active:", "0", "channels_label")
        add_info_row("Access Tokens:", "0", "tokens_label")

        status_sizer.Add(info_grid, 0, wx.ALL, PADDING_MD)

        # API Endpoint (shows clickable URL when running)
        endpoint_row = wx.BoxSizer(wx.HORIZONTAL)

        ep_lbl = wx.StaticText(status_card, label="API Endpoint:")
        ep_lbl.SetFont(make_font(9))
        ep_lbl.SetForegroundColour(TEXT_SECONDARY)
        endpoint_row.Add(ep_lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)

        self.endpoint_label = wx.StaticText(status_card, label="Not running")
        self.endpoint_label.SetFont(make_font(9, family=FONT_MONO))
        self.endpoint_label.SetForegroundColour(TEXT_MUTED)
        endpoint_row.Add(self.endpoint_label, 0, wx.ALIGN_CENTER_VERTICAL)

        status_sizer.Add(endpoint_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM,
                         PADDING_MD)

        status_card.SetSizer(status_sizer)
        content_sizer.Add(status_card, 0, wx.EXPAND | wx.ALL, PADDING_MD)

        # ── Control buttons ──────────────────────────────────────────────────
        btn_panel = wx.Panel(content)
        btn_panel.SetBackgroundColour(BG_PANEL)
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.start_btn = wx.Button(btn_panel,
                                   label="▶  Start Gateway",
                                   size=dip_size(btn_panel, 160, 40))
        style_button_primary(self.start_btn)
        btn_sizer.Add(self.start_btn, 0, wx.RIGHT, PADDING_SM)

        self.stop_btn = wx.Button(btn_panel,
                                  label="■  Stop Gateway",
                                  size=dip_size(btn_panel, 160, 40))
        style_button_secondary(self.stop_btn)
        self.stop_btn.SetBackgroundColour(BG_CARD)
        self.stop_btn.Enable(False)
        btn_sizer.Add(self.stop_btn, 0, wx.RIGHT, PADDING_SM)

        self.restart_btn = wx.Button(btn_panel,
                                     label="↺  Restart",
                                     size=dip_size(btn_panel, 160, 40))
        style_button_secondary(self.restart_btn)
        self.restart_btn.Enable(False)
        btn_sizer.Add(self.restart_btn, 0)

        btn_panel.SetSizer(btn_sizer)
        content_sizer.Add(btn_panel, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM,
                          PADDING_MD)

        # ── Quick stats cards ─────────────────────────────────────────────────
        stats_row = wx.BoxSizer(wx.HORIZONTAL)

        def make_stat_card(parent_panel, title: str, icon: str, attr: str):
            card = wx.Panel(parent_panel)
            card.SetBackgroundColour(BG_CARD)
            card_sizer = wx.BoxSizer(wx.VERTICAL)

            icon_lbl = wx.StaticText(card, label=icon)
            icon_lbl.SetFont(make_font(18))
            icon_lbl.SetForegroundColour(ACCENT)
            card_sizer.Add(icon_lbl, 0, wx.TOP | wx.LEFT, PADDING_MD)

            val_lbl = wx.StaticText(card, label="0")
            val_lbl.SetFont(make_font(22, bold=True, family=FONT_TITLE))
            val_lbl.SetForegroundColour(TEXT_PRIMARY)
            card_sizer.Add(val_lbl, 0, wx.LEFT, PADDING_MD)
            setattr(self, attr, val_lbl)

            title_lbl = wx.StaticText(card, label=title)
            title_lbl.SetFont(make_font(8))
            title_lbl.SetForegroundColour(TEXT_SECONDARY)
            card_sizer.Add(title_lbl, 0, wx.LEFT | wx.BOTTOM, PADDING_MD)

            card.SetSizer(card_sizer)
            card.SetMinSize(dip_size(card, 120, 100))
            return card

        stats_row.Add(
            make_stat_card(content, "Channels", "⟳", "stat_channels"), 1,
            wx.EXPAND | wx.RIGHT, PADDING_SM)
        stats_row.Add(make_stat_card(content, "Tokens", "🔑", "stat_tokens"), 1,
                      wx.EXPAND | wx.RIGHT, PADDING_SM)
        stats_row.Add(make_stat_card(content, "Models", "◈", "stat_models"), 1,
                      wx.EXPAND)

        content_sizer.Add(stats_row, 0,
                          wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
                          PADDING_MD)

        # ── Log panel ─────────────────────────────────────────────────────────
        log_header_row = wx.BoxSizer(wx.HORIZONTAL)

        log_title = wx.StaticText(content, label="Activity Log")
        log_title.SetFont(make_font(10, bold=True, family=FONT_TITLE))
        log_title.SetForegroundColour(TEXT_PRIMARY)
        log_header_row.Add(log_title, 0, wx.ALIGN_CENTER_VERTICAL)

        log_header_row.AddStretchSpacer()

        clear_btn = wx.Button(content,
                              label="Clear",
                              size=dip_size(content, 60, 24))
        style_button_secondary(clear_btn)
        clear_btn.SetFont(make_font(8))
        log_header_row.Add(clear_btn, 0)

        content_sizer.Add(log_header_row, 0,
                          wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
                          PADDING_MD)

        self.log_panel = LogPanel(content)
        self.log_panel.SetMinSize(dip_size(content, -1, 180))
        content_sizer.Add(self.log_panel, 1,
                          wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
                          PADDING_MD)

        content.SetSizer(content_sizer)
        main_sizer.Add(content, 1, wx.EXPAND)

        self.SetSizer(main_sizer)

        # Store clear button reference
        clear_btn.Bind(wx.EVT_BUTTON, lambda e: self.log_panel.clear())

    def _bind_events(self):
        self.start_btn.Bind(wx.EVT_BUTTON, self.on_start)
        self.stop_btn.Bind(wx.EVT_BUTTON, self.on_stop)
        self.restart_btn.Bind(wx.EVT_BUTTON, self.on_restart)

    def on_start(self, event):
        self.controller.start_server()

    def on_stop(self, event):
        self.controller.stop_server()

    def on_restart(self, event):
        self.controller.restart_server()

    def set_running(self, running: bool, config=None):
        """Update UI state based on server running status"""
        self.start_btn.Enable(not running)
        self.stop_btn.Enable(running)
        self.restart_btn.Enable(running)

        if running:
            self.status_badge.set_status("running", "RUNNING")
            if config:
                host = config.settings.host
                display_host = "localhost" if host == "0.0.0.0" else host
                port = config.settings.port
                self.addr_label.SetLabel(f"{host}:{port}")
                self.endpoint_label.SetLabel(
                    f"http://{display_host}:{port}/v1")
                self.endpoint_label.SetForegroundColour(ACCENT)
        else:
            self.status_badge.set_status("stopped", "STOPPED")
            self.addr_label.SetLabel("—")
            self.endpoint_label.SetLabel("Not running")
            self.endpoint_label.SetForegroundColour(TEXT_MUTED)

        self.Layout()

    def update_stats(self, channels: int, tokens: int, models: int):
        """Update the quick stats display"""
        self.channels_label.SetLabel(str(channels))
        self.tokens_label.SetLabel(str(tokens))
        self.stat_channels.SetLabel(str(channels))
        self.stat_tokens.SetLabel(str(tokens))
        self.stat_models.SetLabel(str(models))

    def log(self, text: str, level: str = "info"):
        """Add a log entry"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")

        color_map = {
            "info": TEXT_PRIMARY,
            "success": SUCCESS,
            "warning": WARNING,
            "error": ERROR,
            "debug": TEXT_MUTED,
        }
        color = color_map.get(level, TEXT_PRIMARY)

        prefix_map = {
            "info": "  ",
            "success": "✓ ",
            "warning": "⚠ ",
            "error": "✗ ",
            "debug": "· ",
        }
        prefix = prefix_map.get(level, "  ")

        self.log_panel.append(f"[{timestamp}] {prefix}{text}", color)
