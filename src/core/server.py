"""
FastAPI server for AI Gateway
Implements OpenAI-compatible API endpoints
"""
from __future__ import annotations
import asyncio
import logging
import logging.config
import threading
import uvicorn
from typing import Optional, Callable
from contextlib import asynccontextmanager


def _configure_logging(log_level: str = "info"):
    """
    Manually configure logging to avoid uvicorn's default formatter
    lookup which breaks under PyInstaller ('Unable to configure formatter default').
    We set up a simple StreamHandler ourselves and tell uvicorn to skip its
    own log setup via log_config=None.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Root logger
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(fmt)
        root.addHandler(handler)
    root.setLevel(level)

    # Quiet down noisy uvicorn sub-loggers we don't need
    for name in ("uvicorn.error", "uvicorn.access", "uvicorn", "fastapi"):
        lgr = logging.getLogger(name)
        lgr.setLevel(level)
        lgr.propagate = True

from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from src.models.config import AppConfig
from src.core.proxy import ProxyEngine

logger = logging.getLogger("ai-gateway.server")

# Global proxy engine instance
_proxy_engine: Optional[ProxyEngine] = None
_app_config: Optional[AppConfig] = None


def get_proxy_engine() -> ProxyEngine:
    global _proxy_engine
    if _proxy_engine is None:
        raise RuntimeError("Proxy engine not initialized")
    return _proxy_engine


def create_app(config: AppConfig) -> FastAPI:
    """Create and configure the FastAPI application"""
    global _proxy_engine, _app_config
    _app_config = config
    _proxy_engine = ProxyEngine(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("AI Gateway starting up...")
        yield
        logger.info("AI Gateway shutting down...")
        engine = get_proxy_engine()
        await engine.close()

    app = FastAPI(
        title="AI Gateway",
        description="Personal Lightweight AI API Gateway",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS middleware
    if config.settings.enable_cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # ─── Helper to extract bearer token ────────────────────────────────────────
    def extract_token(authorization: Optional[str]) -> Optional[str]:
        if not authorization:
            return None
        if authorization.startswith("Bearer "):
            return authorization[7:]
        return authorization

    # ─── Health check ───────────────────────────────────────────────────────────
    @app.get("/health")
    async def health_check():
        engine = get_proxy_engine()
        channels = engine.config.get_enabled_channels()
        return {
            "status": "ok",
            "version": "1.0.0",
            "channels": len(channels),
        }

    # ─── Models endpoint ────────────────────────────────────────────────────────
    @app.get("/v1/models")
    async def list_models(authorization: Optional[str] = Header(default=None)):
        engine = get_proxy_engine()
        token = extract_token(authorization)
        return await engine.list_models(token)

    # ─── Chat completions ───────────────────────────────────────────────────────
    @app.post("/v1/chat/completions")
    async def chat_completions(
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ):
        engine = get_proxy_engine()
        token = extract_token(authorization)
        return await engine.proxy_request(request, "/v1/chat/completions", token)

    # ─── Completions (legacy) ───────────────────────────────────────────────────
    @app.post("/v1/completions")
    async def completions(
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ):
        engine = get_proxy_engine()
        token = extract_token(authorization)
        return await engine.proxy_request(request, "/v1/completions", token)

    # ─── Embeddings ─────────────────────────────────────────────────────────────
    @app.post("/v1/embeddings")
    async def embeddings(
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ):
        engine = get_proxy_engine()
        token = extract_token(authorization)
        return await engine.proxy_request(request, "/v1/embeddings", token)

    # ─── Images ─────────────────────────────────────────────────────────────────
    @app.post("/v1/images/generations")
    async def image_generations(
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ):
        engine = get_proxy_engine()
        token = extract_token(authorization)
        return await engine.proxy_request(request, "/v1/images/generations", token)

    # ─── Audio TTS ──────────────────────────────────────────────────────────────
    @app.post("/v1/audio/speech")
    async def audio_speech(
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ):
        engine = get_proxy_engine()
        token = extract_token(authorization)
        return await engine.proxy_request(request, "/v1/audio/speech", token)

    # ─── Audio transcriptions ───────────────────────────────────────────────────
    @app.post("/v1/audio/transcriptions")
    async def audio_transcriptions(
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ):
        engine = get_proxy_engine()
        token = extract_token(authorization)
        return await engine.proxy_request(request, "/v1/audio/transcriptions", token)

    # ─── Catch-all proxy ────────────────────────────────────────────────────────
    @app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
    async def catch_all_v1(
        path: str,
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ):
        engine = get_proxy_engine()
        token = extract_token(authorization)
        return await engine.proxy_request(request, f"/v1/{path}", token)

    # ─── Global error handler ───────────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled error: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": {"message": str(exc), "type": "internal_error"}}
        )

    return app


class GatewayServer:
    """Manages the lifecycle of the FastAPI server in a background thread"""

    def __init__(self):
        self._server: Optional[uvicorn.Server] = None
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._running = False
        self._status_callback: Optional[Callable[[str], None]] = None

    def set_status_callback(self, callback: Callable[[str], None]):
        self._status_callback = callback

    def _notify(self, msg: str):
        if self._status_callback:
            self._status_callback(msg)

    def is_running(self) -> bool:
        return self._running

    def start(self, config: AppConfig) -> bool:
        """Start the gateway server"""
        if self._running:
            return False

        app = create_app(config)

        # Configure logging ourselves BEFORE uvicorn starts.
        # Passing log_config=None tells uvicorn NOT to touch logging at all,
        # which avoids the "Unable to configure formatter 'default'" error
        # that appears in PyInstaller-frozen environments.
        _configure_logging(config.settings.log_level)

        uv_config = uvicorn.Config(
            app=app,
            host=config.settings.host,
            port=config.settings.port,
            log_level=config.settings.log_level,
            log_config=None,      # ← disable uvicorn's own logging setup
            access_log=False,     # ← we handle our own access logging if needed
        )
        self._server = uvicorn.Server(uv_config)

        def run():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            try:
                self._loop.run_until_complete(self._server.serve())
            finally:
                self._running = False
                self._notify("stopped")

        self._thread = threading.Thread(target=run, daemon=True, name="gateway-server")
        self._thread.start()
        self._running = True
        self._notify("started")
        return True

    def stop(self):
        """Stop the gateway server"""
        if self._server and self._running:
            self._server.should_exit = True
            if self._loop:
                self._loop.call_soon_threadsafe(self._server.shutdown)
            if self._thread:
                self._thread.join(timeout=5)
            self._running = False
            self._notify("stopped")

    def reload(self, config: AppConfig):
        """Reload with new configuration"""
        global _proxy_engine, _app_config
        if _proxy_engine:
            _proxy_engine.update_config(config)
            _app_config = config
            self._notify("config_reloaded")
