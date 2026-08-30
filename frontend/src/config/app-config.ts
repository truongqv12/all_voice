export const appConfig = {
  support: {
    buyMeCoffeeUrl: 'https://www.buymeacoffee.com/',
  },
  demos: { limits: true },
  features: {
    cloning: import.meta.env.VITE_FEATURE_CLONING === 'true' || false,
    ttsToSrt: false,
  },
} as const
