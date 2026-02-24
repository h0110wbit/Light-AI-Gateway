"""
Token management panel
"""
import wx
import wx.lib.scrolledpanel as scrolled
import secrets
import string
from src.gui.theme import *
from src.gui.widgets import *
from src.models.config import TokenConfig


def dip(window: wx.Window, size: int) -> int:
    """将逻辑尺寸转换为物理像素尺寸（DPI感知）。"""
    try:
        return window.FromDIP(size)
    except AttributeError:
        return size


def dip_size(window: wx.Window, width: int, height: int) -> tuple:
    """将逻辑尺寸元组转换为物理像素尺寸（DPI感知）。"""
    return (dip(window, width), dip(window, height))


def generate_token(prefix: str = "sk-gw") -> str:
    """Generate a random API token"""
    chars = string.ascii_letters + string.digits
    random_part = ''.join(secrets.choice(chars) for _ in range(48))
    return f"{prefix}-{random_part}"


class TokenDialog(wx.Dialog):
    """Dialog for adding/editing a token"""

    def __init__(self, parent, token: TokenConfig = None, channels=None):
        title = "Edit Token" if token else "Create Token"
        super().__init__(parent,
                         title=title,
                         size=dip_size(parent, 500, 480),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.token = token
        self.channels = channels or []
        self.SetBackgroundColour(BG_PANEL)
        self._build_ui()
        if token:
            self._load_token(token)
        self.Centre()

    def _build_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        title_lbl = wx.StaticText(self, label=self.GetTitle())
        title_lbl.SetFont(make_font(13, bold=True, family=FONT_TITLE))
        title_lbl.SetForegroundColour(TEXT_PRIMARY)
        sizer.Add(title_lbl, 0, wx.ALL, PADDING_LG)
        sizer.Add(Divider(self), 0, wx.EXPAND)

        scroll = scrolled.ScrolledPanel(self)
        scroll.SetBackgroundColour(BG_PANEL)
        form = wx.BoxSizer(wx.VERTICAL)

        # Name
        self.name_input = LabeledInput(scroll, "Token Name *",
                                       "My Access Token")
        form.Add(self.name_input, 0, wx.EXPAND | wx.ALL, PADDING_MD)

        # Key
        key_panel = wx.Panel(scroll)
        key_panel.SetBackgroundColour(BG_PANEL)
        key_sizer = wx.BoxSizer(wx.VERTICAL)

        key_lbl = wx.StaticText(key_panel, label="TOKEN KEY *")
        key_lbl.SetFont(make_font(8, bold=True))
        key_lbl.SetForegroundColour(TEXT_SECONDARY)
        key_sizer.Add(key_lbl, 0, wx.BOTTOM, 4)

        key_row = wx.BoxSizer(wx.HORIZONTAL)
        self.key_ctrl = wx.TextCtrl(key_panel, value=generate_token())
        style_text_ctrl(self.key_ctrl)
        key_row.Add(self.key_ctrl, 1, wx.EXPAND | wx.RIGHT, PADDING_SM)

        gen_btn = wx.Button(key_panel,
                            label="↺ Generate",
                            size=dip_size(key_panel, 90, 30))
        gen_btn.SetBackgroundColour(BG_INPUT)
        gen_btn.SetForegroundColour(ACCENT)
        gen_btn.SetFont(make_font(8))
        key_row.Add(gen_btn, 0)

        key_sizer.Add(key_row, 0, wx.EXPAND)
        key_panel.SetSizer(key_sizer)
        form.Add(key_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
                 PADDING_MD)

        # Allowed models
        models_panel = wx.Panel(scroll)
        models_panel.SetBackgroundColour(BG_PANEL)
        models_sizer = wx.BoxSizer(wx.VERTICAL)

        models_lbl = wx.StaticText(
            models_panel,
            label="ALLOWED MODELS (comma-separated, empty = all)")
        models_lbl.SetFont(make_font(8, bold=True))
        models_lbl.SetForegroundColour(TEXT_SECONDARY)
        models_sizer.Add(models_lbl, 0, wx.BOTTOM, 4)

        self.models_ctrl = wx.TextCtrl(models_panel)
        style_text_ctrl(self.models_ctrl)
        models_sizer.Add(self.models_ctrl, 0, wx.EXPAND)

        hint = wx.StaticText(models_panel,
                             label="Leave empty to allow all models")
        hint.SetFont(make_font(8))
        hint.SetForegroundColour(TEXT_MUTED)
        models_sizer.Add(hint, 0, wx.TOP, 3)

        models_panel.SetSizer(models_sizer)
        form.Add(models_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
                 PADDING_MD)

        # Enabled
        self.enabled_check = wx.CheckBox(scroll, label="Token Enabled")
        self.enabled_check.SetValue(True)
        self.enabled_check.SetFont(make_font(9))
        self.enabled_check.SetForegroundColour(TEXT_PRIMARY)
        self.enabled_check.SetBackgroundColour(BG_PANEL)
        form.Add(self.enabled_check, 0, wx.ALL, PADDING_MD)

        scroll.SetSizer(form)
        scroll.SetupScrolling()
        sizer.Add(scroll, 1, wx.EXPAND)

        sizer.Add(Divider(self), 0, wx.EXPAND | wx.TOP, PADDING_MD)

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        btn_row.AddStretchSpacer()

        cancel_btn = wx.Button(self,
                               wx.ID_CANCEL,
                               "Cancel",
                               size=dip_size(self, 80, 32))
        style_button_secondary(cancel_btn)
        btn_row.Add(cancel_btn, 0, wx.RIGHT, PADDING_SM)

        save_btn = wx.Button(self,
                             wx.ID_OK,
                             "Save Token",
                             size=dip_size(self, 120, 32))
        style_button_primary(save_btn)
        btn_row.Add(save_btn, 0)

        sizer.Add(btn_row, 0, wx.ALL, PADDING_MD)

        self.SetSizer(sizer)

        gen_btn.Bind(wx.EVT_BUTTON,
                     lambda e: self.key_ctrl.SetValue(generate_token()))
        save_btn.Bind(wx.EVT_BUTTON, self._on_save)

    def _load_token(self, token: TokenConfig):
        self.name_input.SetValue(token.name)
        self.key_ctrl.SetValue(token.key)
        self.models_ctrl.SetValue(", ".join(token.allowed_models))
        self.enabled_check.SetValue(token.enabled)

    def _on_save(self, event):
        if not self.name_input.GetValue().strip():
            wx.MessageBox("Token name is required", "Validation Error",
                          wx.OK | wx.ICON_WARNING)
            return
        if not self.key_ctrl.GetValue().strip():
            wx.MessageBox("Token key is required", "Validation Error",
                          wx.OK | wx.ICON_WARNING)
            return
        self.EndModal(wx.ID_OK)

    def get_token_data(self) -> dict:
        models_str = self.models_ctrl.GetValue().strip()
        models = [m.strip() for m in models_str.split(",")
                  if m.strip()] if models_str else []

        return {
            "name": self.name_input.GetValue().strip(),
            "key": self.key_ctrl.GetValue().strip(),
            "allowed_models": models,
            "enabled": self.enabled_check.GetValue(),
        }


class TokenRow(wx.Panel):
    """A row representing a single token"""

    def __init__(self, parent, token: TokenConfig, on_edit, on_delete,
                 on_copy):
        super().__init__(parent)
        self.token = token
        self.on_edit_cb = on_edit
        self.on_delete_cb = on_delete
        self.on_copy_cb = on_copy

        self.SetBackgroundColour(BG_CARD)
        self._build_ui()

    def _build_ui(self):
        sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Status dot
        status_color = SUCCESS if self.token.enabled else TEXT_MUTED
        dot = wx.Panel(self, size=dip_size(self, 8, 8))
        dot.SetBackgroundColour(status_color)
        sizer.Add(dot, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, PADDING_MD)

        # Info
        info_sizer = wx.BoxSizer(wx.VERTICAL)

        name_lbl = wx.StaticText(self, label=self.token.name)
        name_lbl.SetFont(make_font(10, bold=True))
        name_lbl.SetForegroundColour(TEXT_PRIMARY)
        info_sizer.Add(name_lbl, 0)

        # Masked key
        key = self.token.key
        masked = key[:8] + "•" * 12 + key[-4:] if len(
            key) > 20 else "•" * len(key)
        key_lbl = wx.StaticText(self, label=masked)
        key_lbl.SetFont(make_font(8, family=FONT_MONO))
        key_lbl.SetForegroundColour(TEXT_SECONDARY)
        info_sizer.Add(key_lbl, 0, wx.TOP, 2)

        models = self.token.allowed_models
        models_str = ", ".join(models[:3]) if models else "All models"
        if len(models) > 3:
            models_str += f" +{len(models)-3} more"
        models_lbl = wx.StaticText(self, label=f"Models: {models_str}")
        models_lbl.SetFont(make_font(8))
        models_lbl.SetForegroundColour(TEXT_MUTED)
        info_sizer.Add(models_lbl, 0, wx.TOP, 1)

        sizer.Add(info_sizer, 1, wx.EXPAND | wx.ALL, PADDING_MD)

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        copy_btn = wx.Button(self, label="Copy", size=dip_size(self, 50, 26))
        copy_btn.SetBackgroundColour(wx.Colour(30, 60, 50))
        copy_btn.SetForegroundColour(ACCENT)
        copy_btn.SetFont(make_font(8))
        btn_sizer.Add(copy_btn, 0, wx.RIGHT, 4)

        edit_btn = wx.Button(self, label="Edit", size=dip_size(self, 50, 26))
        edit_btn.SetBackgroundColour(BG_INPUT)
        edit_btn.SetForegroundColour(TEXT_PRIMARY)
        edit_btn.SetFont(make_font(8))
        btn_sizer.Add(edit_btn, 0, wx.RIGHT, 4)

        del_btn = wx.Button(self, label="Del", size=dip_size(self, 40, 26))
        del_btn.SetBackgroundColour(wx.Colour(80, 30, 30))
        del_btn.SetForegroundColour(ERROR)
        del_btn.SetFont(make_font(8))
        btn_sizer.Add(del_btn, 0)

        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
                  PADDING_MD)

        self.SetSizer(sizer)

        copy_btn.Bind(wx.EVT_BUTTON, lambda e: self.on_copy_cb(self.token))
        edit_btn.Bind(wx.EVT_BUTTON, lambda e: self.on_edit_cb(self.token))
        del_btn.Bind(wx.EVT_BUTTON, lambda e: self.on_delete_cb(self.token))


