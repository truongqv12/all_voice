import { expect, test } from '@playwright/test'

const voices = {
  data: [
    { id: 'vi-demo', name: 'Giọng Việt', model: 'vieneu', language: 'vi', preview_url: '/v1/voices/vieneu/vi-demo/preview' },
    { id: 'ja-demo', name: '日本語', model: 'voicevox', language: 'ja', preview_url: '/v1/voices/voicevox/ja-demo/preview' },
  ],
}

const audio = Buffer.from('ID3\x04\0\0\0\0\0\x21')

test.describe('Phase 6: Functional QA', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/v1/voices', route => route.fulfill({ contentType: 'application/json', body: JSON.stringify(voices) }))
    await page.goto('/')
    await expect(page.locator('article').first()).toBeVisible()
  })

  test('uses buffered speech at 2,000 characters and stream above it', async ({ page }) => {
    const textarea = page.locator('textarea')
    await page.locator('article').filter({ hasText: 'Giọng Việt' }).getByRole('button').last().click()
    await page.route('**/v1/audio/speech', route => route.fulfill({ contentType: 'audio/mpeg', body: audio }))
    await textarea.fill('a'.repeat(2_000))
    const buffered = page.waitForRequest('**/v1/audio/speech')
    await page.getByRole('button', { name: 'Tạo giọng nói' }).click()
    await buffered
    await expect(page.locator('audio')).toBeVisible()

    await page.reload()
    await page.locator('article').filter({ hasText: 'Giọng Việt' }).getByRole('button').last().click()
    await page.route('**/v1/audio/stream', route => route.fulfill({ contentType: 'audio/mpeg', body: audio }))
    await textarea.fill('a'.repeat(2_001))
    const streamed = page.waitForRequest('**/v1/audio/stream')
    await page.getByRole('button', { name: 'Tạo giọng nói' }).click()
    await streamed
  })

  test('enforces the 20,000-character input ceiling', async ({ page }) => {
    const textarea = page.locator('textarea')
    await page.locator('article').filter({ hasText: 'Giọng Việt' }).getByRole('button').last().click()
    await textarea.fill('a'.repeat(20_001))
    await expect(textarea).toHaveValue('a'.repeat(20_000))
    await expect(page.getByRole('button', { name: 'Tạo giọng nói' })).toBeEnabled()
  })

  test('shows a clear preview error without synthesizing a fallback', async ({ page }) => {
    await page.route('**/v1/voices/vieneu/vi-demo/preview', route => route.fulfill({ status: 404, contentType: 'application/json', body: '{}' }))
    let speechRequests = 0
    await page.route('**/v1/audio/speech', route => { speechRequests += 1; return route.fulfill({ body: audio }) })
    await page.locator('article').filter({ hasText: 'Giọng Việt' }).getByRole('button', { name: /Nghe thử/ }).click()
    await expect(page.getByRole('alert')).toContainText('chưa có mẫu')
    expect(speechRequests).toBe(0)
  })

  test('cancels a running stream and does not render stale audio', async ({ page }) => {
    await page.locator('article').filter({ hasText: 'Giọng Việt' }).getByRole('button').last().click()
    await page.route('**/v1/audio/stream', () => new Promise(() => undefined))
    await page.locator('textarea').fill('a'.repeat(2_001))
    await page.getByRole('button', { name: 'Tạo giọng nói' }).click()
    await expect(page.getByRole('button', { name: 'Hủy' })).toBeVisible()
    await page.getByRole('button', { name: 'Hủy' }).click()
    await expect(page.getByRole('button', { name: 'Tạo giọng nói' })).toBeEnabled()
    await expect(page.locator('audio')).toHaveCount(0)
  })

  test('sends the original text as the ASR subtitle prompt', async ({ page }) => {
    const text = 'Phụ đề cần bám sát câu gốc.'
    await page.locator('article').filter({ hasText: 'Giọng Việt' }).getByRole('button').last().click()
    await page.route('**/v1/audio/speech', route => route.fulfill({ contentType: 'audio/mpeg', body: audio }))
    await page.locator('textarea').fill(text)
    await page.getByRole('button', { name: 'Tạo giọng nói' }).click()
    await expect(page.getByRole('button', { name: 'Xuất phụ đề' })).toBeVisible()
    const transcription = page.waitForRequest('**/v1/audio/transcriptions')
    await page.route('**/v1/audio/transcriptions', route => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ language: 'vi', segments: [{ id: 1, start: 0, end: 1, text }], words: [] }) }))
    await page.getByRole('button', { name: 'Xuất phụ đề' }).click()
    expect((await transcription).postData()).toContain(text)
    await expect(page.getByText('Đã tải tệp phụ đề .srt.')).toBeVisible()
  })

  test('uses native timing for a VOICEVOX subtitle', async ({ page }) => {
    await page.locator('article').filter({ hasText: '日本語' }).getByRole('button').last().click()
    await page.route('**/v1/audio/speech', route => route.fulfill({ contentType: 'audio/mpeg', body: audio }))
    await page.route('**/v1/audio/speech/timing', route => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ cues: [{ start: 0, end: 1, text: 'テスト' }] }) }))
    await page.locator('textarea').fill('テスト')
    await page.getByRole('button', { name: 'Tạo giọng nói' }).click()
    const timing = page.waitForRequest('**/v1/audio/speech/timing')
    await page.getByRole('button', { name: 'Xuất phụ đề' }).click()
    expect(JSON.parse((await timing).postData() || '{}')).toMatchObject({ model: 'voicevox', streaming: false })
    await expect(page.getByText('Phụ đề tiếng Nhật dùng nhịp mora VOICEVOX native để khớp audio.')).toBeVisible()
  })
})
