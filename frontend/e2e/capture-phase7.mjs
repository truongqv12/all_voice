import { chromium } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { spawn } from 'node:child_process'

const outputDir = new URL('./__screenshots__/phase7/', import.meta.url)
const viewports = [
  { name: '375', width: 375, height: 812 },
  { name: '768', width: 768, height: 1024 },
  { name: '1024', width: 1024, height: 900 },
  { name: '1440', width: 1440, height: 900 },
]
const themes = ['light', 'dark']
const BASE_URL = process.env.PREVIEW_URL || 'http://127.0.0.1:4273'
const sampleAudioPath = fileURLToPath(new URL('../public/audio/mock-sample.mp3', import.meta.url))

await mkdir(outputDir, { recursive: true })

async function isServerUp(url) {
  try {
    const res = await fetch(url, { method: 'HEAD' })
    return res.ok || res.status < 500
  } catch {
    return false
  }
}

async function ensurePreviewServer() {
  if (await isServerUp(BASE_URL)) {
    console.log(`Preview server is already running on ${BASE_URL}`)
    return null
  }

  console.log(`Starting preview server on port 4273...`)
  const server = spawn('pnpm', ['preview'], {
    cwd: fileURLToPath(new URL('..', import.meta.url)),
    stdio: 'ignore',
    detached: true,
  })

  // Wait up to 10s for server to start
  for (let i = 0; i < 50; i++) {
    await new Promise((r) => setTimeout(r, 200))
    if (await isServerUp(BASE_URL)) {
      console.log(`Preview server ready at ${BASE_URL}`)
      return server
    }
  }
  throw new Error(`Timed out waiting for preview server at ${BASE_URL}`)
}

async function captureScreen(page, filename, width, theme) {
  await page.evaluate(() => document.fonts.ready)
  await page.waitForTimeout(250)
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1
  )
  if (overflow) {
    const scrollW = await page.evaluate(() => document.documentElement.scrollWidth)
    const clientW = await page.evaluate(() => document.documentElement.clientWidth)
    throw new Error(`Horizontal overflow detected in ${filename} at ${width}px ${theme} (scrollWidth=${scrollW}, clientWidth=${clientW})`)
  }
  const filePath = fileURLToPath(new URL(filename, outputDir))
  await page.screenshot({
    path: filePath,
    fullPage: true,
    animations: 'disabled',
  })
  console.log(`Captured: ${filename}`)
}

