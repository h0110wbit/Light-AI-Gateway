"""
Channels management panel
"""
import wx
import wx.lib.scrolledpanel as scrolled
from src.gui.theme import *
from src.gui.widgets import *
from src.models.config import ChannelConfig

CHANNEL_TYPES = ["openai", "anthropic", "gemini", "ollama", "custom"]
DEFAULT_URLS = {
    "openai": "https://api.openai.com",
    "anthropic": "https://api.anthropic.com",
    "gemini": "https://generativelanguage.googleapis.com",
    "ollama": "http://localhost:11434",
    "custom": "https://api.example.com",
}


class ChannelDialog(wx.Dialog):
    """Dialog for adding/editing a channel"""

    def __init__(self, parent, channel: ChannelConfig = None):
        title = "Edit Channel" if channel else "Add Channel"
        super().__init__(parent,
                         title=title,
                         size=(520, 560),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.channel = channel
        self.SetBackgroundColour(BG_PANEL)
        self._build_ui()
        if channel:
            self._load_channel(channel)
        self.Centre()

    def _build_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Title
        title_lbl = wx.StaticText(self, label=self.GetTitle())
        title_lbl.SetFont(make_font(13, bold=True, family=FONT_TITLE))
        title_lbl.SetForegroundColour(TEXT_PRIMARY)
        sizer.Add(title_lbl, 0, wx.ALL, PADDING_LG)
        sizer.Add(Divider(self), 0, wx.EXPAND)

        # Scroll area for form
        scroll = scrolled.ScrolledPanel(self)
        scroll.SetBackgroundColour(BG_PANEL)
        form = wx.BoxSizer(wx.VERTICAL)

        # Name
        self.name_input = LabeledInput(scroll, "Channel Name *",
                                       "My API Channel")
        form.Add(self.name_input, 0, wx.EXPAND | wx.ALL, PADDING_MD)

        # Type
        type_panel = wx.Panel(scroll)
        type_panel.SetBackgroundColour(BG_PANEL)
        type_sizer = wx.BoxSizer(wx.VERTICAL)

        type_lbl = wx.StaticText(type_panel, label="PROVIDER TYPE *")
        type_lbl.SetFont(make_font(8, bold=True))
        type_lbl.SetForegroundColour(TEXT_SECONDARY)
        type_sizer.Add(type_lbl, 0, wx.BOTTOM, 4)

        self.type_choice = wx.Choice(
            type_panel, choices=[t.upper() for t in CHANNEL_TYPES])
        self.type_choice.SetSelection(0)
        self.type_choice.SetFont(make_font(9))
        self.type_choice.SetBackgroundColour(BG_INPUT)
        self.type_choice.SetForegroundColour(TEXT_PRIMARY)
        self.type_choice.SetMinSize((-1, 30))
        type_sizer.Add(self.type_choice, 0, wx.EXPAND)

        type_panel.SetSizer(type_sizer)
        form.Add(type_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
                 PADDING_MD)

        # Base URL
        self.url_input = LabeledInput(scroll, "Base URL *",
                                      DEFAULT_URLS["openai"])
        form.Add(self.url_input, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
                 PADDING_MD)

        # API Key
        self.key_input = LabeledInput(scroll, "API Key", "", password=True)
        form.Add(self.key_input, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
                 PADDING_MD)

        # Models (comma-separated)
        self.models_input = LabeledInput(
            scroll, "Supported Models (comma-separated, leave empty for all)",
            "gpt-4o, gpt-4o-mini")
        form.Add(self.models_input, 0,
                 wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, PADDING_MD)

        # Priority and Timeout row
        row_panel = wx.Panel(scroll)
        row_panel.SetBackgroundColour(BG_PANEL)
        row_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Priority
        prio_panel = wx.Panel(row_panel)
        prio_panel.SetBackgroundColour(BG_PANEL)
        prio_sizer = wx.BoxSizer(wx.VERTICAL)

        prio_lbl = wx.StaticText(prio_panel, label="PRIORITY (1=highest)")
        prio_lbl.SetFont(make_font(8, bold=True))
        prio_lbl.SetForegroundColour(TEXT_SECONDARY)
        prio_sizer.Add(prio_lbl, 0, wx.BOTTOM, 4)

        self.priority_spin = wx.SpinCtrl(prio_panel, value="1", min=1, max=100)
        self.priority_spin.SetBackgroundColour(BG_INPUT)
        self.priority_spin.SetForegroundColour(TEXT_PRIMARY)
        self.priority_spin.SetMinSize((-1, 30))
        prio_sizer.Add(self.priority_spin, 0, wx.EXPAND)

        prio_panel.SetSizer(prio_sizer)
        row_sizer.Add(prio_panel, 1, wx.EXPAND | wx.RIGHT, PADDING_MD)

        # Timeout
        timeout_panel = wx.Panel(row_panel)
        timeout_panel.SetBackgroundColour(BG_PANEL)
        timeout_sizer = wx.BoxSizer(wx.VERTICAL)

        timeout_lbl = wx.StaticText(timeout_panel, label="TIMEOUT (seconds)")
        timeout_lbl.SetFont(make_font(8, bold=True))
        timeout_lbl.SetForegroundColour(TEXT_SECONDARY)
        timeout_sizer.Add(timeout_lbl, 0, wx.BOTTOM, 4)

        self.timeout_spin = wx.SpinCtrl(timeout_panel,
                                        value="60",
                                        min=5,
                                        max=600)
        self.timeout_spin.SetBackgroundColour(BG_INPUT)
        self.timeout_spin.SetForegroundColour(TEXT_PRIMARY)
        self.timeout_spin.SetMinSize((-1, 30))
        timeout_sizer.Add(self.timeout_spin, 0, wx.EXPAND)

        timeout_panel.SetSizer(timeout_sizer)
        row_sizer.Add(timeout_panel, 1, wx.EXPAND)

        row_panel.SetSizer(row_sizer)
        form.Add(row_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
                 PADDING_MD)

        # Enabled toggle
        self.enabled_check = wx.CheckBox(scroll, label="Channel Enabled")
        self.enabled_check.SetValue(True)
        self.enabled_check.SetFont(make_font(9))
        self.enabled_check.SetForegroundColour(TEXT_PRIMARY)
        self.enabled_check.SetBackgroundColour(BG_PANEL)
        form.Add(self.enabled_check, 0, wx.ALL, PADDING_MD)

        scroll.SetSizer(form)
        scroll.SetupScrolling()
        sizer.Add(scroll, 1, wx.EXPAND)

        # Update URL on type change
        self.type_choice.Bind(wx.EVT_CHOICE, self._on_type_change)

        # Buttons
        sizer.Add(Divider(self), 0, wx.EXPAND | wx.TOP, PADDING_MD)

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        btn_row.AddStretchSpacer()

        cancel_btn = wx.Button(self, wx.ID_CANCEL, "Cancel", size=(80, 32))
        style_button_secondary(cancel_btn)
        btn_row.Add(cancel_btn, 0, wx.RIGHT, PADDING_SM)

        self.save_btn = wx.Button(self,
                                  wx.ID_OK,
                                  "Save Channel",
                                  size=(120, 32))
        style_button_primary(self.save_btn)
        btn_row.Add(self.save_btn, 0)

        sizer.Add(btn_row, 0, wx.ALL, PADDING_MD)

        self.SetSizer(sizer)
        self.save_btn.Bind(wx.EVT_BUTTON, self._on_save)

    def _on_type_change(self, event):
        sel = self.type_choice.GetSelection()
        if sel >= 0:
            type_key = CHANNEL_TYPES[sel]
            current_url = self.url_input.GetValue()
            if not current_url or current_url in DEFAULT_URLS.values():
                self.url_input.SetValue(DEFAULT_URLS.get(type_key, ""))

    def _load_channel(self, ch: ChannelConfig):
        self.name_input.SetValue(ch.name)
        try:
            idx = CHANNEL_TYPES.index(ch.type.lower())
            self.type_choice.SetSelection(idx)
        except ValueError:
            self.type_choice.SetSelection(len(CHANNEL_TYPES) - 1)
        self.url_input.SetValue(ch.base_url)
        self.key_input.SetValue(ch.api_key)
        self.models_input.SetValue(", ".join(ch.models))
        self.priority_spin.SetValue(ch.priority)
        self.timeout_spin.SetValue(ch.timeout)
        self.enabled_check.SetValue(ch.enabled)

    def _on_save(self, event):
        if not self.name_input.GetValue().strip():
            wx.MessageBox("Channel name is required", "Validation Error",
                          wx.OK | wx.ICON_WARNING)
            return
        if not self.url_input.GetValue().strip():
            wx.MessageBox("Base URL is required", "Validation Error",
                          wx.OK | wx.ICON_WARNING)
            return
        self.EndModal(wx.ID_OK)

    def get_channel_data(self) -> dict:
        models_str = self.models_input.GetValue().strip()
        models = [m.strip() for m in models_str.split(",")
                  if m.strip()] if models_str else []

        return {
            "name": self.name_input.GetValue().strip(),
            "type": CHANNEL_TYPES[self.type_choice.GetSelection()],
            "base_url": self.url_input.GetValue().strip(),
            "api_key": self.key_input.GetValue(),
            "models": models,
            "priority": self.priority_spin.GetValue(),
            "timeout": self.timeout_spin.GetValue(),
            "enabled": self.enabled_check.GetValue(),
        }


class ChannelRow(wx.Panel):
    """A row representing a single channel"""

    def __init__(self, parent, channel: ChannelConfig, on_edit, on_delete,
                 on_toggle):
        super().__init__(parent)
        self.channel = channel
        self.on_edit_cb = on_edit
        self.on_delete_cb = on_delete
        self.on_toggle_cb = on_toggle

        self.SetBackgroundColour(BG_CARD)
        self._build_ui()

    def _build_ui(self):
        sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Status indicator (clickable for toggle)
        self.status_dot = wx.Panel(self, size=(8, 8))
        self._update_status_color()
        sizer.Add(self.status_dot, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
                  PADDING_MD)

        # Info
        info_sizer = wx.BoxSizer(wx.VERTICAL)

        name_row = wx.BoxSizer(wx.HORIZONTAL)
        name_lbl = wx.StaticText(self, label=self.channel.name)
        name_lbl.SetFont(make_font(10, bold=True))
        name_lbl.SetForegroundColour(TEXT_PRIMARY)
        name_row.Add(name_lbl, 0, wx.RIGHT, PADDING_SM)

        type_badge = wx.StaticText(self,
                                   label=f"[{self.channel.type.upper()}]")
        type_badge.SetFont(make_font(8))
        type_badge.SetForegroundColour(ACCENT_DIM)
        name_row.Add(type_badge, 0, wx.ALIGN_CENTER_VERTICAL)

        info_sizer.Add(name_row, 0)

        url_lbl = wx.StaticText(self, label=self.channel.base_url)
        url_lbl.SetFont(make_font(8, family=FONT_MONO))
        url_lbl.SetForegroundColour(TEXT_SECONDARY)
        info_sizer.Add(url_lbl, 0, wx.TOP, 2)

        models_str = ", ".join(
            self.channel.models[:3]) if self.channel.models else "All models"
        if len(self.channel.models) > 3:
            models_str += f" +{len(self.channel.models) - 3} more"
        models_lbl = wx.StaticText(self, label=f"Models: {models_str}")
        models_lbl.SetFont(make_font(8))
        models_lbl.SetForegroundColour(TEXT_MUTED)
        info_sizer.Add(models_lbl, 0, wx.TOP, 1)

        sizer.Add(info_sizer, 1, wx.EXPAND | wx.ALL, PADDING_MD)

        # Priority badge
        prio_lbl = wx.StaticText(self, label=f"P{self.channel.priority}")
        prio_lbl.SetFont(make_font(8, bold=True))
        prio_lbl.SetForegroundColour(TEXT_SECONDARY)
        sizer.Add(prio_lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, PADDING_MD)

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Toggle button
        toggle_label = "ON" if self.channel.enabled else "OFF"
        toggle_color = wx.Colour(
            30, 80, 50) if self.channel.enabled else wx.Colour(60, 50, 40)
        toggle_fg = SUCCESS if self.channel.enabled else TEXT_MUTED
        self.toggle_btn = wx.Button(self, label=toggle_label, size=(40, 26))
        self.toggle_btn.SetBackgroundColour(toggle_color)
        self.toggle_btn.SetForegroundColour(toggle_fg)
        self.toggle_btn.SetFont(make_font(8, bold=True))
        btn_sizer.Add(self.toggle_btn, 0, wx.RIGHT, 4)

        edit_btn = wx.Button(self, label="Edit", size=(50, 26))
        edit_btn.SetBackgroundColour(BG_INPUT)
        edit_btn.SetForegroundColour(TEXT_PRIMARY)
        edit_btn.SetFont(make_font(8))
        btn_sizer.Add(edit_btn, 0, wx.RIGHT, 4)

        del_btn = wx.Button(self, label="Del", size=(40, 26))
        del_btn.SetBackgroundColour(wx.Colour(80, 30, 30))
        del_btn.SetForegroundColour(ERROR)
        del_btn.SetFont(make_font(8))
        btn_sizer.Add(del_btn, 0)

        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
                  PADDING_MD)

        self.SetSizer(sizer)

        # Bind events
        self.toggle_btn.Bind(wx.EVT_BUTTON, self._on_toggle)
        edit_btn.Bind(wx.EVT_BUTTON, lambda e: self.on_edit_cb(self.channel))
        del_btn.Bind(wx.EVT_BUTTON, lambda e: self.on_delete_cb(self.channel))

    def _update_status_color(self):
        """Update the status dot color based on enabled state"""
        status_color = ACCENT if self.channel.enabled else TEXT_MUTED
        self.status_dot.SetBackgroundColour(status_color)

    def _update_toggle_button(self):
        """Update the toggle button appearance"""
        if self.channel.enabled:
            self.toggle_btn.SetLabel("ON")
            self.toggle_btn.SetBackgroundColour(wx.Colour(30, 80, 50))
            self.toggle_btn.SetForegroundColour(SUCCESS)
        else:
            self.toggle_btn.SetLabel("OFF")
            self.toggle_btn.SetBackgroundColour(wx.Colour(60, 50, 40))
            self.toggle_btn.SetForegroundColour(TEXT_MUTED)

    def _on_toggle(self, event):
        """Handle toggle button click"""
        if self.on_toggle_cb:
            self.on_toggle_cb(self.channel)

    def update_channel(self, channel: ChannelConfig):
        """Update the channel data and refresh UI"""
        self.channel = channel
        self._update_status_color()
        self._update_toggle_button()


