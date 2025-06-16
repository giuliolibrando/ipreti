#!/usr/bin/env python3
"""
Test script per verificare la connessione con le API Django
"""

import requests
import json

# Configuration
API_BASE_URL = "http://localhost:8000/api"

def test_api_connection():
    """Test basic API connectivity"""
    try:
        # Test health endpoint
        response = requests.get("http://localhost:8000/health/")
        print(f"Health check: {response.status_code} - {response.json()}")
        
        # Test IP list endpoint
        response = requests.get(f"{API_BASE_URL}/ips/")
        print(f"IP List: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Total IPs: {data.get('count', 0)}")
            print(f"First IP: {data.get('results', [{}])[0].get('ip', 'None') if data.get('results') else 'None'}")
        
        # Test compatibility endpoint
        response = requests.get(f"{API_BASE_URL}/ips/getbyip/?title=192.168.1.1")
        print(f"GetByIP (Drupal compat): {response.status_code}")
        
        return True
        
    except Exception as e:
        print(f"API test failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing Django API connection...")
    success = test_api_connection()
    print(f"Test {'PASSED' if success else 'FAILED'}") 