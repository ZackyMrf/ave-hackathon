import { useCallback } from 'react';
import { isLikelyAddress, normalizeSweepResults, resolveTokenInput } from '../utils/monitoring';

export function useMonitoringFetchActions({
  API_BASE,
  token,
  tokenSearchMode,
  chain,
  sweepChain,
  category,
  top,
  whaleToken,
  whaleChain,
  selectedWhaleWallet,
  setTop,
  setStatus,
  setError,
  setReport,
  setSweep,
  setSweepLoading,
  setWhaleLoading,
  setWhaleError,
  setWhaleReport,
  setWhaleWalletHistory,
  setSelectedWhaleWallet,
  sweepAbortControllerRef,
  syncSweepWithChartKlines,
  autoSyncSweepTrend = false,
}) {
  const analyzeToken = useCallback(async () => {
    const tokenInput = String(token || '').trim();
    if (!tokenInput) {
      setError('Token wajib diisi.');
      setStatus('Analysis failed');
      return null;
    }

    const isAddressMode = tokenSearchMode === 'address';
    if (isAddressMode && !isLikelyAddress(tokenInput)) {
      setError('Format contract address tidak valid untuk chain ini.');
      setStatus('Address analysis failed');
      return null;
    }

    setStatus(isAddressMode ? 'Analyzing by contract address...' : 'Analyzing by symbol...');
    setError('');
    try {
      const tokenForApi = isAddressMode ? tokenInput : resolveTokenInput(tokenInput, chain);
      const res = await fetch(
        `${API_BASE}/api/analyze?token=${encodeURIComponent(tokenForApi)}&chain=${encodeURIComponent(chain)}`
      );
      const payload = await res.json();
      if (!res.ok) throw new Error(payload.detail || 'Analyze failed');
      setReport(payload);
      const modeLabel = isAddressMode ? 'Address' : 'Symbol';
      setStatus(`${modeLabel} analysis complete for ${payload.token?.toUpperCase?.() || tokenInput.toUpperCase()}`);
      return payload;
    } catch (err) {
      setError(err.message);
      setStatus(isAddressMode ? 'Address analysis failed' : 'Symbol analysis failed');
      return null;
    }
  }, [API_BASE, chain, setError, setReport, setStatus, token, tokenSearchMode]);

  const runSweep = useCallback(async () => {
    const topRequested = Math.min(20, Math.max(1, Number.parseInt(String(top), 10) || 1));
    if (topRequested !== top) {
      setTop(topRequested);
    }

    if (sweepAbortControllerRef.current) {
      sweepAbortControllerRef.current.abort();
    }
    sweepAbortControllerRef.current = new AbortController();
    const signal = sweepAbortControllerRef.current.signal;
    const requestChain = sweepChain;
    const requestCategory = category;

    const scopeLabel = `${sweepChain} (${category} filter)`;
    setSweepLoading(true);
    setStatus(`Running sweep: ${scopeLabel}...`);
    setError('');
    try {
      const res = await fetch(
        `${API_BASE}/api/sweep?category=${encodeURIComponent(category)}&chain=${encodeURIComponent(sweepChain)}&top=${topRequested}`,
        { signal }
      );
      const payload = await res.json();
      if (!res.ok) throw new Error(payload.detail || 'Sweep failed');

      if (requestChain !== sweepChain || requestCategory !== category) {
        console.log(`Sweep response stale: requested ${requestChain}/${requestCategory} but now ${sweepChain}/${category}`);
        return;
      }

      const results = normalizeSweepResults(payload.results || [], sweepChain, topRequested);
      setSweep(results);
      if (autoSyncSweepTrend && typeof syncSweepWithChartKlines === 'function') {
        syncSweepWithChartKlines(results, sweepChain);
      }
      setStatus(`Sweep complete (${scopeLabel}): ${results.length}/${topRequested} assets`);
    } catch (err) {
      if (err.name === 'AbortError') {
        console.log('Sweep request cancelled (new sweep started or inputs changed)');
        return;
      }
      setError(err.message);
      setStatus('Sweep failed');
    } finally {
      setSweepLoading(false);
    }
  }, [
    API_BASE,
    category,
    setError,
    setStatus,
    setSweep,
    setSweepLoading,
    setTop,
    sweepAbortControllerRef,
    sweepChain,
    syncSweepWithChartKlines,
    top,
    autoSyncSweepTrend,
  ]);

  const runWhaleFeedAnalysis = useCallback(async () => {
    const tokenInput = String(whaleToken || '').trim();
    const chainInput = String(whaleChain || '').trim().toLowerCase();
    if (!tokenInput || !chainInput) {
      setWhaleError('Token dan chain wajib diisi.');
      return;
    }

    setWhaleLoading(true);
    setWhaleError('');
    try {
      const tokenForApi = resolveTokenInput(tokenInput, chainInput);
      const res = await fetch(
        `${API_BASE}/api/analyze?token=${encodeURIComponent(tokenForApi)}&chain=${encodeURIComponent(chainInput)}`
      );
      const payload = await res.json();
      if (!res.ok) throw new Error(payload.detail || 'Whale analysis failed');

      setWhaleReport(payload);
      const whales = Array.isArray(payload?.whales) ? payload.whales : [];
      const snapshotTs = Date.now();

      setWhaleWalletHistory((prev) => {
        const next = { ...prev };
        for (const w of whales) {
          const address = String(w?.address || '').trim();
          if (!address) continue;
          const key = address.toLowerCase();
          const row = {
            capturedAt: snapshotTs,
            token: String(payload?.token || tokenInput).toUpperCase(),
            chain: chainInput,
            ratio: Number(w?.balance_ratio || 0),
            delta: Number(w?.change_24h || 0),
            isNew: Boolean(w?.is_new),
          };

          const existing = Array.isArray(next[key]) ? next[key] : [];
          const last = existing[existing.length - 1];
          const unchanged =
            last &&
            last.chain === row.chain &&
            last.token === row.token &&
            Math.abs(Number(last.ratio || 0) - row.ratio) < 0.0001 &&
            Math.abs(Number(last.delta || 0) - row.delta) < 0.0001;

          if (unchanged) continue;
          next[key] = [...existing.slice(-49), row];
        }
        return next;
      });

      if (!selectedWhaleWallet && whales.length) {
        setSelectedWhaleWallet(String(whales[0]?.address || '').trim());
      }
      setStatus(`Whale feed updated for ${String(payload?.token || tokenInput).toUpperCase()} (${chainInput})`);
    } catch (err) {
      setWhaleError(err.message || 'Failed to load whale feed');
      setWhaleReport(null);
    } finally {
      setWhaleLoading(false);
    }
  }, [
    API_BASE,
    selectedWhaleWallet,
    setSelectedWhaleWallet,
    setStatus,
    setWhaleError,
    setWhaleLoading,
    setWhaleReport,
    setWhaleWalletHistory,
    whaleChain,
    whaleToken,
  ]);

  return {
    analyzeToken,
    runSweep,
    runWhaleFeedAnalysis,
  };
}
