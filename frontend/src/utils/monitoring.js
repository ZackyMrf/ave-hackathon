import { CANONICAL_TOKEN_IDS, SWEEP_FALLBACK_TOKENS } from '../constants/monitoring';

export function buildPairCacheKey(tokenAddress, chain) {
  const addr = String(tokenAddress || '').trim().toLowerCase();
  const ch = String(chain || '').trim().toLowerCase();
  if (!addr || !ch) return '';
  return `${addr}-${ch}`;
}

export function getIntervalMinutes(days) {
  return days <= 7 ? 60 : days <= 30 ? 120 : 240;
}

export function resolveTokenInput(rawToken, chainName) {
  const token = String(rawToken || '').trim();
  const chain = String(chainName || '').trim().toLowerCase();
  if (!token) return '';

  const alias = CANONICAL_TOKEN_IDS[chain]?.[token.toLowerCase()];
  return alias || token;
}

export function formatMoney(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  const n = Number(value);
  if (Math.abs(n) >= 1_000_000_000) return `$${(n / 1_000_000_000).toFixed(2)}B`;
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (Math.abs(n) >= 1_000) return `$${(n / 1_000).toFixed(2)}K`;
  return `$${n.toFixed(4)}`;
}

export function scoreTone(score) {
  if (score >= 75) return 'tone-red';
  if (score >= 55) return 'tone-orange';
  if (score >= 35) return 'tone-yellow';
  return 'tone-green';
}

export function getRiskTier(score) {
  const n = Number(score || 0);
  if (n >= 75) return 'high';
  if (n >= 55) return 'elevated';
  if (n >= 35) return 'watch';
  return 'low';
}

export function shortAddress(value) {
  const text = String(value || '').trim();
  if (!text) return '-';
  if (text.length <= 12) return text;
  return `${text.slice(0, 6)}...${text.slice(-4)}`;
}

export function getArkhamAddressUrl(address) {
  const addr = String(address || '').trim();
  if (!addr) return '';
  return `https://platform.arkhamintelligence.com/explorer/address/${encodeURIComponent(addr)}`;
}

export function getAddressExplorerUrl(chain, address) {
  const addr = String(address || '').trim();
  const ch = String(chain || '').trim().toLowerCase();
  if (!addr) return '';

  const templates = {
    solana: `https://solscan.io/account/${encodeURIComponent(addr)}`,
    ethereum: `https://etherscan.io/address/${encodeURIComponent(addr)}`,
    bsc: `https://bscscan.com/address/${encodeURIComponent(addr)}`,
    base: `https://basescan.org/address/${encodeURIComponent(addr)}`,
    arbitrum: `https://arbiscan.io/address/${encodeURIComponent(addr)}`,
    optimism: `https://optimistic.etherscan.io/address/${encodeURIComponent(addr)}`,
    polygon: `https://polygonscan.com/address/${encodeURIComponent(addr)}`,
    avalanche: `https://snowtrace.io/address/${encodeURIComponent(addr)}`,
  };

  return templates[ch] || '';
}

export function getTxExplorerUrl(chain, txHash) {
  const hash = String(txHash || '').trim();
  const ch = String(chain || '').trim().toLowerCase();
  if (!hash) return '';

  const templates = {
    solana: `https://solscan.io/tx/${encodeURIComponent(hash)}`,
    ethereum: `https://etherscan.io/tx/${encodeURIComponent(hash)}`,
    bsc: `https://bscscan.com/tx/${encodeURIComponent(hash)}`,
    base: `https://basescan.org/tx/${encodeURIComponent(hash)}`,
    arbitrum: `https://arbiscan.io/tx/${encodeURIComponent(hash)}`,
    optimism: `https://optimistic.etherscan.io/tx/${encodeURIComponent(hash)}`,
    polygon: `https://polygonscan.com/tx/${encodeURIComponent(hash)}`,
    avalanche: `https://snowtrace.io/tx/${encodeURIComponent(hash)}`,
  };

  return templates[ch] || '';
}

export function formatSnapshotTime(ts) {
  if (!Number.isFinite(Number(ts))) return '-';
  return new Date(Number(ts)).toLocaleString();
}

export function isLikelyAddress(value) {
  const text = String(value || '').trim();
  if (!text || text.includes(' ')) return false;
  if (/^0x[a-fA-F0-9]{40}$/.test(text)) return true;
  if (/^[1-9A-HJ-NP-Za-km-z]{32,48}$/.test(text)) return true;
  return false;
}

// Maps native/placeholder token addresses to their wrapped equivalents
// so that external tools (Bubblemaps, Ave Pro) work correctly.
const NATIVE_TOKEN_WRAPPED_MAP = {
  // Ethereum mainnet — native ETH placeholder -> WETH
  'ethereum:0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee': '0xC02aaA39b223FE8D0A0E5C4F27eAD9083C756Cc2',
  'eth:0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee':      '0xC02aaA39b223FE8D0A0E5C4F27eAD9083C756Cc2',
  // BSC — native BNB placeholder -> WBNB
  'bsc:0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee':      '0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c',
  // Base — native ETH placeholder -> WETH on Base
  'base:0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee':     '0x4200000000000000000000000000000000000006',
  // Arbitrum — native ETH placeholder -> WETH on Arbitrum
  'arbitrum:0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee': '0x82af49447d8a07e3bd95bd0d56f35241523fbab1',
  // Optimism — native ETH placeholder -> WETH on OP
  'optimism:0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee': '0x4200000000000000000000000000000000000006',
  // Polygon — native MATIC placeholder -> WMATIC
  'polygon:0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee':  '0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270',
  // Avalanche — native AVAX placeholder -> WAVAX
  'avalanche:0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee': '0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7',
  // Solana — native SOL placeholder -> WSOL
  'solana:so11111111111111111111111111111111111111111':   'So11111111111111111111111111111111111111112',
  'solana:11111111111111111111111111111111':              'So11111111111111111111111111111111111111112',
};

