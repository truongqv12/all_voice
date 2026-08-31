import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';

test.describe('Phase 6: Functional QA', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('TC1: Voices filter and display', async ({ page }) => {
    await expect(page.locator('article').first()).toBeVisible();
    await expect(page.getByText('Nữ', { exact: true })).toHaveCount(0);
    await expect(page.getByText('Nam', { exact: true })).toHaveCount(0);
  });

  test('TC2: Preview audio', async ({ page }) => {
    const playBtn = page.locator('article').first().locator('button').first();
    const [response] = await Promise.all([
      page.waitForResponse(res => res.url().includes('/preview')),
      playBtn.click()
    ]);
    expect(response.ok()).toBeTruthy();
    await expect(playBtn).toBeDisabled();
  });

  test('TC3: Short synth', async ({ page }) => {
    await page.locator('article').first().locator('button').last().click();
    await page.getByRole('button', { name: 'Chào mừng ngắn' }).click();
    
    const [response] = await Promise.all([
      page.waitForResponse(res => res.url().includes('/audio/speech'), { timeout: 60000 }),
      page.getByRole('button', { name: 'Tạo giọng nói' }).click()
    ]);
    expect(response.ok()).toBeTruthy();
    
    await expect(page.locator('audio')).toBeVisible({ timeout: 60000 });
    await expect(page.getByRole('button', { name: 'Phát' })).toBeVisible();
  });

  test('TC4: Long synth stream', async ({ page }) => {
    await page.locator('article').first().locator('button').last().click();
    await page.getByRole('button', { name: 'Đoạn văn dài' }).click();
    
    const [response] = await Promise.all([
      page.waitForResponse(res => res.url().includes('/audio/stream'), { timeout: 60000 }),
      page.getByRole('button', { name: 'Tạo giọng nói' }).click()
    ]);
    expect(response.ok()).toBeTruthy();
    
    await expect(page.locator('audio')).toBeVisible({ timeout: 60000 });
    await expect(page.getByRole('button', { name: 'Tải xuống' })).toBeVisible();
  });

  test('TC5: Style and Speed by engine', async ({ page }) => {
    await page.getByPlaceholder('Tìm giọng').fill('Ngọc Huyền');
    await page.locator('article').first().locator('button').last().click();
    
    await expect(page.getByText('Tốc độ', { exact: false })).toHaveCount(0);
    await expect(page.getByText('Phong cách', { exact: false })).toHaveCount(0);
  });

  test('TC7: Voice search clear', async ({ page }) => {
    await page.getByPlaceholder('Tìm giọng').fill('KhongTonTaiVoice');
    await expect(page.getByText('Không có giọng khớp')).toBeVisible();
    await page.locator('button', { hasText: 'Đặt lại bộ lọc' }).click();
    await expect(page.getByText('Không có giọng khớp')).toHaveCount(0);
  });

  test('TC8: Global error handling', async ({ page }) => {
    await page.route('**/v1/audio/speech', route => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: { message: 'Fake server error', type: 'server_error' } })
      });
    });
    
    await page.locator('article').first().locator('button').last().click();
    await page.getByRole('button', { name: 'Chào mừng ngắn' }).click();
    await page.getByRole('button', { name: 'Tạo giọng nói' }).click();
    await expect(page.getByRole('alert').first()).toBeVisible();
  });

  test('TC9: Speed controls (Kokoro)', async ({ page }) => {
    await page.getByPlaceholder('Tìm giọng').fill('Alloy');
    await page.locator('article').first().locator('button').last().click();
    await expect(page.getByText('Tốc độ', { exact: false })).toBeVisible();
  });

  test('TC10: API utility token', async ({ page }) => {
    await page.evaluate(() => {
      localStorage.setItem('agy_token', 'test_token_123');
    });
    
    const [request] = await Promise.all([
      page.waitForRequest(req => req.url().includes('/v1/voices')),
      page.reload()
    ]);
    
    const authHeader = request.headers()['authorization'];
    expect(authHeader).toBe('Bearer test_token_123');
  });

  test('TC11: ASR upload', async ({ page }) => {
    await page.goto('/transcribe');
    
    const dummyAudio = Buffer.from('dummy audio content');
    const dummyPath = path.join(process.cwd(), 'dummy.mp3');
    fs.writeFileSync(dummyPath, dummyAudio);
    
    await page.route('**/audio/transcriptions', async route => {
      const json = {
        language: 'vi',
        segments: [{ id: 1, start: 0, end: 1, text: 'xin chào' }],
        words: [{ word: 'xin', start: 0, end: 0.5 }, { word: 'chào', start: 0.5, end: 1 }]
      };
      await route.fulfill({ json });
    });
    
    await page.setInputFiles('input[type="file"]', dummyPath);
    await expect(page.getByText('xin chào').first()).toBeVisible();
    await expect(page.getByText('0.00')).toBeVisible();
    fs.unlinkSync(dummyPath);
  });

  test('TC12: Limits intercept', async ({ page }) => {
    await page.route('**/audio/speech', async route => {
      await route.fulfill({ status: 429, json: { error: { code: 'rate_limit_exceeded', message: 'Rate limit exceeded' } } });
    });
    
    await page.locator('article').first().locator('button').last().click();
    await page.getByRole('button', { name: 'Chào mừng ngắn' }).click();
    await page.getByRole('button', { name: 'Tạo giọng nói' }).click();
    
    await expect(page.getByRole('alert').first()).toBeVisible();
  });

  test('TC13: Cloning hidden', async ({ page }) => {
    await expect(page.getByRole('link', { name: 'Nhân bản giọng' })).toHaveCount(0);
    await page.goto('/clone');
    await expect(page).toHaveURL('/');
  });

  test('TC14: Deep link transcribe', async ({ page }) => {
    await page.goto('/transcribe');
    await expect(page.getByText('Thả tệp âm thanh vào đây')).toBeVisible();
  });

  test('TC15: i18n and theme', async ({ page }) => {
    await expect(page.getByRole('button', { name: 'Đổi ngôn ngữ' }).or(page.getByRole('button', { name: 'Change interface language' }))).toBeVisible();
    await page.getByRole('button', { name: 'Đổi ngôn ngữ' }).click();
    
    await expect(page.getByRole('banner')).toContainText('Text to speech');
    
    await page.getByRole('button', { name: 'Dark theme' }).or(page.getByRole('button', { name: 'Giao diện tối' })).click();
    await expect(page.locator('html')).toHaveAttribute('class', 'dark');
    
    await page.getByRole('button', { name: 'Change interface language' }).click();
    await page.getByRole('button', { name: 'Giao diện sáng' }).or(page.getByRole('button', { name: 'Light theme' })).click();
  });
});
