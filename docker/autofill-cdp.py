#!/usr/bin/env python3
"""
CDP-based autofill for GlobalProtect SAML authentication.
Handles the OneLogin SSO flow with Google Authenticator MFA.

Flow:
1. Okta redirect page -> auto-redirects to OneLogin
2. OneLogin password page (username pre-filled via login_hint)
3. MFA selection page -> select Google Authenticator
4. TOTP input page -> enter code and submit
"""
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
step_delay = int(os.environ.get('STEP_DELAY', 3))

if not all([username, password, totp_secret]):
    print("GP_USERNAME, GP_PASSWORD, and GP_TOTP_SECRET must be set")
    sys.exit(1)

def get_totp():
    """Generate current TOTP code."""
    result = subprocess.run(['oathtool', '--totp', '-b', totp_secret], capture_output=True, text=True)
    return result.stdout.strip()

def wait_for_devtools(timeout=120):
    """Wait for CDP DevTools to be available."""
    for i in range(timeout):
        try:
            r = requests.get('http://localhost:9222/json', timeout=2)
            if r.ok:
                pages = r.json()
                if pages:
                    return pages
        except Exception:
            pass
        if i % 10 == 0:
            print(f"Waiting for DevTools... ({i+1}/{timeout})")
        time.sleep(1)
    raise Exception("DevTools not available")

class CDPClient:
    """Chrome DevTools Protocol client."""
    
    def __init__(self, ws_url):
        self.ws = create_connection(ws_url, timeout=30)
        self.msg_id = 0
    
    def send(self, method, params=None):
        """Send a CDP command and wait for response."""
        self.msg_id += 1
        msg = {'id': self.msg_id, 'method': method}
        if params:
            msg['params'] = params
        self.ws.send(json.dumps(msg))
        
        while True:
            try:
                data = self.ws.recv()
                result = json.loads(data)
                if 'id' in result and result['id'] == self.msg_id:
                    if 'error' in result:
                        print(f"CDP Error: {result['error']}")
                    return result.get('result', {})
            except WebSocketTimeoutException:
                print("Timeout waiting for CDP response")
                return None
            except Exception as e:
                print(f"WebSocket error: {e}")
                return None
    
    def evaluate(self, js):
        """Evaluate JavaScript and return the result value."""
        result = self.send('Runtime.evaluate', {
            'expression': js,
            'returnByValue': True,
            'awaitPromise': False
        })
        if result and 'result' in result:
            return result['result'].get('value')
        return None
    
    def wait_for_element(self, selector, timeout=60):
        """Wait for an element to appear in the DOM."""
        print(f"Waiting for: {selector}")
        # Escape the selector for use in JavaScript
        js_selector = json.dumps(selector)
        for i in range(timeout):
            if self.evaluate(f'document.querySelector({js_selector}) !== null'):
                return True
            time.sleep(1)
        print(f"Timeout waiting for: {selector}")
        return False
    
    def wait_for_page_load(self, timeout=30):
        """Wait for the page to be fully loaded."""
        for i in range(timeout):
            root_len = self.evaluate('document.getElementById("root") ? document.getElementById("root").innerHTML.length : 0')
            if root_len and root_len > 100:
                return True
            time.sleep(1)
        return False
    
    def get_url(self):
        """Get current page URL."""
        return self.evaluate('window.location.href') or ''
    
    def get_page_text(self):
        """Get visible text content of the page."""
        return self.evaluate('document.body.innerText') or ''
    
    def fill_input(self, selector, value):
        """Fill an input field with proper event dispatch for React."""
        js_selector = json.dumps(selector)
        js_value = json.dumps(value)
        return self.evaluate(f'''
            (function() {{
                var input = document.querySelector({js_selector});
                if (!input) return false;
                input.focus();
                input.value = {js_value};
                input.dispatchEvent(new Event('input', {{bubbles: true}}));
                input.dispatchEvent(new Event('change', {{bubbles: true}}));
                return true;
            }})()
        ''')
    
    def click(self, selector):
        """Click an element."""
        js_selector = json.dumps(selector)
        return self.evaluate(f'''
            (function() {{
                var el = document.querySelector({js_selector});
                if (el) {{ el.click(); return true; }}
                return false;
            }})()
        ''')
    
    def click_by_text(self, text):
        """Click an element containing specific text."""
        js_text = json.dumps(text)
        return self.evaluate(f'''
            (function() {{
                var elements = document.querySelectorAll('a, button, div[role="button"], li, span');
                for (var el of elements) {{
                    if (el.textContent.includes({js_text})) {{
                        el.click();
                        return true;
                    }}
                }}
                return false;
            }})()
        ''')
    
    def close(self):
        """Close the WebSocket connection."""
        self.ws.close()


def handle_okta_username(cdp):
    """Handle Okta username/identifier entry page."""
    print("Step: Entering username on Okta...")
    
    # Check if username/identifier field exists
    if cdp.wait_for_element('input[name="identifier"], input[name="username"]', timeout=10):
        if cdp.fill_input('input[name="identifier"], input[name="username"]', username):
            print("Username entered")
            time.sleep(1)
            
            # Click submit
            if cdp.click('input[type="submit"], button[type="submit"]'):
                print("Clicked submit")
                return True
    
    return False


