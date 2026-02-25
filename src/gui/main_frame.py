"""
Main application window for AI Gateway
Features a sidebar navigation with multiple panels
"""
import wx
import wx.lib.scrolledpanel as scrolled
from src.gui.theme import *
from src.gui.widgets import *
from src.gui.controller import GatewayController
from src.gui.panels.dashboard import DashboardPanel
from src.gui.panels.channels import ChannelsPanel
from src.gui.panels.tokens import TokensPanel
from src.gui.panels.settings import SettingsPanel
from src.gui.tray import SystemTrayIcon, get_icon_path
import os


def dip(window: wx.Window, size: int) -> int:
    """将逻辑尺寸转换为物理像素尺寸（DPI感知）。"""
    try:
        return window.FromDIP(size)
    except AttributeError:
        return size


def dip_size(window: wx.Window, width: int, height: int) -> tuple:
    """将逻辑尺寸元组转换为物理像素尺寸（DPI感知）。"""
    return (dip(window, width), dip(window, height))


NAV_ITEMS = [
    ("🏠", "Dashboard", "dashboard"),
    ("⟳", "Channels", "channels"),
    ("🔑", "Tokens", "tokens"),
    ("⚙", "Settings", "settings"),
]


class NavButton(wx.Panel):
    """Sidebar navigation button"""

    def __init__(self, parent, icon: str, label: str, key: str, on_click):
        super().__init__(parent, size=dip_size(parent, -1, 52))
        self.key = key
        self.label = label
        self.icon = icon
        self.on_click_cb = on_click
        self._selected = False
        self._hover = False

        self.SetBackgroundColour(BG_DARK)
        self.SetMinSize(dip_size(self, -1, 52))

        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_click)
        self.Bind(wx.EVT_ENTER_WINDOW, lambda e: self._set_hover(True))
        self.Bind(wx.EVT_LEAVE_WINDOW, lambda e: self._set_hover(False))

    def _set_hover(self, val: bool):
        self._hover = val
        self.Refresh()

    def set_selected(self, val: bool):
        self._selected = val
        self.Refresh()

    def _on_click(self, event):
        self.on_click_cb(self.key)

    def _on_paint(self, event):
        dc = wx.PaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        if not gc:
            return

        w, h = self.GetSize()
        accent_width = dip(self, 3)
        icon_x = dip(self, 16)
        label_x = dip(self, 44)

        # Background
        if self._selected:
            bg = BG_PANEL
            # Left accent bar
            gc.SetBrush(gc.CreateBrush(wx.Brush(ACCENT)))
            gc.SetPen(gc.CreatePen(wx.Pen(wx.TRANSPARENT_PEN)))
            gc.DrawRectangle(0, 0, accent_width, h)
        elif self._hover:
            bg = BG_CARD
        else:
            bg = BG_DARK

        gc.SetBrush(gc.CreateBrush(wx.Brush(bg)))
        gc.SetPen(gc.CreatePen(wx.Pen(wx.TRANSPARENT_PEN)))
        gc.DrawRectangle(accent_width if self._selected else 0, 0, w, h)

        # Icon
        icon_color = ACCENT if self._selected else (
            TEXT_PRIMARY if self._hover else TEXT_SECONDARY)
        gc.SetFont(gc.CreateFont(make_font(16), icon_color))
        iw, ih = gc.GetTextExtent(self.icon)
        gc.DrawText(self.icon, icon_x, (h - ih) / 2)

        # Label
        label_color = TEXT_PRIMARY if self._selected else TEXT_SECONDARY
        gc.SetFont(
            gc.CreateFont(make_font(9, bold=self._selected), label_color))
        lw, lh = gc.GetTextExtent(self.label)
        gc.DrawText(self.label, label_x, (h - lh) / 2)