async function run() {
  const previewProcess = await ensurePreviewServer()
  console.log(`Starting Phase 7 E2E capture on ${BASE_URL}...`)
  const browser = await chromium.launch({ headless: true })

  try {
    for (const vp of viewports) {
      for (const theme of themes) {
        console.log(`\n--- Viewport ${vp.name}px | Theme: ${theme} ---`)

        // 1. TTS - Empty state
        {
          const page = await browser.newPage({
            viewport: { width: vp.width, height: vp.height },
            colorScheme: theme,
          })
          await page.addInitScript(({ theme }) => {
            localStorage.setItem('all-voice-theme', theme)
            localStorage.setItem('all-voice-language', 'vi')
          }, { theme })
          await page.goto(`${BASE_URL}/`, { waitUntil: 'networkidle' })
          await captureScreen(page, `tts-empty__${vp.name}__${theme}.png`, vp.width, theme)
          await page.close()
        }

        // 2. TTS - Filled & Result state
        {
          const page = await browser.newPage({
            viewport: { width: vp.width, height: vp.height },
            colorScheme: theme,
          })
          await page.addInitScript(({ theme }) => {
            localStorage.setItem('all-voice-theme', theme)
            localStorage.setItem('all-voice-language', 'vi')
          }, { theme })
          await page.goto(`${BASE_URL}/`, { waitUntil: 'networkidle' })
          const textarea = page.locator('textarea')
          await textarea.fill('Hệ thống tạo giọng nói tự nhiên với công nghệ AI hiện đại, hỗ trợ đa ngôn ngữ và chuẩn hoá văn bản tiếng Việt.')
          await captureScreen(page, `tts-filled__${vp.name}__${theme}.png`, vp.width, theme)

          // Click generate button and wait for result
          const generateBtn = page.getByRole('button', { name: /Tạo giọng nói|Create speech/i })
          await generateBtn.click()
          await page.getByRole('button', { name: /Tải xuống|Download/i }).first().waitFor({ timeout: 10000 })
          await captureScreen(page, `tts-result__${vp.name}__${theme}.png`, vp.width, theme)
          await page.close()
        }

        // 3. Transcribe / ASR - Empty state
        {
          const page = await browser.newPage({
            viewport: { width: vp.width, height: vp.height },
            colorScheme: theme,
          })
          await page.addInitScript(({ theme }) => {
            localStorage.setItem('all-voice-theme', theme)
            localStorage.setItem('all-voice-language', 'vi')
          }, { theme })
          await page.goto(`${BASE_URL}/transcribe`, { waitUntil: 'networkidle' })
          await captureScreen(page, `transcribe-empty__${vp.name}__${theme}.png`, vp.width, theme)
          await page.close()
        }

        // 4. Transcribe / ASR - Result state (with transcript & export panel)
        {
          const page = await browser.newPage({
            viewport: { width: vp.width, height: vp.height },
            colorScheme: theme,
          })
          await page.addInitScript(({ theme }) => {
            localStorage.setItem('all-voice-theme', theme)
            localStorage.setItem('all-voice-language', 'vi')
          }, { theme })
          await page.goto(`${BASE_URL}/transcribe`, { waitUntil: 'networkidle' })
          const fileInput = page.locator('input[type="file"]')
          await fileInput.setInputFiles(sampleAudioPath)
          // Wait for transcription processing to finish and both panels to render
          await page.getByRole('heading', { name: /Chỉnh nhịp và tải xuống|Export subtitles/i }).first().waitFor({ state: 'visible', timeout: 15000 })
          await page.locator('ol > li').first().waitFor({ state: 'visible', timeout: 15000 })
          await captureScreen(page, `transcribe-result__${vp.name}__${theme}.png`, vp.width, theme)
          await page.close()
        }

        // 5. Clone - Auth Gate state
        {
          const page = await browser.newPage({
            viewport: { width: vp.width, height: vp.height },
            colorScheme: theme,
          })
          await page.addInitScript(({ theme }) => {
            localStorage.setItem('all-voice-theme', theme)
            localStorage.setItem('all-voice-language', 'vi')
          }, { theme })
          await page.goto(`${BASE_URL}/clone`, { waitUntil: 'networkidle' })
          await captureScreen(page, `clone-gate__${vp.name}__${theme}.png`, vp.width, theme)
          await page.close()
        }

        // 6. Clone - Enrol form & Created Clones list state
        {
          const page = await browser.newPage({
            viewport: { width: vp.width, height: vp.height },
            colorScheme: theme,
          })
          await page.addInitScript(({ theme }) => {
            localStorage.setItem('all-voice-theme', theme)
            localStorage.setItem('all-voice-language', 'vi')
          }, { theme })
          await page.goto(`${BASE_URL}/clone`, { waitUntil: 'networkidle' })
          const signInBtn = page.getByRole('button', { name: /Đăng nhập bản mẫu|Demo sign in/i })
          await signInBtn.click()
          const nameInput = page.getByLabel(/Tên giọng|Voice name/i)
          await nameInput.fill('Giọng đọc truyền cảm')
          const fileInput = page.locator('input[type="file"]')
          await fileInput.setInputFiles(sampleAudioPath)
          const consentCheckbox = page.getByRole('checkbox')
          await consentCheckbox.check()
          const createBtn = page.getByRole('button', { name: /Tạo giọng nhân bản mẫu|Create sample voice clone/i })
          await createBtn.click()
          await page.getByText('Giọng đọc truyền cảm').first().waitFor({ timeout: 10000 })
          await captureScreen(page, `clone-app__${vp.name}__${theme}.png`, vp.width, theme)
          await page.close()
        }
      }
    }
    console.log(`\nSuccessfully captured all screenshots in ${fileURLToPath(outputDir)}!`)
  } finally {
    await browser.close()
    if (previewProcess) {
      try {
        process.kill(-previewProcess.pid)
      } catch {
        previewProcess.kill()
      }
    }
  }
}

run().catch((err) => {
  console.error('Capture failed:', err)
  process.exit(1)
})
