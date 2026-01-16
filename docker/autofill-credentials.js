const { chromium } = require('playwright');
const { execSync } = require('child_process');

const GP_PORTAL = process.env.GP_PORTAL;
const GP_USERNAME = process.env.GP_USERNAME;
const GP_PASSWORD = process.env.GP_PASSWORD;
const GP_TOTP_SECRET = process.env.GP_TOTP_SECRET;
const CDP_PORT = process.env.QTWEBENGINE_REMOTE_DEBUGGING || '9222';

if (!GP_PORTAL || !GP_USERNAME || !GP_PASSWORD || !GP_TOTP_SECRET) {
    console.error('GP_PORTAL, GP_USERNAME, GP_PASSWORD, and GP_TOTP_SECRET must be set');
    process.exit(1);
}

function generateTOTP() {
    return execSync(`oathtool --totp -b "${GP_TOTP_SECRET}"`).toString().trim();
}

async function waitForCDP(maxRetries = 30, interval = 2000) {
    for (let i = 0; i < maxRetries; i++) {
        try {
            const response = await fetch(`http://127.0.0.1:${CDP_PORT}/json/version`);
            if (response.ok) {
                console.log('CDP server is ready');
                return true;
            }
        } catch (e) {
        }
        console.log(`Waiting for CDP server... (${i + 1}/${maxRetries})`);
        await new Promise(r => setTimeout(r, interval));
    }
    throw new Error('CDP server not available');
}

async function main() {
    await waitForCDP();
    
    await new Promise(r => setTimeout(r, 3000));
    
    console.log('Connecting to QtWebEngine via CDP...');
    const browser = await chromium.connectOverCDP(`http://127.0.0.1:${CDP_PORT}`);
    
    const contexts = browser.contexts();
    if (contexts.length === 0) {
        throw new Error('No browser contexts found');
    }
    
    const context = contexts[0];
    const pages = context.pages();
    if (pages.length === 0) {
        throw new Error('No pages found');
    }
    
    const page = pages[0];
    console.log('Connected to page:', await page.title());

    console.log('Filling portal URL...');
    const portalInput = await page.waitForSelector('input[type="text"], input[name="portal"], input[placeholder*="portal" i]', { timeout: 30000 });
    await portalInput.fill(GP_PORTAL);
    
    const connectButton = await page.waitForSelector('button:has-text("Connect"), input[type="submit"], button[type="submit"]', { timeout: 5000 });
    await connectButton.click();

    console.log('Waiting for OneLogin login page...');
    await page.waitForSelector('input[name="username"], input[id="username"], input[type="email"]', { timeout: 30000 });
    
    console.log('Filling username...');
    const usernameInput = await page.waitForSelector('input[name="username"], input[id="username"], input[type="email"]');
    await usernameInput.fill(GP_USERNAME);
    
    const continueButton = await page.waitForSelector('button:has-text("Continue"), button[type="submit"], input[type="submit"]', { timeout: 5000 });
    await continueButton.click();

    console.log('Waiting for password field...');
    await page.waitForSelector('input[name="password"], input[id="password"], input[type="password"]', { timeout: 30000 });
    
    console.log('Filling password...');
    const passwordInput = await page.waitForSelector('input[name="password"], input[id="password"], input[type="password"]');
    await passwordInput.fill(GP_PASSWORD);
    
    const submitButton = await page.waitForSelector('button:has-text("Continue"), button:has-text("Sign In"), button:has-text("Log In"), button[type="submit"]', { timeout: 5000 });
    await submitButton.click();

    console.log('Waiting for MFA selection...');
    await page.waitForTimeout(3000);
    
    const googleAuthOption = await page.waitForSelector('text=Google Authenticator, text=Authenticator, [data-mfa="google"]', { timeout: 30000 });
    await googleAuthOption.click();

    console.log('Waiting for TOTP input...');
    await page.waitForTimeout(2000);
    
    const totpInput = await page.waitForSelector('input[name="otp"], input[name="totp"], input[name="code"], input[type="tel"], input[placeholder*="code" i]', { timeout: 30000 });
    
    const totpCode = generateTOTP();
    console.log('Entering TOTP code...');
    await totpInput.fill(totpCode);
    
    const verifyButton = await page.waitForSelector('button:has-text("Verify"), button:has-text("Continue"), button:has-text("Submit"), button[type="submit"]', { timeout: 5000 });
    await verifyButton.click();

    console.log('Credentials submitted successfully');
    
    await browser.close();
}

main().catch(err => {
    console.error('Error:', err.message);
    process.exit(1);
});
