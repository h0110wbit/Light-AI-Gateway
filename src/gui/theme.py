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
    """Style a text control with dark theme"""
    ctrl.SetBackgroundColour(BG_INPUT)
    ctrl.SetForegroundColour(TEXT_PRIMARY)
    ctrl.SetFont(make_font(9))


def style_label(label: wx.StaticText,
                secondary: bool = False,
                size: int = 9,
                bold: bool = False):
    """Style a static text label"""
    color = TEXT_SECONDARY if secondary else TEXT_PRIMARY
    label.SetForegroundColour(color)
    label.SetFont(make_font(size, bold=bold))
