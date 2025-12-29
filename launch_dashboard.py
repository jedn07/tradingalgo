"""
Dashboard Launcher
Runs backtest and automatically opens the dashboard
"""

import webbrowser
import http.server
import socketserver
import threading
import time


def start_server(port=8000):
    """Start a simple HTTP server in the background"""
    Handler = http.server.SimpleHTTPRequestHandler
    Handler.extensions_map.update({
        '.csv': 'text/csv',
    })
    
    httpd = socketserver.TCPServer(("", port), Handler)
    
    # Run server in a daemon thread so it doesn't block
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()


def main():
    """Main function to run backtest and launch dashboard"""
    print("="*60)
    print("BACKTEST DASHBOARD LAUNCHER")
    print("="*60)
    
    # Import and run backtest
    import engine
    
    print("\nStarting local web server...")
    port = 8000
    start_server(port)
    print(f"Server started at http://localhost:{port}")

    print("\nOpening dashboard in browser...")
    
    # Open in browser
    webbrowser.open(f'http://localhost:{port}/dashboard.html')
    
    print("\n" + "="*60)
    print("DASHBOARD LAUNCHED")
    print("="*60)
    print(f"\nDashboard URL: http://localhost:{port}/dashboard.html")
    print("="*60)
    
    try:
        # Keep the script running so the server stays alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n✓ Server stopped. Goodbye!")


if __name__ == "__main__":
    main()