def handle_onelogin_password(cdp):
    """Handle OneLogin password entry page."""
    print("Step: Entering password on OneLogin...")
    
    # Wait for the page to render
    if not cdp.wait_for_page_load(timeout=30):
        print("Warning: Page may not have fully loaded")
    
    time.sleep(step_delay)
    
    # Check if password field exists (username may be pre-filled)
    if cdp.wait_for_element('input[name="password"], input#password', timeout=30):
        if cdp.fill_input('input[name="password"], input#password', password):
            print("Password entered")
            time.sleep(1)
            
            # Click submit/continue
            if cdp.click('button[type="submit"]'):
                print("Clicked submit")
                return True
    
    return False


def handle_mfa_selection(cdp):
    """Handle MFA method selection page."""
    print("Step: Selecting MFA method...")
    time.sleep(step_delay)
    
    page_text = cdp.get_page_text()
    
    # Check if we're on MFA selection page
    if 'Select Authentication Factor' in page_text or 'Change Authentication Factor' in page_text:
        # First click "Change Authentication Factor" if YubiKey is default
        if 'YubiKey' in page_text and 'Enter your code' not in page_text:
            if 'Change Authentication Factor' in page_text:
                print("Changing authentication factor...")
                cdp.click_by_text('Change Authentication Factor')
                time.sleep(step_delay)
    
    # Now select Google Authenticator
    page_text = cdp.get_page_text()
    if 'Google Authenticator' in page_text:
        print("Selecting Google Authenticator...")
        cdp.click_by_text('Google Authenticator')
        return True
    
    return False


def handle_totp_entry(cdp):
    """Handle TOTP code entry page."""
    print("Step: Entering TOTP code...")
    time.sleep(step_delay)
    
    # Wait for TOTP input
    if cdp.wait_for_element('input#security-code, input[name="otp"], input[type="tel"]', timeout=30):
        totp = get_totp()
        print(f"Generated TOTP: {totp}")
        
        if cdp.fill_input('input#security-code, input[name="otp"], input[type="tel"]', totp):
            print("TOTP entered")
            time.sleep(1)
            
            if cdp.click('button[type="submit"]'):
                print("Clicked submit")
                return True
    
    return False


def main():
    print("Starting autofill...")
    print(f"Step delay: {step_delay}s")
    
    # Wait for DevTools
    print("Waiting for DevTools...")
    pages = wait_for_devtools()
    
    page = None
    for p in pages:
        if 'webSocketDebuggerUrl' in p:
            page = p
            break
    
    if not page:
        print("No page found")
        return
    
    print(f"Page: {page.get('title', 'Unknown')} - {page.get('url', '')[:60]}...")
    print(f"Connecting to CDP...")
    cdp = CDPClient(page['webSocketDebuggerUrl'])
    
    # Wait for initial page load
    time.sleep(step_delay)
    
    # Main authentication loop - handle multiple pages/steps
    max_steps = 10
    for step in range(max_steps):
        try:
            url = cdp.get_url()
            page_text = cdp.get_page_text()
            print(f"\n--- Step {step + 1} ---")
            print(f"URL: {url[:80]}...")
            print(f"Page text preview: {page_text[:100]}...")
        except Exception as e:
            print(f"Could not get page info: {e}")
            # CDP connection might be lost (page closed/redirected)
            break
        
        # Detect which page we're on and handle it
        if 'onelogin.com' in url:
            if 'Enter your code' in page_text:
                # TOTP entry page
                if handle_totp_entry(cdp):
                    print("TOTP submitted, waiting for redirect...")
                    time.sleep(step_delay * 2)
            elif 'Select Authentication Factor' in page_text or ('YubiKey' in page_text and 'Google Authenticator' in page_text):
                # MFA selection page
                handle_mfa_selection(cdp)
                time.sleep(step_delay)
            elif 'Change Authentication Factor' in page_text and 'YubiKey' in page_text:
                # Default MFA is YubiKey, need to change
                handle_mfa_selection(cdp)
                time.sleep(step_delay)
            elif cdp.evaluate('document.querySelector("input[name=password], input#password") !== null'):
                # Password entry page
                if handle_onelogin_password(cdp):
                    time.sleep(step_delay)
            else:
                print("Unknown OneLogin page state, waiting...")
                time.sleep(step_delay)
        
        elif 'okta.com' in url:
            # Okta page - check if we need to enter username
            if cdp.evaluate('document.querySelector("input[name=identifier], input[name=username]") !== null'):
                print("Okta login page detected, entering username...")
                if handle_okta_username(cdp):
                    time.sleep(step_delay)
            else:
                # Okta SSO redirect page - usually auto-redirects
                print("On Okta redirect page, waiting for redirect...")
                time.sleep(step_delay)
        
        else:
            print(f"Unknown page, waiting...")
            time.sleep(step_delay)
    
    print("\nAutofill complete")
    try:
        cdp.close()
    except:
        pass


if __name__ == '__main__':
    main()
