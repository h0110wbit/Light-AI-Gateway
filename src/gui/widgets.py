"""
Custom reusable widgets for AI Gateway GUI
"""
import wx
import wx.lib.scrolledpanel as scrolled
from src.gui.theme import *


def dip(window: wx.Window, size: int) -> int:
    """将逻辑尺寸转换为物理像素尺寸（DPI感知）。"""
    try:
        return window.FromDIP(size)
    except AttributeError:
        return size


def dip_size(window: wx.Window, width: int, height: int) -> tuple:
    """将逻辑尺寸元组转换为物理像素尺寸（DPI感知）。"""
    return (dip(window, width), dip(window, height))


class DarkPanel(wx.Panel):
    """A panel with dark theme applied"""

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.SetBackgroundColour(BG_PANEL)


class CardPanel(wx.Panel):
    """A card-style panel with rounded appearance"""

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.SetBackgroundColour(BG_CARD)
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_SIZE, self._on_size)

    def _on_paint(self, event):
        dc = wx.PaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        if gc:
            w, h = self.GetSize()
            gc.SetBrush(gc.CreateBrush(wx.Brush(BG_CARD)))
            gc.SetPen(gc.CreatePen(wx.Pen(BORDER, 1)))
            gc.DrawRoundedRectangle(0, 0, w - 1, h - 1, BORDER_RADIUS)

    def _on_size(self, event):
        self.Refresh()
        event.Skip()


class SectionHeader(wx.Panel):
    """A section header with title and optional subtitle"""

    def __init__(self, parent, title: str, subtitle: str = ""):
        super().__init__(parent)
        self.SetBackgroundColour(BG_PANEL)

        sizer = wx.BoxSizer(wx.VERTICAL)

        title_label = wx.StaticText(self, label=title)
        title_label.SetFont(make_font(14, bold=True, family=FONT_TITLE))
        title_label.SetForegroundColour(TEXT_PRIMARY)
        sizer.Add(title_label, 0, wx.BOTTOM, 2)

        if subtitle:
            sub_label = wx.StaticText(self, label=subtitle)
            sub_label.SetFont(make_font(9, family=FONT_UI))
            sub_label.SetForegroundColour(TEXT_SECONDARY)
            sizer.Add(sub_label, 0)

        self.SetSizer(sizer)


class StatusBadge(wx.Panel):
    """A colored status indicator badge"""

    STATUS_COLORS = {
        "running": SUCCESS,
        "stopped": TEXT_MUTED,
        "error": ERROR,
        "warning": WARNING,
    }

    def __init__(self, parent, status: str = "stopped", label: str = ""):
        super().__init__(parent, size=dip_size(parent, -1, 24))
        self.SetBackgroundColour(BG_PANEL)
        self._status = status
        self._label = label
        self.Bind(wx.EVT_PAINT, self._on_paint)

    def set_status(self, status: str, label: str = ""):
        self._status = status
        if label:
            self._label = label
        self.Refresh()

    def _on_paint(self, event):
        dc = wx.PaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        if not gc:
            return

        color = self.STATUS_COLORS.get(self._status, TEXT_MUTED)
        w, h = self.GetSize()

        # Draw dot
        dot_r = dip(self, 5)
        dot_x = dot_r + dip(self, 2)
        dot_y = h // 2
        gc.SetBrush(gc.CreateBrush(wx.Brush(color)))
        gc.SetPen(gc.CreatePen(wx.Pen(wx.TRANSPARENT_PEN)))
        gc.DrawEllipse(dot_x - dot_r, dot_y - dot_r, dot_r * 2, dot_r * 2)

        # Draw label
        label = self._label or self._status.upper()
        gc.SetFont(gc.CreateFont(make_font(9, bold=True), color))
        tw, th = gc.GetTextExtent(label)
        gc.DrawText(label, dot_x + dot_r + dip(self, 6), (h - th) / 2)


class LabeledInput(wx.Panel):
    """An input field with a label above it"""

    def __init__(self,
                 parent,
                 label: str,
                 value: str = "",
                 password: bool = False,
                 multiline: bool = False,
                 readonly: bool = False):
        super().__init__(parent)
        self.SetBackgroundColour(BG_PANEL)

        sizer = wx.BoxSizer(wx.VERTICAL)

        lbl = wx.StaticText(self, label=label)
        lbl.SetFont(make_font(8, bold=True))
        lbl.SetForegroundColour(TEXT_SECONDARY)
        sizer.Add(lbl, 0, wx.BOTTOM, 4)

        style = 0
        if password:
            style |= wx.TE_PASSWORD
        if multiline:
            style |= wx.TE_MULTILINE
        if readonly:
            style |= wx.TE_READONLY

        self.ctrl = wx.TextCtrl(self, value=value, style=style)
        style_text_ctrl(self.ctrl)
        if multiline:
            self.ctrl.SetMinSize(dip_size(self, -1, 80))
        sizer.Add(self.ctrl, 1 if multiline else 0, wx.EXPAND)

        self.SetSizer(sizer)

    def GetValue(self) -> str:
        return self.ctrl.GetValue()

    def SetValue(self, value: str):
        self.ctrl.SetValue(value)


