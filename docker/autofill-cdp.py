#!/usr/bin/env python3
import json
import time
import os
import subprocess
import sys
import requests
from websocket import create_connection, WebSocketTimeoutException

# Get env vars
username = os.environ.get('GP_USERNAME')
password = os.environ.get('GP_PASSWORD')  
totp_secret = os.environ.get('GP_TOTP_SECRET')
step_delay = int(os.environ.get('STEP_DELAY', 5))

if not all([username, password, totp_secret]):
    print("GP_USERNAME, GP_PASSWORD, and GP_TOTP_SECRET must be set")
    sys.exit(1)

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

class CDPConnection:
    def __init__(self, ws_url):
        self.ws = create_connection(ws_url, timeout=30)
        self.msg_id = 0
    
    def send_command(self, method, params=None):
        self.msg_id += 1
        msg = {'id': self.msg_id, 'method': method}
        if params:
            msg['params'] = params
        self.ws.send(json.dumps(msg))
        
        # Wait for response with matching ID
        while True:
            try:
                data = self.ws.recv()
                result = json.loads(data)
                # Skip events (they have 'method' key)
                if 'id' in result and result['id'] == self.msg_id:
                    if 'error' in result:
                        print(f"CDP Error: {result['error']}")
                    return result.get('result', {})
            except WebSocketTimeoutException:
                print(f"Timeout waiting for CDP response")
                return None
            except Exception as e:
                print(f"WebSocket error: {e}")
                return None
    
    def evaluate(self, expression):
        result = self.send_command('Runtime.evaluate', {
            'expression': expression,
            'returnByValue': True,
            'awaitPromise': False
        })
        if result and 'result' in result:
            return result['result'].get('value')
        return None
    
    def close(self):
        self.ws.close()

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
    cdp = CDPConnection(page['webSocketDebuggerUrl'])
    
    # Initial delay to let page load
    time.sleep(step_delay)
    
    # Helper function to wait for an element
    def wait_for_element(selector, timeout=60):
        print(f"Waiting for element: {selector}")
        for i in range(timeout):
            result = cdp.evaluate(f'document.querySelector("{selector}") !== null')
            if result:
                print(f"Found element: {selector}")
                return True
            time.sleep(1)
        print(f"Timeout waiting for element: {selector}")
        return False
    
    # Get current URL to understand which page we're on
    url = cdp.evaluate('window.location.href')
    print(f"Current URL: {url}")
    
    # Step 1: Fill username
    print("Step 1: Filling username...")
    # Wait for any input to appear (page needs to fully render)
    wait_for_element('input[name="username"], input[type="email"], input#username, input[type="text"]')
    
    js_username = json.dumps(username)
    filled = cdp.evaluate(f'''
        (function() {{
            var input = document.querySelector('input[name="username"], input[type="email"], input#username, input[autocomplete="username"], input[type="text"]');
            if (input) {{ 
                input.focus();
                input.value = {js_username}; 
                input.dispatchEvent(new Event('input', {{bubbles: true}}));
                input.dispatchEvent(new Event('change', {{bubbles: true}}));
                console.log('Username filled');
                return true;
            }}
            console.log('Username input not found');
            return false;
        }})()
    ''')
    print(f"Username filled: {filled}")
    
    # Click continue/next button
    cdp.evaluate('''
        (function() {
            var btn = document.querySelector('input[type="submit"], button[type="submit"], button.button--primary, #okta-signin-submit');
            if (btn) { btn.click(); return true; }
            return false;
        })()
    ''')
    
    time.sleep(step_delay)
    
    # Check URL to see if we moved to password page or OneLogin
    url = cdp.evaluate('window.location.href')
    print(f"After username, URL: {url}")
    
    # Step 2: Fill password
    print("Step 2: Filling password...")
    # Wait for password input to appear
    wait_for_element('input[name="password"], input[type="password"]')
    
    js_password = json.dumps(password)
    filled = cdp.evaluate(f'''
        (function() {{
            var input = document.querySelector('input[name="password"], input[type="password"]');
            if (input) {{ 
                input.focus();
                input.value = {js_password}; 
                input.dispatchEvent(new Event('input', {{bubbles: true}}));
                input.dispatchEvent(new Event('change', {{bubbles: true}}));
                console.log('Password filled');
                return true;
            }}
            console.log('Password input not found');
            return false;
        }})()
    ''')
    print(f"Password filled: {filled}")
    
    # Click submit
    cdp.evaluate('''
        (function() {
            var btn = document.querySelector('input[type="submit"], button[type="submit"], button.button--primary, #okta-signin-submit');
            if (btn) { btn.click(); return true; }
            return false;
        })()
    ''')
    
    time.sleep(step_delay)
    
    # Check URL after password
    url = cdp.evaluate('window.location.href')
    print(f"After password, URL: {url}")
    
    # Step 3: Select MFA method (Google Authenticator)
    print("Step 3: Selecting MFA method...")
    cdp.evaluate('''
        (function() {
            // Look for Google Authenticator option
            var options = document.querySelectorAll('a[data-se], button[data-se], .authenticator-row, [data-factor]');
            for (var opt of options) {
                var text = (opt.textContent || '').toLowerCase();
                var dataSe = (opt.getAttribute('data-se') || '').toLowerCase();
                if (text.includes('google') || text.includes('authenticator') || dataSe.includes('google')) {
                    opt.click();
                    console.log('Selected MFA option');
                    return true;
                }
            }
            // Also try clicking any visible OTP/TOTP link
            var links = document.querySelectorAll('a, button');
            for (var link of links) {
                var text = (link.textContent || '').toLowerCase();
                if (text.includes('otp') || text.includes('totp') || text.includes('authenticator')) {
                    link.click();
                    return true;
                }
            }
            return false;
        })()
    ''')
    
    time.sleep(step_delay)
    
    # Step 4: Confirm MFA (if there's a verify button)
    print("Step 4: Confirming MFA selection...")
    cdp.evaluate('''
        (function() {
            var btn = document.querySelector('input[type="submit"], button[type="submit"], button.button--primary, [data-type="save"]');
            if (btn) { btn.click(); return true; }
            return false;
        })()
    ''')
    
    time.sleep(step_delay)
    
    # Step 5: Fill TOTP
    print("Step 5: Filling TOTP...")
    totp = get_totp()
    print(f"Generated TOTP: {totp}")
    js_totp = json.dumps(totp)
    cdp.evaluate(f'''
        (function() {{
            var input = document.querySelector('input[name="answer"], input[name="otp"], input[name="totp"], input[name="passcode"], input[type="tel"], input.otp-input, input#otp');
            if (input) {{ 
                input.focus();
                input.value = {js_totp}; 
                input.dispatchEvent(new Event('input', {{bubbles: true}}));
                input.dispatchEvent(new Event('change', {{bubbles: true}}));
                console.log('TOTP filled');
                return true;
            }}
            console.log('TOTP input not found');
            return false;
        }})()
    ''')
    
    # Click verify
    cdp.evaluate('''
        (function() {
            var btn = document.querySelector('input[type="submit"], button[type="submit"], button.button--primary, [data-type="save"]');
            if (btn) { btn.click(); return true; }
            return false;
        })()
    ''')
    
    time.sleep(step_delay)
    print("Credentials submitted")
    cdp.close()

if __name__ == '__main__':
    main()