class Sidebar(wx.Panel):
    """Left sidebar with logo and navigation"""

    def __init__(self, parent, on_navigate):
        super().__init__(parent, size=dip_size(parent, 180, -1))
        self.SetBackgroundColour(BG_DARK)
        self.SetMinSize(dip_size(self, 180, -1))
        self.on_navigate = on_navigate
        self._nav_buttons = {}
        self._build_ui()

    def _build_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Logo area
        logo_panel = wx.Panel(self)
        logo_panel.SetBackgroundColour(BG_DARK)
        logo_sizer = wx.BoxSizer(wx.VERTICAL)

        icon_path = get_icon_path()
        if os.path.exists(icon_path):
            img = wx.Image(icon_path, wx.BITMAP_TYPE_ICO)
            if img.IsOk():
                icon_size = dip(self, 32)
                img = img.Scale(icon_size, icon_size, wx.IMAGE_QUALITY_HIGH)
                logo_bmp = wx.StaticBitmap(logo_panel,
                                           bitmap=img.ConvertToBitmap())
                logo_sizer.Add(logo_bmp, 0,
                               wx.TOP | wx.ALIGN_CENTER_HORIZONTAL, PADDING_LG)
            else:
                logo_lbl = wx.StaticText(logo_panel, label="⊕")
                logo_lbl.SetFont(make_font(28, family=FONT_TITLE))
                logo_lbl.SetForegroundColour(ACCENT)
                logo_sizer.Add(logo_lbl, 0,
                               wx.TOP | wx.ALIGN_CENTER_HORIZONTAL, PADDING_LG)
        else:
            logo_lbl = wx.StaticText(logo_panel, label="⊕")
            logo_lbl.SetFont(make_font(28, family=FONT_TITLE))
            logo_lbl.SetForegroundColour(ACCENT)
            logo_sizer.Add(logo_lbl, 0, wx.TOP | wx.ALIGN_CENTER_HORIZONTAL,
                           PADDING_LG)

        app_lbl = wx.StaticText(logo_panel, label="AI Gateway")
        app_lbl.SetFont(make_font(11, bold=True, family=FONT_TITLE))
        app_lbl.SetForegroundColour(TEXT_PRIMARY)
        logo_sizer.Add(app_lbl, 0, wx.ALIGN_CENTER_HORIZONTAL)

        tagline = wx.StaticText(logo_panel, label="Personal LLM Proxy")
        tagline.SetFont(make_font(7))
        tagline.SetForegroundColour(TEXT_MUTED)
        logo_sizer.Add(tagline, 0, wx.BOTTOM | wx.ALIGN_CENTER_HORIZONTAL,
                       PADDING_LG)

        logo_panel.SetSizer(logo_sizer)
        sizer.Add(logo_panel, 0, wx.EXPAND)

        # Separator
        sep = wx.Panel(self, size=dip_size(self, -1, 1))
        sep.SetBackgroundColour(BORDER)
        sizer.Add(sep, 0, wx.EXPAND)

        sizer.AddSpacer(PADDING_SM)

        # Nav items
        for icon, label, key in NAV_ITEMS:
            btn = NavButton(self, icon, label, key, self._on_nav_click)
            self._nav_buttons[key] = btn
            sizer.Add(btn, 0, wx.EXPAND)

        sizer.AddStretchSpacer()

        # Bottom separator + info
        sep2 = wx.Panel(self, size=dip_size(self, -1, 1))
        sep2.SetBackgroundColour(BORDER)
        sizer.Add(sep2, 0, wx.EXPAND)

        # Server status indicator at bottom
        self.server_status = wx.Panel(self)
        self.server_status.SetBackgroundColour(BG_DARK)
        status_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self._status_dot = wx.Panel(self.server_status,
                                    size=dip_size(self, 8, 8))
        self._status_dot.SetBackgroundColour(TEXT_MUTED)
        status_sizer.Add(self._status_dot, 0,
                         wx.ALIGN_CENTER_VERTICAL | wx.LEFT, PADDING_MD)

        self._status_lbl = wx.StaticText(self.server_status, label="Stopped")
        self._status_lbl.SetFont(make_font(8))
        self._status_lbl.SetForegroundColour(TEXT_MUTED)
        status_sizer.Add(self._status_lbl, 0,
                         wx.ALIGN_CENTER_VERTICAL | wx.LEFT, dip(self, 6))

        self.server_status.SetSizer(status_sizer)
        sizer.Add(self.server_status, 0, wx.EXPAND | wx.ALL, PADDING_SM)

        self.SetSizer(sizer)

        # Select first item
        self._select("dashboard")

    def _on_nav_click(self, key: str):
        self._select(key)
        self.on_navigate(key)

    def _select(self, key: str):
        for k, btn in self._nav_buttons.items():
            btn.set_selected(k == key)

    def set_server_status(self, running: bool):
        if running:
            self._status_dot.SetBackgroundColour(SUCCESS)
            self._status_lbl.SetLabel("Running")
            self._status_lbl.SetForegroundColour(SUCCESS)
        else:
            self._status_dot.SetBackgroundColour(TEXT_MUTED)
            self._status_lbl.SetLabel("Stopped")
            self._status_lbl.SetForegroundColour(TEXT_MUTED)
        self.server_status.Layout()


