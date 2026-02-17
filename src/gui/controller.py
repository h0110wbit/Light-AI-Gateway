"""
Controller - connects the GUI to backend services
Handles all business logic between UI events and the gateway server/config
"""
from __future__ import annotations
import threading
import logging
from typing import Optional, Callable
from src.models.config import AppConfig, ChannelConfig, TokenConfig, GatewaySettings, load_config, save_config
from src.core.server import GatewayServer

logger = logging.getLogger("ai-gateway.controller")


class GatewayController:
    """
    Central controller for the AI Gateway application.
    Manages configuration, server lifecycle, and provides callbacks for UI updates.
    """
    
    def __init__(self):
        self._config = load_config()
        self._server = GatewayServer()
        self._callbacks = {
            "status_changed": [],
            "config_changed": [],
            "log_message": [],
        }
        
        # Wire up server status callback
        self._server.set_status_callback(self._on_server_status)
    
    # ─── Callback registration ──────────────────────────────────────────────────
    
    def on_status_changed(self, callback: Callable):
        self._callbacks["status_changed"].append(callback)
    
    def on_config_changed(self, callback: Callable):
        self._callbacks["config_changed"].append(callback)
    
    def on_log_message(self, callback: Callable):
        self._callbacks["log_message"].append(callback)
    
    def _fire(self, event: str, *args, **kwargs):
        """Fire callbacks for an event, safely on the main thread"""
        import wx
        for cb in self._callbacks.get(event, []):
            wx.CallAfter(cb, *args, **kwargs)
    
    def _on_server_status(self, status: str):
        self._fire("status_changed", status)
        if status == "started":
            self._log(f"Gateway started on {self._config.settings.host}:{self._config.settings.port}", "success")
        elif status == "stopped":
            self._log("Gateway stopped", "info")
        elif status == "config_reloaded":
            self._log("Configuration reloaded", "success")
    
    def _log(self, message: str, level: str = "info"):
        logger.info(message)
        self._fire("log_message", message, level)
    
    # ─── Server management ──────────────────────────────────────────────────────
    
    def start_server(self):
        """Start the gateway server"""
        if self._server.is_running():
            self._log("Server is already running", "warning")
            return
        
        self._log("Starting gateway server...", "info")
        
        def _start():
            try:
                self._server.start(self._config)
            except Exception as e:
                self._log(f"Failed to start server: {e}", "error")
        
        thread = threading.Thread(target=_start, daemon=True)
        thread.start()
    
    def stop_server(self):
        """Stop the gateway server"""
        if not self._server.is_running():
            return
        
        self._log("Stopping gateway server...", "info")
        
        def _stop():
            self._server.stop()
        
        thread = threading.Thread(target=_stop, daemon=True)
        thread.start()
    
    def restart_server(self):
        """Restart the gateway server"""
        self._log("Restarting gateway server...", "info")
        
        def _restart():
            self._server.stop()
            import time
            time.sleep(1)
            self._server.start(self._config)
        
        thread = threading.Thread(target=_restart, daemon=True)
        thread.start()
    
    def is_running(self) -> bool:
        return self._server.is_running()
    
    def reload_config(self):
        """Reload configuration into the running server"""
        if self._server.is_running():
            self._server.reload(self._config)
            self._log("Configuration reloaded into running server", "success")
    
    # ─── Config access ──────────────────────────────────────────────────────────
    
    def get_config(self) -> AppConfig:
        return self._config
    
    def _save(self):
        """Save config and notify UI"""
        save_config(self._config)
        self._fire("config_changed", self._config)
        # Also reload if server is running
        if self._server.is_running():
            self._server.reload(self._config)
    
    # ─── Channel management ─────────────────────────────────────────────────────
    
    def add_channel(self, data: dict):
        """Add a new channel"""
        channel = ChannelConfig(
            id=self._config.next_channel_id(),
            **data
        )
        self._config.channels.append(channel)
        self._save()
        self._log(f"Channel '{channel.name}' added", "success")
    
    def update_channel(self, channel_id: int, data: dict):
        """Update an existing channel"""
        for i, ch in enumerate(self._config.channels):
            if ch.id == channel_id:
                updated = ChannelConfig(id=channel_id, **data)
                self._config.channels[i] = updated
                self._save()
                self._log(f"Channel '{updated.name}' updated", "success")
                return
        self._log(f"Channel {channel_id} not found", "error")
    
    def delete_channel(self, channel_id: int):
        """Delete a channel"""
        ch = self._config.get_channel_by_id(channel_id)
        name = ch.name if ch else str(channel_id)
        self._config.channels = [c for c in self._config.channels if c.id != channel_id]
        self._save()
        self._log(f"Channel '{name}' deleted", "info")
    
    def toggle_channel(self, channel_id: int):
        """Toggle channel enabled state"""
        ch = self._config.get_channel_by_id(channel_id)
        if ch:
            ch.enabled = not ch.enabled
            self._save()
            status = "enabled" if ch.enabled else "disabled"
            self._log(f"Channel '{ch.name}' {status}", "success")
        else:
            self._log(f"Channel {channel_id} not found", "error")
    
    # ─── Token management ───────────────────────────────────────────────────────
    
    def add_token(self, data: dict):
        """Add a new token"""
        token = TokenConfig(
            id=self._config.next_token_id(),
            allowed_channels=data.pop("allowed_channels", []),
            **data
        )
        self._config.tokens.append(token)
        self._save()
        self._log(f"Token '{token.name}' created", "success")
    
    def update_token(self, token_id: int, data: dict):
        """Update an existing token"""
        for i, t in enumerate(self._config.tokens):
            if t.id == token_id:
                updated = TokenConfig(
                    id=token_id,
                    allowed_channels=data.pop("allowed_channels", t.allowed_channels),
                    **data
                )
                self._config.tokens[i] = updated
                self._save()
                self._log(f"Token '{updated.name}' updated", "success")
                return
    
    def delete_token(self, token_id: int):
        """Delete a token"""
        token = next((t for t in self._config.tokens if t.id == token_id), None)
        name = token.name if token else str(token_id)
        self._config.tokens = [t for t in self._config.tokens if t.id != token_id]
        self._save()
        self._log(f"Token '{name}' deleted", "info")
    
    # ─── Settings management ─────────────────────────────────────────────────────
    
    def update_settings(self, data: dict):
        """Update global settings"""
        self._config.settings = GatewaySettings(**data)
        self._save()
        self._log("Settings updated", "success")
    
    # ─── Stats ──────────────────────────────────────────────────────────────────
    
    def get_stats(self) -> dict:
        """Get current stats for dashboard display"""
        enabled_channels = len(self._config.get_enabled_channels())
        active_tokens = len([t for t in self._config.tokens if t.enabled])
        
        all_models = set()
        for ch in self._config.channels:
            all_models.update(ch.models)
        
        return {
            "channels": enabled_channels,
            "tokens": active_tokens,
            "models": len(all_models),
        }
