export async function downloadAudio(url: string, filename: string) {
  const response = await fetch(url); const blobUrl = URL.createObjectURL(await response.blob()); const link = document.createElement('a')
  link.href = blobUrl; link.download = filename; link.click(); URL.revokeObjectURL(blobUrl)
}

export function utf8TextBlob(content: string, mimeType: string) {
  return new Blob(['\uFEFF', content], { type: `${mimeType};charset=utf-8` })
}

export function downloadText(content: string, filename: string, mimeType: string) {
  const blobUrl = URL.createObjectURL(utf8TextBlob(content, mimeType))
  const link = document.createElement('a')
  link.href = blobUrl
  link.download = filename
  link.click()
  window.setTimeout(() => URL.revokeObjectURL(blobUrl), 0)
}
