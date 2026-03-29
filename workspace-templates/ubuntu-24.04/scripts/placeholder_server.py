#!/usr/bin/env python3
"""
Placeholder Preview Server

Returns a JSON response indicating the preview server is not configured.
This allows the frontend to display helpful messages to users.
"""

import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler


class PlaceholderHandler(BaseHTTPRequestHandler):
    """Handler that returns placeholder JSON responses."""

    def log_message(self, format, *args):
        """Suppress default logging to stderr."""
        pass

    def send_json_response(self, status_code, data):
        """Send a JSON response with CORS headers."""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()

    def do_GET(self):
        """Handle GET requests with placeholder response."""
        message = os.environ.get('PLACEHOLDER_MESSAGE', 'not_configured')
        detail = os.environ.get('PLACEHOLDER_DETAIL', 'Preview server not configured')

        response = {
            'status': 'placeholder',
            'message': message,
            'detail': detail,
            'hint': 'Create start_app.sh in your workspace to start a preview server. '
                    'Example: npm run dev -- --port 3000 --host 0.0.0.0'
        }

        self.send_json_response(503, response)

    def do_POST(self):
        """Handle POST requests same as GET."""
        self.do_GET()


def main():
    """Start the placeholder server on port 3000."""
    port = 3000
    host = '0.0.0.0'

    server = HTTPServer((host, port), PlaceholderHandler)
    print(f"Placeholder preview server running on {host}:{port}")
    server.serve_forever()


if __name__ == '__main__':
    main()