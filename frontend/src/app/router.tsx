import { lazy, Suspense } from 'react'
import { createBrowserRouter } from 'react-router-dom'
import { AppShell } from '../components/layout/app-shell'

const TtsPage = lazy(() => import('../features/tts/tts-page'))
const TranscribePage = lazy(() => import('../features/transcribe/transcribe-page'))
const ClonePage = lazy(() => import('../features/clone/clone-page'))
const loading = (page: React.ReactNode) => <Suspense fallback={<div className="min-h-64 animate-pulse rounded-[var(--radius-panel)] bg-[var(--color-surface-soft)]" />}>{page}</Suspense>

import { appConfig } from '../config/app-config'
import { Navigate } from 'react-router-dom'

export const router = createBrowserRouter([{ element: <AppShell />, children: [
  { index: true, element: loading(<TtsPage />) },
  { path: 'transcribe', element: loading(<TranscribePage />) },
  ...(appConfig.features.cloning ? [{ path: 'clone', element: loading(<ClonePage />) }] : []),
  { path: 'clone', element: <Navigate to="/" replace /> },
] }])
