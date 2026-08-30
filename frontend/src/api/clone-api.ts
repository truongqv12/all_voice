import type { Voice } from './types'

export type VoiceClone = { id: string; name: string; createdAt: string; status: 'ready'; voice: Voice }
export interface CloneApi { createClone(name: string, sampleName: string): Promise<VoiceClone>; deleteClone(id: string): Promise<void> }
const wait = (ms: number) => new Promise(resolve => window.setTimeout(resolve, ms))

export const mockCloneApi: CloneApi = {
  async createClone(name) { await wait(950); const id = `clone-${Date.now()}`; return { id, name, createdAt: new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium' }).format(new Date()), status: 'ready', voice: { id, name, language: 'vi', engine: 'clone', gender: 'neutral', styles: ['Tự nhiên'], description: 'Giọng nhân bản mẫu của bạn' } } },
  async deleteClone() { await wait(260) },
}
