"""
System tray icon for AI Gateway
Provides minimize-to-tray functionality and quick controls
"""
import wx
import wx.adv
import os
import sys
from src.gui.theme import ACCENT, SUCCESS, TEXT_MUTED


def get_icon_path() -> str:
    """
    Get the path to the application icon file.
    Handles both source mode and compiled EXE mode (including PyInstaller onefile).
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled EXE
        # PyInstaller extracts resources to sys._MEIPASS for onefile mode
        if hasattr(sys, '_MEIPASS'):
            base_dir = sys._MEIPASS
        else:
            base_dir = os.path.dirname(sys.executable)
    else:
        # Running from source - project root is parent of src
        base_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    return os.path.join(base_dir, "resources", "icon.ico")


def get_tray_icon_size() -> int:
    """
    获取系统托盘图标的推荐尺寸。
    在高DPI显示器上返回更大的尺寸以确保图标清晰。
    """
    try:
        # 获取系统推荐的托盘图标尺寸
        size_info = wx.adv.TaskBarIcon.GetSystemIconSize()
        if size_info:
            return max(size_info[0], size_info[1])
    except Exception:
        pass
    
    # 备用方案：根据DPI缩放计算
    try:
        scale_factor = wx.GetDisplayPPI()[0] / 96.0
        base_size = 16
        return int(base_size * scale_factor)
    except Exception:
        pass
    
    # 默认返回较大尺寸以确保在高DPI下清晰
    return 32


class SystemTrayIcon(wx.adv.TaskBarIcon):
    """
    System tray icon with context menu for quick actions.
    Allows the application to run in background when window is closed.
    """

    def __init__(self, frame, controller):
        super().__init__()
        self.frame = frame
        self.controller = controller
        self._icon_path = get_icon_path()

        # Create icon
        self._create_icon()

        # Bind events
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DOWN, self._on_left_click)

    def _create_icon(self):
        """Create the tray icon from icon file"""
        icon = self._load_icon()
        self.SetIcon(icon, "AI Gateway")

    def _load_icon(self) -> wx.Icon:
        """
        Load icon from file with appropriate size for system tray.
        Uses larger icon size for high DPI displays.
        """
        # 获取适合当前DPI的图标尺寸
        target_size = get_tray_icon_size()
        
        if os.path.exists(self._icon_path):
            # Load from file - ICO files can contain multiple sizes
            img = wx.Image(self._icon_path, wx.BITMAP_TYPE_ICO)
            if img.IsOk():
                # 获取原始尺寸
                orig_w, orig_h = img.GetWidth(), img.GetHeight()
                
                # 如果原始图像足够大，直接缩放到目标尺寸
                if orig_w >= target_size:
                    img = img.Scale(target_size, target_size, wx.IMAGE_QUALITY_HIGH)
                else:
                    # 如果原始图像较小，尝试放大但保持质量
                    img = img.Scale(target_size, target_size, wx.IMAGE_QUALITY_HIGH)
                
                return wx.Icon(img.ConvertToBitmap())

        # Fallback: create a simple icon with proper size
        return self._create_fallback_icon(target_size)

    def _create_fallback_icon(self, size: int = 32) -> wx.Icon:
        """
        Create a simple fallback icon if icon file is not found.
        
        Args:
            size: The size of the icon to create
        """
        bmp = wx.Bitmap(size, size)
        dc = wx.MemoryDC(bmp)
        dc.SetBackground(wx.Brush(wx.Colour(18, 18, 24)))
        dc.Clear()
        dc.SetBrush(wx.Brush(ACCENT))
        dc.SetPen(wx.Pen(ACCENT))
        # 按比例绘制圆形
        center = size // 2
        radius = int(size * 0.375)
        dc.DrawCircle(center, center, radius)
        dc.SelectObject(wx.NullBitmap)
        return wx.Icon(bmp)

    def _on_left_click(self, event):
        """Handle left click on tray icon - show/hide window"""
        if self.frame.IsShown():
            self.frame.Hide()
        else:
            self.frame.Show()
            self.frame.Raise()

    def CreatePopupMenu(self):
        """Create the right-click context menu"""
        menu = wx.Menu()

        # Server status
        running = self.controller.is_running()
        status_text = "● Running" if running else "○ Stopped"
        status_item = menu.Append(wx.ID_ANY, status_text)
        status_item.Enable(False)

        menu.AppendSeparator()

        # Start/Stop server
        if running:
            stop_item = menu.Append(wx.ID_ANY, "Stop Gateway")
            self.Bind(wx.EVT_MENU, self._on_stop, stop_item)
        else:
            start_item = menu.Append(wx.ID_ANY, "Start Gateway")
            self.Bind(wx.EVT_MENU, self._on_start, start_item)

        menu.AppendSeparator()

        # Show window
        show_item = menu.Append(wx.ID_ANY, "Show Window")
        self.Bind(wx.EVT_MENU, self._on_show, show_item)

        # Open in browser
        browser_item = menu.Append(wx.ID_ANY, "Open API in Browser")
        self.Bind(wx.EVT_MENU, self._on_open_browser, browser_item)

        menu.AppendSeparator()

        # Quit
        quit_item = menu.Append(wx.ID_EXIT, "Quit AI Gateway")
        self.Bind(wx.EVT_MENU, self._on_quit, quit_item)

        return menu

    def _on_start(self, event):
        """Start the gateway server"""
        self.controller.start_server()

    def _on_stop(self, event):
        """Stop the gateway server"""
        self.controller.stop_server()

    def _on_show(self, event):
        """Show the main window"""
        self.frame.Show()
        self.frame.Raise()

    def _on_open_browser(self, event):
        """Open the API endpoint in browser"""
        import webbrowser
        config = self.controller.get_config()
        host = config.settings.host
        display_host = "localhost" if host == "0.0.0.0" else host
        port = config.settings.port
        webbrowser.open(f"http://{display_host}:{port}/docs")

    def _on_quit(self, event):
        """Quit the application completely"""
        self.frame._really_close = True
        self.frame.Close()

    def update_icon_status(self, running: bool):
        """Update the tray icon tooltip to reflect server status"""
        status = "Running" if running else "Stopped"
        self.SetIcon(self._load_icon(), f"AI Gateway - {status}")