class TokensPanel(wx.Panel):
    """Token management panel"""

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.SetBackgroundColour(BG_PANEL)
        # Cache for tokens data to avoid unnecessary re-rendering
        self._cached_tokens = None
        self._cached_auth_setting = None
        self._build_ui()

    def _build_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Header
        header_row = wx.BoxSizer(wx.HORIZONTAL)

        header = SectionHeader(self, "Access Tokens",
                               "Manage API keys for gateway authentication")
        header_row.Add(header, 1, wx.EXPAND)

        add_btn = wx.Button(self,
                            label="＋  Create Token",
                            size=dip_size(self, 130, 34))
        style_button_primary(add_btn)
        header_row.Add(add_btn, 0, wx.ALIGN_CENTER_VERTICAL)

        sizer.Add(header_row, 0, wx.EXPAND | wx.ALL, PADDING_LG)
        sizer.Add(Divider(self), 0, wx.EXPAND)

        # Auth setting info bar
        self.auth_info = wx.Panel(self)
        self.auth_info.SetBackgroundColour(wx.Colour(20, 40, 30))
        info_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.auth_label = wx.StaticText(
            self.auth_info,
            label="🔒 Authentication is ENABLED — tokens are required")
        self.auth_label.SetFont(make_font(9))
        self.auth_label.SetForegroundColour(SUCCESS)
        info_sizer.Add(self.auth_label, 0, wx.ALL, PADDING_SM)

        self.auth_info.SetSizer(info_sizer)
        sizer.Add(self.auth_info, 0, wx.EXPAND)

        # Token list
        self.scroll = scrolled.ScrolledPanel(self)
        self.scroll.SetBackgroundColour(BG_PANEL)
        self.list_sizer = wx.BoxSizer(wx.VERTICAL)

        self.empty_label = wx.StaticText(
            self.scroll,
            label=
            "No access tokens.\nClick '+ Create Token' to create your first token."
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
        self.refresh()

    def refresh(self, force=False):
        """Refresh the token list from config

        Args:
            force: If True, force re-render even if data hasn't changed
        """
        config = self.controller.get_config()
        tokens = config.tokens

        # Check if auth setting has changed
        auth_changed = self._cached_auth_setting != config.settings.require_auth
        if auth_changed:
            self._cached_auth_setting = config.settings.require_auth
            # Update auth info bar
            if config.settings.require_auth:
                self.auth_label.SetLabel(
                    "🔒 Authentication is ENABLED — tokens are required")
                self.auth_label.SetForegroundColour(SUCCESS)
                self.auth_info.SetBackgroundColour(wx.Colour(20, 40, 30))
            else:
                self.auth_label.SetLabel(
                    "⚠ Authentication is DISABLED — all requests are allowed")
                self.auth_label.SetForegroundColour(WARNING)
                self.auth_info.SetBackgroundColour(wx.Colour(40, 35, 15))

        # Check if tokens data has changed
        tokens_changed = force or auth_changed or self._cached_tokens is None
        if not tokens_changed:
            if len(tokens) != len(self._cached_tokens):
                tokens_changed = True
            else:
                # Compare token data
                current_data = [(t.id, t.name, t.key[:10])
                                for t in sorted(tokens, key=lambda x: x.id)]
                cached_data = [
                    (t.id, t.name, t.key[:10])
                    for t in sorted(self._cached_tokens, key=lambda x: x.id)
                ]
                tokens_changed = current_data != cached_data

        if tokens_changed:
            self._cached_tokens = tokens
            self._render_tokens(tokens)

        self.Layout()

    def _render_tokens(self, tokens):
        # Freeze to prevent flickering during rendering
        self.scroll.Freeze()
        try:
            for child in list(self.scroll.GetChildren()):
                if isinstance(child, TokenRow):
                    child.Destroy()
            self.list_sizer.Clear(False)

            if not tokens:
                self.empty_label.Show()
                self.list_sizer.Add(self.empty_label, 0, wx.ALL, PADDING_XL)
            else:
                self.empty_label.Hide()
                for i, token in enumerate(tokens):
                    row = TokenRow(
                        self.scroll,
                        token,
                        on_edit=self.on_edit,
                        on_delete=self.on_delete,
                        on_copy=self.on_copy,
                    )
                    if i > 0:
                        self.list_sizer.Add(Divider(self.scroll), 0, wx.EXPAND)
                    self.list_sizer.Add(row, 0, wx.EXPAND)

            self.scroll.SetupScrolling()
            self.scroll.Layout()
        finally:
            self.scroll.Thaw()

    def on_add(self, event):
        config = self.controller.get_config()
        dlg = TokenDialog(self, channels=config.channels)
        if dlg.ShowModal() == wx.ID_OK:
            data = dlg.get_token_data()
            self.controller.add_token(data)
            self.refresh()
        dlg.Destroy()

    def on_edit(self, token: TokenConfig):
        config = self.controller.get_config()
        dlg = TokenDialog(self, token, channels=config.channels)
        if dlg.ShowModal() == wx.ID_OK:
            data = dlg.get_token_data()
            self.controller.update_token(token.id, data)
            self.refresh()
        dlg.Destroy()

    def on_delete(self, token: TokenConfig):
        result = wx.MessageBox(f"Delete token '{token.name}'?",
                               "Confirm Delete",
                               wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
                               self)
        if result == wx.YES:
            self.controller.delete_token(token.id)
            self.refresh()

    def on_copy(self, token: TokenConfig):
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(token.key))
            wx.TheClipboard.Close()
            wx.MessageBox(f"Token key copied to clipboard!", "Copied",
                          wx.OK | wx.ICON_INFORMATION)
