import { LoaderCircle, Sparkles } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '../../components/ui/button'
import type { GenerateState } from './use-generate'

export function GenerateButton({ disabled, state, onClick }: { disabled: boolean; state: GenerateState; onClick(): void }) {
  const { t } = useTranslation()
  const generating = state === 'generating'

  return (
    <Button className="w-full sm:w-auto" disabled={disabled} onClick={onClick}>
      {generating ? (
        <>
          <LoaderCircle className="animate-spin shrink-0" size={17} />
          <span>{t('compose.generating')}</span>
        </>
      ) : (
        <>
          <Sparkles className="shrink-0" size={17} />
          <span>{t('compose.generate')}</span>
        </>
      )}
    </Button>
  )
}
