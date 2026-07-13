"""
SunoSync Token Server — Local HTTP server for Chrome extension communication.

Listens on 127.0.0.1:38945 for token pushes from the SunoSync Chrome Extension.
Thread-safe, non-blocking, and integrates with the main app via callbacks.
"""

import json
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler

logger = logging.getLogger(__name__)

TOKEN_SERVER_HOST = "127.0.0.1"
TOKEN_SERVER_PORT = 38945


class _TokenHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the token server."""

    def log_message(self, format, *args):
        """Suppress default stderr logging; use our logger instead."""
        logger.debug("TokenServer: %s", format % args)

    def _send_cors_headers(self):
        """Allow requests from Chrome extensions."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        """GET /status — Health check endpoint."""
        if self.path == "/status":
            self._send_json(200, {"running": True, "app": "SunoSync"})
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        """POST /token — Receive a token from the Chrome extension."""
        if self.path != "/token":
            self._send_json(404, {"error": "Not found"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self._send_json(400, {"error": "Empty body"})
                return

            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))
            token = data.get("token", "").strip()

            if not token:
                self._send_json(400, {"error": "No token provided"})
                return

            # Store token and fire callbacks
            server = self.server
            token_changed = False
            with server.token_lock:
                if server.current_token != token:
                    server.current_token = token
                    token_changed = True

            # Fire callbacks (outside the lock to avoid deadlocks)
            # Only fire if changed or if it's the first time (implied by changed=True if init is None)
            if token_changed:
                for callback in server.token_callbacks:
                    try:
                        callback(token)
                    except Exception as e:
                        logger.error("Token callback error: %s", e)
                
                logger.info("Token received from Chrome extension (%d chars) [NEW]", len(token))
            else:
                logger.debug("Token received (unchanged)")

            self._send_json(200, {"success": True})

        except json.JSONDecodeError:
            self._send_json(400, {"error": "Invalid JSON"})
        except Exception as e:
            logger.error("Token server error: %s", e)
            self._send_json(500, {"error": str(e)})


class TokenServer:
    """
    Local HTTP server that receives Suno authentication tokens
    from the SunoSync Chrome Extension.
    
    Usage:
        server = TokenServer()
        server.on_token(lambda token: print("Got token:", token[:20] + "..."))
        server.start()
        # ... later ...
        server.stop()
    """

    def __init__(self, host=TOKEN_SERVER_HOST, port=TOKEN_SERVER_PORT):
        self.host = host
        self.port = port
        self._httpd = None
        self._thread = None
        self._running = False

    def stop(self):
        """Stop the token server."""
        if self._httpd:
            self._httpd.shutdown()
            # Release the listening socket so a later restart in the same
            # process doesn't hit "address already in use" on the port.
            self._httpd.server_close()
            self._httpd = None
            self._running = False
            logger.info("Token server stopped")

    def on_token(self, callback):
        """
        Register a callback to be called when a new token is received.
        
        Args:
            callback: A callable that takes a single string argument (the token).
        """
        if self._httpd:
            self._httpd.token_callbacks.append(callback)
        else:
            # Server not started yet — store for later
            if not hasattr(self, '_pending_callbacks'):
                self._pending_callbacks = []
            self._pending_callbacks.append(callback)

    def _flush_pending_callbacks(self):
        """Move any callbacks registered before start() to the server."""
        if hasattr(self, '_pending_callbacks') and self._httpd:
            for cb in self._pending_callbacks:
                self._httpd.token_callbacks.append(cb)
            self._pending_callbacks.clear()

    def start(self):
        """Start the token server on a background thread."""
        if self._running:
            logger.warning("Token server is already running")
            return

        try:
            self._httpd = HTTPServer((self.host, self.port), _TokenHandler)
            self._httpd.token_lock = threading.Lock()
            self._httpd.current_token = None
            self._httpd.token_callbacks = []

            # Flush any callbacks registered before start()
            self._flush_pending_callbacks()

            self._thread = threading.Thread(
                target=self._httpd.serve_forever,
                daemon=True,
                name="SunoSync-TokenServer"
            )
            self._thread.start()
            self._running = True
            logger.info("Token server started on %s:%d", self.host, self.port)
        except OSError as e:
            if "address already in use" in str(e).lower() or "10048" in str(e):
                logger.warning("Token server port %d already in use", self.port)
            else:
                logger.error("Failed to start token server: %s", e)

    @property
    def is_running(self):
        return self._running

    @property
    def current_token(self):
        """Get the last received token (thread-safe)."""
        if self._httpd:
            with self._httpd.token_lock:
                return self._httpd.current_token
        return None