class ToggleSwitch(wx.Panel):
    """A toggle switch widget"""

    def __init__(self, parent, label: str = "", value: bool = True):
        super().__init__(parent, size=dip_size(parent, -1, 28))
        self.SetBackgroundColour(BG_PANEL)
        self._value = value
        self._label = label
        self._hover = False

        sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_click)
        self.Bind(wx.EVT_ENTER_WINDOW, lambda e: self._set_hover(True))
        self.Bind(wx.EVT_LEAVE_WINDOW, lambda e: self._set_hover(False))

        # Reserve space for switch + label
        self.SetMinSize(dip_size(self, 100, 28))

    def _set_hover(self, val: bool):
        self._hover = val
        self.Refresh()

    def _on_click(self, event):
        self._value = not self._value
        self.Refresh()
        # Send event to self
        evt = wx.CommandEvent(wx.EVT_CHECKBOX.typeId, self.GetId())
        evt.SetInt(1 if self._value else 0)
        evt.SetEventObject(self)
        wx.PostEvent(self, evt)

    def GetValue(self) -> bool:
        return self._value

    def SetValue(self, value: bool):
        self._value = value
        self.Refresh()

    def _on_paint(self, event):
        dc = wx.PaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        if not gc:
            return

        w, h = self.GetSize()

        # Track dimensions
        track_w = dip(self, 40)
        track_h = dip(self, 20)
        track_x = 0
        track_y = (h - track_h) // 2
        radius = track_h // 2

        # Track background
        track_color = ACCENT if self._value else BG_INPUT
        gc.SetBrush(gc.CreateBrush(wx.Brush(track_color)))
        gc.SetPen(gc.CreatePen(wx.Pen(wx.TRANSPARENT_PEN)))
        gc.DrawRoundedRectangle(track_x, track_y, track_w, track_h, radius)

        # Thumb
        thumb_r = track_h // 2 - dip(self, 2)
        thumb_x = track_x + (track_w - track_h + dip(self, 2)
                             ) + 1 if self._value else track_x + dip(self, 2)
        thumb_y = track_y + track_h // 2
        gc.SetBrush(gc.CreateBrush(wx.Brush(wx.WHITE)))
        gc.DrawEllipse(thumb_x, thumb_y - thumb_r, thumb_r * 2, thumb_r * 2)

        # Label
        if self._label:
            gc.SetFont(gc.CreateFont(make_font(9), TEXT_PRIMARY))
            tw, th = gc.GetTextExtent(self._label)
            gc.DrawText(self._label, track_w + dip(self, 8), (h - th) / 2)


class LogPanel(wx.Panel):
    """A scrollable log output panel"""

    def __init__(self, parent):
        super().__init__(parent)
        self.SetBackgroundColour(BG_DARK)

        sizer = wx.BoxSizer(wx.VERTICAL)

        self.log_ctrl = wx.TextCtrl(self,
                                    style=wx.TE_MULTILINE | wx.TE_READONLY
                                    | wx.TE_RICH2 | wx.HSCROLL)
        self.log_ctrl.SetBackgroundColour(BG_DARK)
        self.log_ctrl.SetForegroundColour(TEXT_PRIMARY)
        self.log_ctrl.SetFont(make_font(8, family=FONT_MONO))

        sizer.Add(self.log_ctrl, 1, wx.EXPAND)
        self.SetSizer(sizer)

    def append(self, text: str, color: wx.Colour = None):
        """Append a line to the log"""
        if color:
            attr = wx.TextAttr(color)
            self.log_ctrl.SetDefaultStyle(attr)
        self.log_ctrl.AppendText(text + "\n")
        # Reset to default
        self.log_ctrl.SetDefaultStyle(wx.TextAttr(TEXT_PRIMARY))
        self.log_ctrl.ShowPosition(self.log_ctrl.GetLastPosition())

    def clear(self):
        self.log_ctrl.Clear()


class Divider(wx.Panel):
    """A horizontal divider line"""

    def __init__(self, parent):
        super().__init__(parent, size=dip_size(parent, -1, 1))
        self.SetBackgroundColour(BORDER)
        self.SetMinSize(dip_size(self, -1, 1))


class IconButton(wx.Button):
    """A compact icon-style button"""

    def __init__(self,
                 parent,
                 label: str,
                 color: wx.Colour = None,
                 tooltip: str = ""):
        super().__init__(parent, label=label, size=dip_size(parent, -1, 28))
        bg = color or BG_CARD
        self.SetBackgroundColour(bg)
        self.SetForegroundColour(TEXT_PRIMARY)
        self.SetFont(make_font(8))
        if tooltip:
            self.SetToolTip(tooltip)
