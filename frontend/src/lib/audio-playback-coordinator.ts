let activeStop: (() => void) | null = null

export function claimAudio(stop: () => void) {
  activeStop?.(); activeStop = stop
  return () => { if (activeStop === stop) activeStop = null }
}
