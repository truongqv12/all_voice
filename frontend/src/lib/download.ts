export async function downloadAudio(url: string, filename: string) {
  const response = await fetch(url); const blobUrl = URL.createObjectURL(await response.blob()); const link = document.createElement('a')
  link.href = blobUrl; link.download = filename; link.click(); URL.revokeObjectURL(blobUrl)
}
