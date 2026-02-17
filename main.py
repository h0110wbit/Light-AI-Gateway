"""
AI Gateway - Personal Lightweight AI API Gateway
Entry point for the application
"""
import sys
import os
import argparse

# Ensure the src directory is in the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="AI Gateway - Personal LLM API Gateway")
    parser.add_argument(
        "--silent",
        action="store_true",
        help="Start minimized to system tray (no visible window)"
    )
    parser.add_argument(
        "--start",
        action="store_true",
        help="Auto-start the gateway server on launch"
    )
    return parser.parse_args()


def main():
    """Main entry point - launch the wxPython GUI application"""
    args = parse_args()
    
    from src.gui.app import GatewayApp
    app = GatewayApp(silent=args.silent, auto_start=args.start)
    app.MainLoop()


if __name__ == "__main__":
    main()
