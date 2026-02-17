"""
Windows Auto-start management module
Handles registry operations for auto-start on Windows login
"""
import sys
import os


def is_windows() -> bool:
    """Check if the current platform is Windows"""
    return sys.platform == "win32"


def get_app_path() -> str:
    """
    Get the application executable path.
    Returns the EXE path when running as compiled, or the script path when running from source.
    """
    if getattr(sys, 'frozen', False):
        return sys.executable
    else:
        return os.path.abspath(sys.argv[0])


def is_auto_start_enabled() -> bool:
    """
    Check if auto-start is currently enabled in Windows registry.
    Returns False on non-Windows platforms.
    """
    if not is_windows():
        return False
    
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_READ
        )
        try:
            winreg.QueryValueEx(key, "AI Gateway")
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except Exception:
        return False


def enable_auto_start() -> bool:
    """
    Enable auto-start by adding registry entry.
    The application will start silently (minimized to tray) on Windows login.
    Returns True on success, False on failure.
    """
    if not is_windows():
        return False
    
    try:
        import winreg
        app_path = get_app_path()
        
        # Add --silent and --start flags for background startup
        command = f'"{app_path}" --silent --start'
        
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_WRITE
        )
        
        winreg.SetValueEx(
            key,
            "AI Gateway",
            0,
            winreg.REG_SZ,
            command
        )
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"Failed to enable auto-start: {e}")
        return False


def disable_auto_start() -> bool:
    """
    Disable auto-start by removing registry entry.
    Returns True on success, False on failure.
    """
    if not is_windows():
        return False
    
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_WRITE
        )
        
        try:
            winreg.DeleteValue(key, "AI Gateway")
        except FileNotFoundError:
            pass
        
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"Failed to disable auto-start: {e}")
        return False


def set_auto_start(enabled: bool) -> bool:
    """
    Set auto-start state.
    
    Args:
        enabled: True to enable auto-start, False to disable
        
    Returns:
        True on success, False on failure
    """
    if enabled:
        return enable_auto_start()
    else:
        return disable_auto_start()
