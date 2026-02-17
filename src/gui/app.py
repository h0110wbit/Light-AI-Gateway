"""
Main wxPython Application entry point
"""
import wx
from src.gui.main_frame import MainFrame


class GatewayApp(wx.App):
    """Main wxPython application"""

    def OnInit(self):
        self.SetAppName("AI Gateway")

        # Set app-wide font
        font = wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL,
                       wx.FONTWEIGHT_NORMAL)
        wx.SystemOptions.SetOption("msw.remap", 0)

        frame = MainFrame(None, title="AI Gateway - Personal LLM Proxy")
        frame.Show()
        self.SetTopWindow(frame)
        return True

    def OnExit(self):
        return 0
