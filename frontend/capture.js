const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({
    viewport: { width: 820, height: 1180 }
  });
  await page.goto('http://localhost:5173');
  await page.waitForTimeout(2000); // Wait for animations/load
  await page.screenshot({ path: 'ipad_820_debug.png' });
  await browser.close();
})();
