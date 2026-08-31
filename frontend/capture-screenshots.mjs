import { chromium, devices } from '@playwright/test';

(async () => {
  const browser = await chromium.launch();
  
  // Desktop
  const desktopContext = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    colorScheme: 'dark'
  });
  const desktopPage = await desktopContext.newPage();
  
  const initPage = async (page) => {
    await page.goto('http://127.0.0.1:4273');
    await page.evaluate(() => { 
      localStorage.setItem('i18nextLng', 'vi'); 
      localStorage.setItem('all-voice-language', 'vi');
    });
  };

  console.log('Capturing Desktop...');
  await initPage(desktopPage);
  
  await desktopPage.goto('http://127.0.0.1:4273', { waitUntil: 'networkidle' });
  // Find the button inside the tab switcher for community/support
  await desktopPage.locator('button').filter({ hasText: 'Ủng hộ' }).click().catch(() => {});
  await desktopPage.locator('button').filter({ hasText: 'Cộng đồng' }).click().catch(() => {});
  await desktopPage.waitForTimeout(500);
  await desktopPage.screenshot({ path: '../assets/screenshots/tts-page-desktop.png' });

  await desktopPage.goto('http://127.0.0.1:4273/transcribe', { waitUntil: 'networkidle' });
  await desktopPage.screenshot({ path: '../assets/screenshots/transcribe-page-desktop.png' });

  await desktopPage.goto('http://127.0.0.1:4273/clone', { waitUntil: 'networkidle' });
  await desktopPage.screenshot({ path: '../assets/screenshots/clone-page-desktop.png' });
  await desktopContext.close();

  // Mobile
  console.log('Capturing Mobile...');
  const iPhone = devices['iPhone 12'];
  const mobileContext = await browser.newContext({
    ...iPhone,
    colorScheme: 'dark'
  });
  const mobilePage = await mobileContext.newPage();
  await initPage(mobilePage);

  await mobilePage.goto('http://127.0.0.1:4273', { waitUntil: 'networkidle' });
  await mobilePage.screenshot({ path: '../assets/screenshots/tts-page-mobile.png' });
  await mobileContext.close();

  await browser.close();
  console.log("Screenshots captured successfully!");
})();