class ChannelsPanel(wx.Panel):
    """Channel management panel"""

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.SetBackgroundColour(BG_PANEL)
        self._build_ui()

    def _build_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Header
        header_row = wx.BoxSizer(wx.HORIZONTAL)

        header = SectionHeader(self, "Channels",
                               "Configure upstream AI provider connections")
        header_row.Add(header, 1, wx.EXPAND)

        add_btn = wx.Button(self, label="＋  Add Channel", size=(130, 34))
        style_button_primary(add_btn)
        header_row.Add(add_btn, 0, wx.ALIGN_CENTER_VERTICAL)

        sizer.Add(header_row, 0, wx.EXPAND | wx.ALL, PADDING_LG)
        sizer.Add(Divider(self), 0, wx.EXPAND)

        # Channels list (scrollable)
        self.scroll = scrolled.ScrolledPanel(self)
        self.scroll.SetBackgroundColour(BG_PANEL)
        self.list_sizer = wx.BoxSizer(wx.VERTICAL)

        self.empty_label = wx.StaticText(
            self.scroll,
            label=
            "No channels configured.\nClick '+ Add Channel' to add your first upstream provider."
        )
        self.empty_label.SetFont(make_font(10))
        self.empty_label.SetForegroundColour(TEXT_MUTED)
        self.empty_label.SetBackgroundColour(BG_PANEL)
        self.list_sizer.Add(self.empty_label, 0, wx.ALL, PADDING_XL)

        self.scroll.SetSizer(self.list_sizer)
        self.scroll.SetupScrolling()
        sizer.Add(self.scroll, 1, wx.EXPAND)

        self.SetSizer(sizer)

        add_btn.Bind(wx.EVT_BUTTON, self.on_add)

        # Initial load
        self.refresh()

    def refresh(self):
        """Refresh the channel list from config"""
        config = self.controller.get_config()
        self._render_channels(config.channels)
        self.Layout()

    def _render_channels(self, channels):
        # Clear existing rows (except empty label)
        for child in list(self.scroll.GetChildren()):
            if isinstance(child, ChannelRow):
                child.Destroy()
        self.list_sizer.Clear(False)

        if not channels:
            self.empty_label.Show()
            self.list_sizer.Add(self.empty_label, 0, wx.ALL, PADDING_XL)
        else:
            self.empty_label.Hide()
            for i, ch in enumerate(channels):
                row = ChannelRow(
                    self.scroll,
                    ch,
                    on_edit=self.on_edit,
                    on_delete=self.on_delete,
                    on_toggle=self.on_toggle,
                )
                if i > 0:
                    self.list_sizer.Add(Divider(self.scroll), 0, wx.EXPAND)
                self.list_sizer.Add(row, 0, wx.EXPAND)

        self.scroll.SetupScrolling()
        self.scroll.Layout()

    def on_add(self, event):
        dlg = ChannelDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            data = dlg.get_channel_data()
            self.controller.add_channel(data)
            self.refresh()
        dlg.Destroy()

    def on_edit(self, channel: ChannelConfig):
        dlg = ChannelDialog(self, channel)
        if dlg.ShowModal() == wx.ID_OK:
            data = dlg.get_channel_data()
            self.controller.update_channel(channel.id, data)
            self.refresh()
        dlg.Destroy()

    def on_delete(self, channel: ChannelConfig):
        result = wx.MessageBox(f"Delete channel '{channel.name}'?",
                               "Confirm Delete",
                               wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
                               self)
        if result == wx.YES:
            self.controller.delete_channel(channel.id)
            self.refresh()

    def on_toggle(self, channel: ChannelConfig):
        """Toggle channel enabled state"""
        self.controller.toggle_channel(channel.id)
        self.refresh()
