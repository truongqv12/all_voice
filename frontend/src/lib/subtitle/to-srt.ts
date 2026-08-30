import type { SubtitleCue } from './chunk-cues'

function timestamp(seconds: number) {
  const milliseconds = Math.round(seconds * 1000); const hours = Math.floor(milliseconds / 3_600_000); const minutes = Math.floor(milliseconds / 60_000) % 60; const secs = Math.floor(milliseconds / 1000) % 60; const ms = milliseconds % 1000
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')},${String(ms).padStart(3, '0')}`
}

export function toSrt(cues: SubtitleCue[]) { return cues.map((cue, index) => `${index + 1}\n${timestamp(cue.start)} --> ${timestamp(cue.end)}\n${cue.lines.join('\n')}`).join('\n\n') + '\n' }
