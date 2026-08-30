import { Mic, Sliders } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BottomSheet } from '../../components/ui/bottom-sheet'
import { SelectedVoiceChip } from '../voice/selected-voice-chip'
import { VoicePanel } from '../voice/voice-panel'
import { ComposePanel } from '../compose/compose-panel'
import { UsageGuide } from '../guide/usage-guide'
import { SupportPanel } from '../support/support-panel'

export default function TtsPage() {
  const { t } = useTranslation()
  const [sheetOpen, setSheetOpen] = useState(false)
  const [activeSideTab, setActiveSideTab] = useState<'voices' | 'support'>('voices')

  return (
    <div className="space-y-6 sm:space-y-8">
      <section className="max-w-2xl">
        <h1 className="text-balance text-3xl font-bold leading-tight tracking-[-0.03em] sm:text-4xl">
          {t('tts.title')}
        </h1>
        <p className="mt-3 max-w-xl text-pretty text-base leading-7 text-[var(--color-muted)]">
          {t('tts.description')}
        </p>
      </section>

      {/* 7:3 DESKTOP SPLIT LAYOUT */}
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.25fr)_minmax(22rem,0.75fr)]">
        {/* LEFT 70% COLUMN: Textarea, Presets, Synth Controls, Audio Result, Usage Guide */}
        <section className="space-y-4 rounded-[var(--radius-panel)] border border-[var(--color-border)] bg-[var(--color-surface)] p-4 sm:p-6">
          <div className="lg:hidden">
            <SelectedVoiceChip onOpen={() => setSheetOpen(true)} />
          </div>
          <div className="pt-2 lg:pt-0">
            <ComposePanel />
          </div>
          <UsageGuide />
          {/* MOBILE ONLY: Support, VietQR & Capacity Notice */}
          <div className="border-t border-[var(--color-border)] pt-4 lg:hidden">
            <SupportPanel />
          </div>
        </section>

        {/* RIGHT 30% COLUMN: Voice Catalog & Support Panel */}
        <section className="hidden space-y-3 lg:block">
          <div className="rounded-[var(--radius-panel)] border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
            {/* Tab switchers */}
            <div className="mb-4 flex items-center gap-1.5 rounded-lg bg-[var(--color-surface-soft)] p-1 border border-[var(--color-border)]">
              <button
                type="button"
                onClick={() => setActiveSideTab('voices')}
                className={`flex-1 inline-flex items-center justify-center gap-2 rounded-md px-3 py-1.5 text-xs font-semibold transition-colors cursor-pointer ${
                  activeSideTab === 'voices'
                    ? 'bg-[var(--color-surface)] text-[var(--color-text)] shadow-xs border border-[var(--color-border)]'
                    : 'text-[var(--color-muted)] hover:text-[var(--color-text)]'
                }`}
              >
                <Mic size={14} className="shrink-0 text-[var(--color-primary)]" />
                <span>{t('support.tabVoices')}</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveSideTab('support')}
                className={`flex-1 inline-flex items-center justify-center gap-2 rounded-md px-3 py-1.5 text-xs font-semibold transition-colors cursor-pointer ${
                  activeSideTab === 'support'
                    ? 'bg-[var(--color-surface)] text-[var(--color-text)] shadow-xs border border-[var(--color-border)]'
                    : 'text-[var(--color-muted)] hover:text-[var(--color-text)]'
                }`}
              >
                <Sliders size={14} className="shrink-0 text-[var(--color-primary)]" />
                <span>{t('support.tabCommunity')}</span>
              </button>
            </div>

            {activeSideTab === 'voices' ? (
              <VoicePanel />
            ) : (
              <SupportPanel />
            )}
          </div>
        </section>
      </div>

      {/* MOBILE BOTTOM SHEET */}
      <BottomSheet open={sheetOpen} onOpenChange={setSheetOpen} title={t('voice.title')}>
        <VoicePanel onSelected={() => setSheetOpen(false)} />
      </BottomSheet>
    </div>
  )
}