/**
 * Resolve a token address for use in external links.
 * Replaces native-token placeholder addresses with their wrapped equivalents.
 * @param {string} address - raw contract address from the API
 * @param {string} chain   - chain name (ethereum, eth, solana, bsc, ...)
 * @returns {string} address suitable for Bubblemaps / Ave Pro links
 */
export function getLinkAddress(address, chain) {
  const addr = String(address || '').trim();
  const ch   = String(chain || '').trim().toLowerCase();
  if (!addr) return '';
  const key = `${ch}:${addr.toLowerCase()}`;
  return NATIVE_TOKEN_WRAPPED_MAP[key] || addr;
}

function toBubbleMapChain(chain) {
  const ch = String(chain || '').trim().toLowerCase();
  const map = {
    ethereum: 'eth',
    arbitrum: 'arb',
    optimism: 'op',
    avalanche: 'avax',
    polygon: 'polygon',
    bsc: 'bsc',
    solana: 'solana',
    base: 'base',
  };
  return map[ch] || ch;
}

export function getBubbleMapUrl(address, chain) {
  const addr = getLinkAddress(address, chain);
  if (!addr) return '';
  const bubbleChain = toBubbleMapChain(chain);
  return `https://v2.bubblemaps.io/map?address=${encodeURIComponent(addr)}&chain=${encodeURIComponent(bubbleChain)}`;
}

export function getAveProUrl(address, chain) {
  const addr = getLinkAddress(address, chain);
  const ch   = String(chain || '').trim().toLowerCase();
  if (!addr || !ch) return '';
  return `https://pro.ave.ai/token/${encodeURIComponent(addr)}-${encodeURIComponent(ch)}`;
}

export function normalizeSweepResults(inputRows, chainName, requestedTop) {
  const rows = Array.isArray(inputRows) ? [...inputRows] : [];
  const out = [];
  const seen = new Set();

  for (const item of rows) {
    const token = String(item?.token || '').trim().toUpperCase();
    const addr = String(item?.address || item?.ca || '').trim().toLowerCase();
    const key = addr || `sym:${token}`;
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(item);
    if (out.length >= requestedTop) break;
  }

  const pool = SWEEP_FALLBACK_TOKENS[String(chainName || 'solana').toLowerCase()] || SWEEP_FALLBACK_TOKENS.solana;
  let idx = 0;
  while (out.length < requestedTop) {
    const symbol = pool[idx % pool.length];
    idx += 1;
    const key = `sym:${symbol}`;
    if (seen.has(key)) continue;
    seen.add(key);

    out.push({
      token: symbol,
      chain: String(chainName || 'solana').toLowerCase(),
      address: symbol,
      price: 0,
      price_change_24h: 0,
      score: { risk_adjusted: 0, alert_level: 'green' },
      signals: { volume_divergence: 0, whale_score: 0 },
      is_fallback: true,
    });
  }

  return out.slice(0, requestedTop);
}

export function buildTrendCacheKey(item, chain) {
  const addr = String(item?.address || item?.ca || '').trim().toLowerCase();
  const tok = String(item?.token || '').trim().toLowerCase();
  const ch = String(chain || '').trim().toLowerCase();
  if (!ch) return '';
  if (addr) return `${addr}-${ch}`;
  if (tok) return `${tok}-${ch}`;
  return '';
}

export function normalizeKlinePoints(points = []) {
  return (points || [])
    .map((p) => {
      const tRaw = Number(p.time);
      const t = tRaw > 10_000_000_000 ? Math.floor(tRaw / 1000) : Math.floor(tRaw);
      const open = Number(p.open);
      const high = Number(p.high);
      const low = Number(p.low);
      const close = Number(p.close);
      const volume = Number(p.volume || 0);
      return { time: t, open, high, low, close, volume };
    })
    .filter(
      (p) =>
        Number.isFinite(p.time) &&
        p.time > 0 &&
        Number.isFinite(p.open) &&
        Number.isFinite(p.high) &&
        Number.isFinite(p.low) &&
        Number.isFinite(p.close) &&
        p.high >= p.low
    )
    .sort((a, b) => a.time - b.time);
}

export function buildTrendSnapshotFromKlines(validPoints = []) {
  if (!validPoints.length) return null;

  const latest = validPoints[validPoints.length - 1];
  const latestClose = Number(latest.close);
  const cutoff = Number(latest.time) - 24 * 60 * 60;

  let basePoint = validPoints[0];
  for (let i = validPoints.length - 1; i >= 0; i -= 1) {
    if (Number(validPoints[i].time) <= cutoff) {
      basePoint = validPoints[i];
      break;
    }
  }

  const baseClose = Number(basePoint?.close || 0);
  const change24h = baseClose > 0 ? ((latestClose - baseClose) / baseClose) * 100 : 0;
  const sparkline = validPoints.slice(-24).map((p) => Number(p.close));

  return {
    latestClose,
    change24h,
    sparkline,
    updatedAt: Date.now(),
    latestTime: latest.time,
  };
}