class MainFrame(wx.Frame):
    """Main application window"""

    def __init__(self,
                 parent,
                 title: str,
                 silent: bool = False,
                 auto_start: bool = False):
        super().__init__(
            parent,
            title=title,
            size=(900, 680),
            style=wx.DEFAULT_FRAME_STYLE,
        )

        self.SetBackgroundColour(BG_DARK)
        self.SetMinSize(dip_size(self, 800, 580))

        # Track if we should really close (vs hide to tray)
        self._really_close = False

        # Silent mode flag
        self._silent = silent

        # Initialize controller
        self.controller = GatewayController()

        # Create system tray icon
        self.tray_icon = SystemTrayIcon(self, self.controller)

        self._build_ui()
        self._bind_controller()
        self._update_stats()

        # Sync auto-start state on Windows
        self.controller.sync_auto_start_state()

        self.Centre()

        # Initial log
        self.dashboard.log("AI Gateway initialized", "success")
        self.dashboard.log(
            f"Loaded config: {len(self.controller.get_config().channels)} channels, "
            f"{len(self.controller.get_config().tokens)} tokens", "info")
        self.dashboard.log(
            f"Listening on {self.controller.get_config().settings.host}:{self.controller.get_config().settings.port}",
            "info")

        # Auto-start server if requested (for silent mode)
        if auto_start or silent:
            self.controller.start_server()
            self.dashboard.log("Gateway auto-started", "success")

        if not silent:
            self.dashboard.log("Ready. Click 'Start Gateway' to begin.",
                               "info")

    def _build_ui(self):
        # Main horizontal layout: sidebar + content
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Sidebar
        self.sidebar = Sidebar(self, self._on_navigate)
        main_sizer.Add(self.sidebar, 0, wx.EXPAND)

        # Vertical separator
        vsep = wx.Panel(self, size=dip_size(self, 1, -1))
        vsep.SetBackgroundColour(BORDER)
        main_sizer.Add(vsep, 0, wx.EXPAND)

        # Content panel (switches between panels)
        self.content_container = wx.Panel(self)
        self.content_container.SetBackgroundColour(BG_PANEL)
        self.content_sizer = wx.BoxSizer(wx.VERTICAL)

        # Create all panels
        self.dashboard = DashboardPanel(self.content_container,
                                        self.controller)
        self.channels_panel = ChannelsPanel(self.content_container,
                                            self.controller)
        self.tokens_panel = TokensPanel(self.content_container,
                                        self.controller)
        self.settings_panel = SettingsPanel(self.content_container,
                                            self.controller)

        self.content_sizer.Add(self.dashboard, 1, wx.EXPAND)
        self.content_sizer.Add(self.channels_panel, 1, wx.EXPAND)
        self.content_sizer.Add(self.tokens_panel, 1, wx.EXPAND)
        self.content_sizer.Add(self.settings_panel, 1, wx.EXPAND)

        self.content_container.SetSizer(self.content_sizer)
        main_sizer.Add(self.content_container, 1, wx.EXPAND)

        self.SetSizer(main_sizer)

        # Show only dashboard initially
        self._show_panel("dashboard")

        # Initialize high availability toggle state
        self.dashboard.init_ha_state()

        # Bind close event
        self.Bind(wx.EVT_CLOSE, self.OnClose)

    def _bind_controller(self):
        """Bind controller callbacks"""
        self.controller.on_status_changed(self._on_status_changed)
        self.controller.on_config_changed(self._on_config_changed)
        self.controller.on_log_message(self._on_log_message)

    def _on_navigate(self, key: str):
        """Handle sidebar navigation"""
        self._show_panel(key)
        # Refresh the target panel
        if key == "channels":
            self.channels_panel.refresh()
        elif key == "tokens":
            self.tokens_panel.refresh()
        elif key == "settings":
            self.settings_panel.refresh()
        elif key == "dashboard":
            self._update_stats()

    def _show_panel(self, key: str):
        """Show the panel for the given key, hide others"""
        panel_map = {
            "dashboard": self.dashboard,
            "channels": self.channels_panel,
            "tokens": self.tokens_panel,
            "settings": self.settings_panel,
        }

        # Freeze to prevent flickering during panel switch
        self.content_container.Freeze()
        try:
            for k, panel in panel_map.items():
                panel.Show(k == key)
            self.content_container.Layout()

            # Force refresh of the visible panel to prevent rendering artifacts
            visible_panel = panel_map.get(key)
            if visible_panel:
                visible_panel.Refresh()
                # For scrolled panels, also refresh the scroll window
                if hasattr(visible_panel, 'scroll') and visible_panel.scroll:
                    visible_panel.scroll.Refresh()
                    visible_panel.scroll.SetupScrolling()
        finally:
            self.content_container.Thaw()

    def _on_status_changed(self, status: str):
        """Handle server status changes"""
        running = (status == "started")
        not_running = (status == "stopped")

        if running:
            self.dashboard.set_running(True, self.controller.get_config())
            self.sidebar.set_server_status(True)
        elif not_running:
            self.dashboard.set_running(False)
            self.sidebar.set_server_status(False)

        # Update tray icon status
        self.tray_icon.update_icon_status(running)

    def _on_config_changed(self, config):
        """Handle configuration changes"""
        self._update_stats()
        # Refresh panels that depend on config
        self.channels_panel.refresh()
        self.tokens_panel.refresh()

    def _on_log_message(self, message: str, level: str = "info"):
        """Handle log messages from controller"""
        self.dashboard.log(message, level)

    def _update_stats(self):
        """Update dashboard stats"""
        stats = self.controller.get_stats()
        self.dashboard.update_stats(stats["channels"], stats["tokens"],
                                    stats["models"])

    def OnClose(self, event):
        """Handle window close - minimize to tray instead of closing"""
        if self._really_close:
            # Really close the application
            if self.controller.is_running():
                self.controller.stop_server()
            self.tray_icon.RemoveIcon()
            self.tray_icon.Destroy()
            event.Skip()
        else:
            # Hide to tray
            self.Hide()

    def ShowWindow(self):
        """Show and raise the window"""
        self.Show()
        self.Raise()
        self.Iconize(False)
