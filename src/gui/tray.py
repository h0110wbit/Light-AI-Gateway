"""
System tray icon for AI Gateway
Provides minimize-to-tray functionality and quick controls
"""
import wx
import wx.adv
from src.gui.theme import ACCENT, SUCCESS, TEXT_MUTED


class SystemTrayIcon(wx.adv.TaskBarIcon):
    """
    System tray icon with context menu for quick actions.
    Allows the application to run in background when window is closed.
    """

    def __init__(self, frame, controller):
        super().__init__()
        self.frame = frame
        self.controller = controller

        # Create icon
        self._create_icon()

        # Bind events
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DOWN, self._on_left_click)

    def _create_icon(self):
        """Create the tray icon bitmap"""
        # Create a simple icon using a bitmap
        bmp = wx.Bitmap(16, 16)
        dc = wx.MemoryDC(bmp)
        dc.SetBackground(wx.Brush(wx.Colour(18, 18, 24)))
        dc.Clear()

        # Draw a simple circle/dot
        dc.SetBrush(wx.Brush(ACCENT))
        dc.SetPen(wx.Pen(ACCENT))
        dc.DrawCircle(8, 8, 6)

        dc.SelectObject(wx.NullBitmap)

        # Set the icon
        icon = wx.Icon(bmp)
        self.SetIcon(icon, "AI Gateway")

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
        """Update the tray icon to reflect server status"""
        bmp = wx.Bitmap(16, 16)
        dc = wx.MemoryDC(bmp)
        dc.SetBackground(wx.Brush(wx.Colour(18, 18, 24)))
        dc.Clear()

        # Draw circle with status color
        color = SUCCESS if running else TEXT_MUTED
        dc.SetBrush(wx.Brush(color))
        dc.SetPen(wx.Pen(color))
        dc.DrawCircle(8, 8, 6)

        dc.SelectObject(wx.NullBitmap)

        icon = wx.Icon(bmp)
        status = "Running" if running else "Stopped"
        self.SetIcon(icon, f"AI Gateway - {status}")
