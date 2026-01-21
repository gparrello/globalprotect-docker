#!/usr/bin/env python3
import json
import time
import os
import subprocess
import requests
from websocket import create_connection

# Get env vars
username = os.environ.get('GP_USERNAME')
password = os.environ.get('GP_PASSWORD')  
totp_secret = os.environ.get('GP_TOTP_SECRET')
step_delay = int(os.environ.get('STEP_DELAY', 5))

if not all([username, password, totp_secret]):
    print("GP_USERNAME, GP_PASSWORD, and GP_TOTP_SECRET must be set")
    exit(1)

def get_totp():
    result = subprocess.run(['oathtool', '--totp', '-b', totp_secret], capture_output=True, text=True)
    return result.stdout.strip()

def wait_for_devtools():
    for i in range(60):
        try:
            r = requests.get('http://localhost:9222/json', timeout=2)
            if r.ok:
                pages = r.json()
                if pages:
                    return pages
        except Exception:
            pass
        print(f"Waiting for DevTools... ({i+1}/60)")
        time.sleep(1)
    raise Exception("DevTools not available")

def evaluate_js(ws, expression):
    msg_id = int(time.time() * 1000)
    ws.send(json.dumps({
        'id': msg_id,
        'method': 'Runtime.evaluate',
        'params': {'expression': expression, 'returnByValue': True}
    }))
    # Read response
    while True:
        result = json.loads(ws.recv())
        if result.get('id') == msg_id:
            return result

def main():
    print("Waiting for DevTools...")
    pages = wait_for_devtools()
    
    # Find the SAML page
    page = None
    for p in pages:
        if 'webSocketDebuggerUrl' in p:
            page = p
            break
    
    if not page:
        print("No page found")
        return
    
    print(f"Connecting to {page['webSocketDebuggerUrl']}")
    ws = create_connection(page['webSocketDebuggerUrl'])
    
    # Enable Runtime
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.enable'}))
    ws.recv()
    
    time.sleep(step_delay)
    
    # Step 1: Fill username (OneLogin has input with name="username" or similar)
    print("Step 1: Filling username...")
    # Escape password and username for JS
    js_username = json.dumps(username)
    evaluate_js(ws, f'''
        (function() {{
            var input = document.querySelector('input[name="username"], input[type="email"], input#username');
            if (input) {{ 
                input.value = {js_username}; 
                input.dispatchEvent(new Event('input', {{bubbles: true}}));
                input.dispatchEvent(new Event('change', {{bubbles: true}}));
            }}
        }})()
    ''')
    
    # Click continue/next
    evaluate_js(ws, '''
        (function() {
            var btn = document.querySelector('button[type="submit"], input[type="submit"], button.btn-primary, #login-button');
            if (btn) btn.click();
        })()
    ''')
    
    time.sleep(step_delay)
    
    # Step 2: Fill password
    print("Step 2: Filling password...")
    js_password = json.dumps(password)
    evaluate_js(ws, f'''
        (function() {{
            var input = document.querySelector('input[name="password"], input[type="password"]');
            if (input) {{ 
                input.value = {js_password}; 
                input.dispatchEvent(new Event('input', {{bubbles: true}}));
                input.dispatchEvent(new Event('change', {{bubbles: true}}));
            }}
        }})()
    ''')
    
    evaluate_js(ws, '''
        (function() {
            var btn = document.querySelector('button[type="submit"], input[type="submit"], button.btn-primary, #login-button');
            if (btn) btn.click();
        })()
    ''')
    
    time.sleep(step_delay)
    
    # Step 3-4: Select MFA method (Google Authenticator)
    print("Step 3: Selecting MFA method...")
    evaluate_js(ws, '''
        (function() {
            var options = document.querySelectorAll('.mfa-option, [data-mfa], button, a');
            for (var opt of options) {
                var text = opt.textContent.toLowerCase();
                if (text.includes('google') || text.includes('authenticator') || text.includes('otp')) {
                    opt.click();
                    break;
                }
            }
        })()
    ''')
    
    time.sleep(step_delay)
    
    # Step 5: Fill TOTP
    print("Step 5: Filling TOTP...")
    totp = get_totp()
    print(f"Generated TOTP: {totp}")
    js_totp = json.dumps(totp)
    evaluate_js(ws, f'''
        (function() {{
            var input = document.querySelector('input[name="otp"], input[name="totp"], input[type="tel"], input.otp-input, input#otp');
            if (input) {{ 
                input.value = {js_totp}; 
                input.dispatchEvent(new Event('input', {{bubbles: true}}));
                input.dispatchEvent(new Event('change', {{bubbles: true}}));
            }}
        }})()
    ''')
    
    evaluate_js(ws, '''
        (function() {
            var btn = document.querySelector('button[type="submit"], input[type="submit"], button.btn-primary, #verify-button');
            if (btn) btn.click();
        })()
    ''')
    
    time.sleep(step_delay)
    print("Credentials submitted")
    ws.close()

if __name__ == '__main__':
    main()
