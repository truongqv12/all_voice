import { expect, test } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { join } from 'node:path'

const imageDir = join(process.cwd(), 'e2e', '__screenshots__', 'phase7')
const voices = { data: [{ id: 'vi-demo', name: 'Giọng Việt', model: 'vieneu', language: 'vi' }] }
const audio = Buffer.from('ID3\x04\0\0\0\0\0\x21')

test.describe('Phase 7: visual long-task states', () => {
  test.beforeEach(async ({ page }) => {
    mkdirSync(imageDir, { recursive: true })
    await page.route('**/v1/voices', route => route.fulfill({ contentType: 'application/json', body: JSON.stringify(voices) }))
    await page.goto('/')
    await page.locator('article').getByRole('button').last().click()
  })

  test('captures synthesis progress', async ({ page }) => {
    await page.route('**/v1/audio/speech', () => new Promise(() => undefined))
    await page.locator('textarea').fill('Đang tổng hợp phụ đề.')
    await page.getByRole('button', { name: 'Tạo giọng nói' }).click()
    await expect(page.getByRole('button', { name: 'Hủy' })).toBeVisible()
    await page.screenshot({ path: join(imageDir, 'tts-progress__375__light.png'), fullPage: true })
  })

  test('captures retryable backend error', async ({ page }) => {
    await page.route('**/v1/audio/speech', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ error: { code: 'overloaded', message: 'Busy' } }) }))
    await page.locator('textarea').fill('Lỗi có thể thử lại.')
    await page.getByRole('button', { name: 'Tạo giọng nói' }).click()
    await expect(page.getByRole('alert').first()).toBeVisible()
    await expect(page.getByRole('button', { name: 'Thử lại' })).toBeVisible()
    await page.screenshot({ path: join(imageDir, 'tts-error__375__light.png'), fullPage: true })
  })

  test('captures approximate subtitle progress', async ({ page }) => {
    await page.route('**/v1/audio/speech', route => route.fulfill({ contentType: 'audio/mpeg', body: audio }))
    await page.route('**/v1/audio/transcriptions', () => new Promise(() => undefined))
    await page.locator('textarea').fill('Phụ đề đang tạo.')
    await page.getByRole('button', { name: 'Tạo giọng nói' }).click()
    await page.getByRole('button', { name: 'Xuất phụ đề .srt' }).click()
    await expect(page.getByText('Đang tạo phụ đề…')).toBeVisible()
    await page.screenshot({ path: join(imageDir, 'subtitle-progress__375__light.png'), fullPage: true })
  })
})
