"""
Main wxPython Application entry point
"""
import wx
from src.gui.main_frame import MainFrame


class GatewayApp(wx.App):
    """Main wxPython application"""

    def __init__(self, silent=False, auto_start=False):
        self._silent = silent
        self._auto_start = auto_start
        self._instance_checker = None
        super().__init__()

    def OnInit(self):
        self.SetAppName("AI Gateway")

        # Check for single instance
        self._instance_checker = wx.SingleInstanceChecker(
            "AI-Gateway-Instance")
        if self._instance_checker.IsAnotherRunning():
            # Another instance is already running
            if not self._silent:
                wx.MessageBox(
                    "AI Gateway is already running.\n\nCheck the system tray for the running instance.",
                    "AI Gateway", wx.OK | wx.ICON_WARNING)
            return False

        # Set app-wide font
        font = wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL,
                       wx.FONTWEIGHT_NORMAL)
        wx.SystemOptions.SetOption("msw.remap", 0)

        frame = MainFrame(None,
                          title="AI Gateway - Personal LLM Proxy",
                          silent=self._silent,
                          auto_start=self._auto_start)

        # Only show window if not in silent mode
        if not self._silent:
            frame.Show()

        self.SetTopWindow(frame)
        return True

    def OnExit(self):
        # Clean up instance checker
        if self._instance_checker:
            del self._instance_checker
        return 0
