export const CANONICAL_TOKEN_IDS = {
  solana: {
    jup: 'JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN',
  },
};

export const SIGNAL_PRESETS = {
  Scalping: { minRisk: 45, minWhale: 8, uptrendOnly: true },
  Swing: { minRisk: 55, minWhale: 12, uptrendOnly: false },
  'High Conviction': { minRisk: 75, minWhale: 20, uptrendOnly: true },
};

export const SWEEP_FALLBACK_TOKENS = {
  solana: ['SOL', 'JUP', 'RAY', 'BONK', 'WIF', 'PYTH', 'JTO', 'RNDR', 'POPCAT', 'BOME'],
  ethereum: ['ETH', 'UNI', 'AAVE', 'LINK', 'CRV', 'MKR', 'SNX', 'LDO', 'ARB', 'OP'],
  bsc: ['BNB', 'CAKE', 'XVS', 'BAKE', 'TWT', 'DOGE', 'SHIB', 'FLOKI', 'XRP', 'USDT'],
  base: ['ETH', 'AERO', 'DEGEN', 'BRETT', 'USDC', 'BALD', 'TOSHI', 'KEYCAT', 'PRIME', 'AAVE'],
  arbitrum: ['ARB', 'GMX', 'RDNT', 'MAGIC', 'GRAIL', 'ETH', 'LINK', 'AAVE', 'UNI', 'USDC'],
  optimism: ['OP', 'VELO', 'SNX', 'LYRA', 'ETH', 'USDC', 'AAVE', 'LINK', 'UNI', 'WBTC'],
  polygon: ['POL', 'AAVE', 'QUICK', 'SUSHI', 'GHST', 'USDC', 'WETH', 'WBTC', 'LINK', 'CRV'],
  avalanche: ['AVAX', 'JOE', 'PNG', 'QI', 'GMX', 'USDC', 'WETH', 'WBTC', 'LINK', 'AAVE'],
};

export const CHAINS = ['solana', 'ethereum', 'bsc', 'base', 'arbitrum', 'optimism', 'polygon', 'avalanche'];
