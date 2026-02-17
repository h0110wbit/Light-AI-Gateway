"""
AI Gateway - Personal Lightweight AI API Gateway
Entry point for the application
"""
import sys
import os

# Ensure the src directory is in the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    """Main entry point - launch the wxPython GUI application"""
    from src.gui.app import GatewayApp
    app = GatewayApp()
    app.MainLoop()


if __name__ == "__main__":
    main()
