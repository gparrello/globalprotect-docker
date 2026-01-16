const { chromium } = require('playwright');
const { execSync } = require('child_process');

const GP_USERNAME = process.env.GP_USERNAME;
const GP_PASSWORD = process.env.GP_PASSWORD;
const GP_TOTP_SECRET = process.env.GP_TOTP_SECRET;
const CDP_PORT = process.env.QTWEBENGINE_REMOTE_DEBUGGING || '9222';

if (!GP_USERNAME || !GP_PASSWORD || !GP_TOTP_SECRET) {
    console.error('GP_USERNAME, GP_PASSWORD, and GP_TOTP_SECRET must be set');
    process.exit(1);
}

function generateTOTP() {
    return execSync(`oathtool --totp -b "${GP_TOTP_SECRET}"`).toString().trim();
}

async function main() {
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

    console.log('Waiting for OneLogin username field...');
    const usernameInput = await page.waitForSelector('input[name="username"], input[id="username"], input[type="email"], input[name="login"]', { timeout: 60000 });
    
    console.log('Filling username...');
    await usernameInput.fill(GP_USERNAME);
    
    const continueButton = await page.waitForSelector('button[type="submit"], input[type="submit"]', { timeout: 5000 });
    await continueButton.click();

    console.log('Waiting for password field...');
    const passwordInput = await page.waitForSelector('input[type="password"]', { timeout: 30000 });
    
    console.log('Filling password...');
    await passwordInput.fill(GP_PASSWORD);
    
    const submitButton = await page.waitForSelector('button[type="submit"], input[type="submit"]', { timeout: 5000 });
    await submitButton.click();

    console.log('Waiting for MFA page...');
    await page.waitForTimeout(3000);
    
    const googleAuthOption = await page.waitForSelector('text=Google Authenticator, text=Authenticator, [data-mfa*="google" i], .mfa-google, a:has-text("Google")', { timeout: 30000 }).catch(() => null);
    if (googleAuthOption) {
        console.log('Selecting Google Authenticator...');
        await googleAuthOption.click();
        await page.waitForTimeout(2000);
    }

    console.log('Waiting for TOTP input...');
    const totpInput = await page.waitForSelector('input[name="otp_token"], input[name="otp"], input[name="totp"], input[name="code"], input[type="tel"], input[inputmode="numeric"]', { timeout: 30000 });
    
    const totpCode = generateTOTP();
    console.log('Entering TOTP code...');
    await totpInput.fill(totpCode);
    
    const verifyButton = await page.waitForSelector('button[type="submit"], input[type="submit"]', { timeout: 5000 });
    await verifyButton.click();

    console.log('Authentication submitted successfully');
    
    await page.waitForTimeout(5000);
    await browser.close();
}

main().catch(err => {
    console.error('Error:', err.message);
    process.exit(1);
});
