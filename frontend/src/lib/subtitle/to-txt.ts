import type { SubtitleCue } from './chunk-cues'

export function toTxt(cues: SubtitleCue[]) { return `${cues.map(cue => cue.lines.join(' ')).join(' ')}\n` }
