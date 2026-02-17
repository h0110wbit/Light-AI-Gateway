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

    def _load_icon(self, size: int = 16) -> wx.Icon:
        """Load icon from file, fallback to generated icon if not found"""
        if os.path.exists(self._icon_path):
            # Load from file
            img = wx.Image(self._icon_path, wx.BITMAP_TYPE_ICO)
            if img.IsOk():
                # Scale to appropriate size for tray
                img = img.Scale(size, size, wx.IMAGE_QUALITY_HIGH)
                return wx.Icon(img.ConvertToBitmap())

        # Fallback: create a simple icon
        return self._create_fallback_icon()

    def _create_fallback_icon(self) -> wx.Icon:
        """Create a simple fallback icon if icon file is not found"""
        bmp = wx.Bitmap(16, 16)
        dc = wx.MemoryDC(bmp)
        dc.SetBackground(wx.Brush(wx.Colour(18, 18, 24)))
        dc.Clear()
        dc.SetBrush(wx.Brush(ACCENT))
        dc.SetPen(wx.Pen(ACCENT))
        dc.DrawCircle(8, 8, 6)
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
