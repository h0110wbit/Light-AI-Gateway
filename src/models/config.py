"""
Configuration models for AI Gateway
"""
from __future__ import annotations
from pydantic import BaseModel, field_validator, ConfigDict
from typing import Optional, List
import json
import os


class ChannelConfig(BaseModel):
    """Represents an upstream AI provider channel"""
    model_config = ConfigDict(validate_assignment=True)
    
    id: int
    name: str
    type: str  # openai, anthropic, gemini, ollama, custom
    base_url: str
    api_key: str
    models: List[str] = []
    enabled: bool = True
    priority: int = 1  # lower = higher priority
    timeout: int = 60
    max_retries: int = 3
    
    @field_validator('base_url')
    @classmethod
    def normalize_base_url(cls, v):
        return v.rstrip('/')


class TokenConfig(BaseModel):
    """Represents an access token for the gateway"""
    id: int
    name: str
    key: str  # the actual token value
    enabled: bool = True
    # Which channels this token can access (empty = all channels)
    allowed_channels: List[int] = []
    # Which models this token can access (empty = all models)
    allowed_models: List[str] = []


class GatewaySettings(BaseModel):
    """Global gateway settings"""
    host: str = "0.0.0.0"
    port: int = 3000
    log_level: str = "info"
    # Whether to require authentication
    require_auth: bool = True
    # Default timeout for upstream requests
    default_timeout: int = 120
    # Allow model fallback if primary channel fails
    enable_fallback: bool = True
    # Add CORS headers
    enable_cors: bool = True
    cors_origins: List[str] = ["*"]


class AppConfig(BaseModel):
    """Complete application configuration"""
    settings: GatewaySettings = GatewaySettings()
    channels: List[ChannelConfig] = []
    tokens: List[TokenConfig] = []
    
    def get_channel_by_id(self, channel_id: int) -> Optional[ChannelConfig]:
        for ch in self.channels:
            if ch.id == channel_id:
                return ch
        return None
    
    def get_enabled_channels(self) -> List[ChannelConfig]:
        return sorted(
            [ch for ch in self.channels if ch.enabled],
            key=lambda x: x.priority
        )
    
    def get_channels_for_model(self, model: str) -> List[ChannelConfig]:
        """Get channels that support a given model, sorted by priority"""
        channels = []
        model_lower = model.lower()
        for ch in self.get_enabled_channels():
            # If channel has no models specified, it accepts all models
            if not ch.models or model_lower in [m.lower() for m in ch.models]:
                channels.append(ch)
        return channels
    
    def validate_token(self, token_key: str) -> Optional[TokenConfig]:
        """Validate an access token and return its config if valid"""
        for token in self.tokens:
            if token.enabled and token.key == token_key:
                return token
        return None
    
    def next_channel_id(self) -> int:
        if not self.channels:
            return 1
        return max(ch.id for ch in self.channels) + 1
    
    def next_token_id(self) -> int:
        if not self.tokens:
            return 1
        return max(t.id for t in self.tokens) + 1


# Default config file path
CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")


def load_config(config_path: str = CONFIG_FILE) -> AppConfig:
    """Load configuration from JSON file"""
    if not os.path.exists(config_path):
        return AppConfig()
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return AppConfig(**data)
    except Exception:
        return AppConfig()


def save_config(config: AppConfig, config_path: str = CONFIG_FILE) -> bool:
    """Save configuration to JSON file"""
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config.model_dump(), f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False
