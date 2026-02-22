"""
UI Theme and color constants for AI Gateway GUI
Clean dark theme with cyan/teal accents
"""
import wx

# ─── Color Palette ──────────────────────────────────────────────────────────────
BG_DARK = wx.Colour(18, 18, 24)  # Main background
BG_PANEL = wx.Colour(26, 26, 36)  # Panel background
BG_CARD = wx.Colour(34, 34, 48)  # Card/section background
BG_INPUT = wx.Colour(42, 42, 58)  # Input field background
BG_HOVER = wx.Colour(50, 50, 68)  # Hover state

ACCENT = wx.Colour(0, 210, 180)  # Primary accent (cyan-teal)
ACCENT_DIM = wx.Colour(0, 150, 128)  # Dimmed accent
ACCENT_GLOW = wx.Colour(80, 240, 210)  # Bright accent for highlights

TEXT_PRIMARY = wx.Colour(230, 235, 240)  # Main text
TEXT_SECONDARY = wx.Colour(140, 150, 165)  # Secondary/muted text
TEXT_MUTED = wx.Colour(80, 90, 105)  # Very muted text
TEXT_ACCENT = wx.Colour(0, 210, 180)  # Accent-colored text

SUCCESS = wx.Colour(50, 210, 120)  # Green for running/ok
WARNING = wx.Colour(255, 185, 50)  # Yellow for warning
ERROR = wx.Colour(240, 80, 80)  # Red for error
INFO = wx.Colour(80, 170, 240)  # Blue for info

BORDER = wx.Colour(55, 55, 75)  # Border color
BORDER_FOCUS = wx.Colour(0, 210, 180)  # Focused border

# ─── Typography ─────────────────────────────────────────────────────────────────
FONT_MONO = "Consolas"
FONT_UI = "Segoe UI"
FONT_TITLE = "Segoe UI Semibold"

# ─── Sizes ──────────────────────────────────────────────────────────────────────
BORDER_RADIUS = 6
PADDING_SM = 6
PADDING_MD = 12
PADDING_LG = 20
PADDING_XL = 32


def get_scaled_sizes(window: wx.Window = None):
    """
    获取DPI缩放后的尺寸常量。
    如果提供了window参数，则使用该窗口的DPI设置进行缩放。
    否则尝试使用wx.Window的静态方法进行缩放。
    """

    def scale(val):
        if window:
            try:
                return window.FromDIP(val)
            except AttributeError:
                return val
        else:
            return dip_to_px(val)

    return {
        'border_radius': scale(BORDER_RADIUS),
        'padding_sm': scale(PADDING_SM),
        'padding_md': scale(PADDING_MD),
        'padding_lg': scale(PADDING_LG),
        'padding_xl': scale(PADDING_XL),
    }


def make_font(size: int = 9,
              bold: bool = False,
              italic: bool = False,
              family: str = FONT_UI) -> wx.Font:
    weight = wx.FONTWEIGHT_BOLD if bold else wx.FONTWEIGHT_NORMAL
    style = wx.FONTSTYLE_ITALIC if italic else wx.FONTSTYLE_NORMAL
    return wx.Font(size, wx.FONTFAMILY_DEFAULT, style, weight, faceName=family)


def apply_dark_theme(window: wx.Window):
    """Apply dark theme colors to a window"""
    window.SetBackgroundColour(BG_PANEL)
    window.SetForegroundColour(TEXT_PRIMARY)


def style_button_primary(btn: wx.Button):
    """Style a button as primary (accent colored)"""
    btn.SetBackgroundColour(ACCENT)
    btn.SetForegroundColour(BG_DARK)
    btn.SetFont(make_font(9, bold=True))


def style_button_secondary(btn: wx.Button):
    """Style a button as secondary"""
    btn.SetBackgroundColour(BG_CARD)
    btn.SetForegroundColour(TEXT_PRIMARY)
    btn.SetFont(make_font(9))


def style_button_danger(btn: wx.Button):
    """Style a button as danger"""
    btn.SetBackgroundColour(ERROR)
    btn.SetForegroundColour(wx.WHITE)
    btn.SetFont(make_font(9, bold=True))


def style_text_ctrl(ctrl: wx.TextCtrl):
    """Style a text control with dark theme and auto-fit height"""
    ctrl.SetBackgroundColour(BG_INPUT)
    ctrl.SetForegroundColour(TEXT_PRIMARY)
    font = make_font(9)
    ctrl.SetFont(font)
    text_height = ctrl.GetTextExtent("Ay")[1]
    padding = 6
    min_height = text_height + padding
    ctrl.SetMinSize((-1, min_height))


def get_control_height(ctrl: wx.Window) -> int:
    """Calculate appropriate control height based on font size"""
    font = make_font(9)
    ctrl.SetFont(font)
    text_height = ctrl.GetTextExtent("Ay")[1]
    padding = 6
    return text_height + padding


def style_choice(ctrl: wx.Choice):
    """Style a choice control with dark theme and auto-fit height"""
    ctrl.SetBackgroundColour(BG_INPUT)
    ctrl.SetForegroundColour(TEXT_PRIMARY)
    font = make_font(9)
    ctrl.SetFont(font)
    text_height = ctrl.GetTextExtent("Ay")[1]
    padding = 6
    min_height = text_height + padding
    ctrl.SetMinSize((-1, min_height))


def style_spin_ctrl(ctrl: wx.SpinCtrl):
    """Style a spin control with dark theme and auto-fit height"""
    ctrl.SetBackgroundColour(BG_INPUT)
    ctrl.SetForegroundColour(TEXT_PRIMARY)
    font = make_font(9)
    ctrl.SetFont(font)
    text_height = ctrl.GetTextExtent("Ay")[1]
    padding = 6
    min_height = text_height + padding
    ctrl.SetMinSize((-1, min_height))


def get_button_height(window: wx.Window) -> int:
    """Calculate appropriate button height based on font size"""
    font = make_font(9, bold=True)
    dc = wx.ClientDC(window)
    dc.SetFont(font)
    text_height = dc.GetTextExtent("Ay")[1]
    padding = 10
    return text_height + padding


def style_label(label: wx.StaticText,
                secondary: bool = False,
                size: int = 9,
                bold: bool = False):
    """Style a static text label"""
    color = TEXT_SECONDARY if secondary else TEXT_PRIMARY
    label.SetForegroundColour(color)
    label.SetFont(make_font(size, bold=bold))


# ─── DIP Conversion Utilities ───────────────────────────────────────────────────
def dip_to_px(dip_value: int) -> int:
    """Convert DIP (Device Independent Pixels) to physical pixels.
    
    On standard displays, 1 DIP = 1 pixel.
    On high DPI displays, this scales appropriately.
    """
    try:
        return wx.Window.DIPToPx(dip_value)
    except AttributeError:
        # Fallback for older wxPython versions
        return dip_value


def px_to_dip(px_value: int) -> int:
    """Convert physical pixels to DIP (Device Independent Pixels)."""
    try:
        return wx.Window.PxToDIP(px_value)
    except AttributeError:
        # Fallback for older wxPython versions
        return px_value


def scale_for_dip(window: wx.Window, size: int) -> int:
    """Scale a size value for the given window's DPI."""
    try:
        return window.FromDIP(size)
    except AttributeError:
        # Fallback for older wxPython versions
        return size
