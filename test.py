#!/usr/bin/env python3
"""Quick connection diagnostic"""
import requests
import socketio
import sys

URL = "https://ss4j58hs-4440.inc1.devtunnels.ms"

print(f"\n{'='*60}")
print(f"Testing: {URL}")
print(f"{'='*60}\n")

# Test 1: Basic HTTP
print("1. Testing basic HTTP connection...")
try:
    response = requests.get(URL, timeout=10, verify=True)
    print(f"   ✓ Connected! Status: {response.status_code}")
    print(f"   Headers: {dict(list(response.headers.items())[:3])}")
except requests.exceptions.SSLError as e:
    print(f"   ✗ SSL Error: {e}")
    print(f"   Trying without SSL verification...")
    try:
        response = requests.get(URL, timeout=10, verify=False)
        print(f"   ✓ Connected WITHOUT SSL verification: {response.status_code}")
        print(f"   ⚠️ SSL certificate issue detected!")
    except Exception as e2:
        print(f"   ✗ Still failed: {e2}")
except requests.exceptions.ConnectionError as e:
    print(f"   ✗ Connection Error: {e}")
    print(f"   Backend might not be running at this URL")
except Exception as e:
    print(f"   ✗ Failed: {e}")
    sys.exit(1)

# Test 2: Health endpoint
print("\n2. Testing /health endpoint...")
try:
    response = requests.get(f"{URL}/health", timeout=10, verify=False)
    print(f"   ✓ Health check: {response.status_code}")
    print(f"   Response: {response.text[:200]}")
except Exception as e:
    print(f"   ✗ Health check failed: {e}")

# Test 3: Socket.IO info
print("\n3. Testing Socket.IO endpoint...")
try:
    response = requests.get(f"{URL}/socket.io/?EIO=4&transport=polling", timeout=10, verify=False)
    print(f"   ✓ Socket.IO polling: {response.status_code}")
    print(f"   Response: {response.text[:100]}")
except Exception as e:
    print(f"   ✗ Socket.IO endpoint failed: {e}")

# Test 4: Socket.IO connection
print("\n4. Testing Socket.IO connection...")
try:
    sio = socketio.Client(logger=True, engineio_logger=True)
    
    @sio.event
    def connect():
        print(f"   ✓ Socket.IO CONNECTED!")
        sio.disconnect()
    
    @sio.event
    def connect_error(data):
        print(f"   ✗ Socket.IO connect_error: {data}")
    
    print(f"   Attempting connection...")
    sio.connect(
        URL, 
        transports=['polling', 'websocket'],
        wait_timeout=10
    )
    
except Exception as e:
    print(f"   ✗ Socket.IO failed: {e}")
    print(f"\n   Common causes:")
    print(f"   - Backend not running")
    print(f"   - CORS blocking the connection")
    print(f"   - Firewall blocking websocket/polling")
    print(f"   - Wrong Socket.IO version mismatch")

print(f"\n{'='*60}\n")