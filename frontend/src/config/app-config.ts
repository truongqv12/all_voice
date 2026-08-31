export const appConfig = {
  useMock: import.meta.env.VITE_USE_MOCK === '1',
  support: {
    buyMeCoffeeUrl: 'https://buymeacoffee.com/truongtt',
  },
  demos: { limits: true },
  features: {
    cloning: import.meta.env.VITE_FEATURE_CLONING === 'true' || false,
    ttsToSrt: true,
  },
} as const
