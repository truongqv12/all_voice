import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { VoiceClone } from '../../api/clone-api'
import { useSelection } from '../../store/selection'
import { AuthGate } from './auth-gate'
import { CloneEnrolForm } from './clone-enrol-form'
import { MyClonesList } from './my-clones-list'

const initialSampleClone: VoiceClone = {
  id: 'clone-demo-1',
  name: 'Giọng đọc Podcast Mẫu',
  createdAt: '2026-08-30T10:00:00Z',
  status: 'ready',
  voice: {
    id: 'clone-demo-1',
    name: 'Giọng đọc Podcast Mẫu (Bạn)',
    language: 'vi',
    engine: 'clone',
    gender: 'neutral',
    styles: ['Tự nhiên', 'Truyền cảm'],
    description: 'Mẫu nhân bản thử nghiệm từ tệp âm thanh 15 giây.',
  },
}

export default function ClonePage() {
  const { t } = useTranslation()
  const { addVoice, removeVoice } = useSelection()
  const [clones, setClones] = useState<VoiceClone[]>([initialSampleClone])

  function created(clone: VoiceClone) {
    setClones(current => [clone, ...current])
    addVoice(clone.voice)
  }

  function deleted(id: string) {
    setClones(current => current.filter(clone => clone.id !== id))
    removeVoice(id)
  }

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <section className="max-w-2xl">
        <p className="text-xs font-bold tracking-[0.08em] text-[var(--color-primary)]">{t('clone.eyebrow')}</p>
        <h1 className="mt-2 text-balance text-3xl font-bold tracking-[-0.03em] sm:text-4xl">{t('clone.title')}</h1>
        <p className="mt-3 max-w-xl leading-7 text-[var(--color-muted)]">{t('clone.description')}</p>
      </section>

      <AuthGate>
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,.7fr)]">
          <CloneEnrolForm onCreated={created} />
          <MyClonesList clones={clones} onDeleted={deleted} />
        </div>
      </AuthGate>
    </div>
  )
}
