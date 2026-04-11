import { useEffect, useRef, useState } from 'react';
import { createChart } from 'lightweight-charts';

function buildSMA(values, period) {
  if (!values.length || period <= 1) return values.slice();
  const out = new Array(values.length).fill(null);
  let sum = 0;
  for (let i = 0; i < values.length; i += 1) {
    sum += values[i];
    if (i >= period) sum -= values[i - period];
    if (i >= period - 1) out[i] = sum / period;
  }
  return out;
}

function buildEMA(values, period) {
  if (!values.length) return [];
  const out = new Array(values.length).fill(null);
  const k = 2 / (period + 1);
  let ema = values[0];
  for (let i = 0; i < values.length; i += 1) {
    ema = i === 0 ? values[0] : values[i] * k + ema * (1 - k);
    if (i >= period - 1) out[i] = ema;
  }
  return out;
}

// Fallback: Use Lightweight Charts
export function LightChartViewer({
  data = [],
  token,
  chain,
  pairAddress = '',
  tokenAddress = '',
  intervalMinutes = 60,
  chartType = 'candlestick',
  showMA = true,
  showEMA = true,
  onPairDiscovered = null,
}) {
  const MAX_LIVE_CANDLES = 1500;
  const STALE_AFTER_MS = 15000;
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const mainSeriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);
  const maSeriesRef = useRef(null);
  const emaSeriesRef = useRef(null);
  const livePriceSeriesRef = useRef(null);
  const mainSeriesTypeRef = useRef('candlestick');
  const latestCandlesRef = useRef([]);
  const showMARef = useRef(showMA);
  const showEMARef = useRef(showEMA);
  const onPairDiscoveredRef = useRef(onPairDiscovered);
  const discoveredPairRef = useRef('');
  const lastTickMsRef = useRef(0);
  const wsRef = useRef(null);
  const [streamState, setStreamState] = useState('idle');

  useEffect(() => {
    showMARef.current = showMA;
  }, [showMA]);

  useEffect(() => {
    showEMARef.current = showEMA;
  }, [showEMA]);

  useEffect(() => {
    onPairDiscoveredRef.current = onPairDiscovered;
  }, [onPairDiscovered]);

  useEffect(() => {
    if (!containerRef.current) return;

    try {
      // Create chart with dark theme
      const chart = createChart(containerRef.current, {
        layout: { 
          background: { color: '#0a0a0a' }, 
          textColor: '#DDD',
          fontSize: 12,
          fontFamily: 'Space Grotesk, sans-serif'
        },
        grid: {
          vertLines: { visible: false },
          horzLines: { visible: false },
        },
        width: containerRef.current.offsetWidth,
        height: 500,
        timeScale: { 
          timeVisible: true, 
          secondsVisible: false,
          fixLeftEdge: false,
          fixRightEdge: false
        },
        rightPriceScale: {
          autoScale: true,
          alignLabels: true,
          scaleMargins: {
            top: 0.1,
            bottom: 0.24
          }
        }
      });

      let mainSeries;
      if (chartType === 'line') {
        mainSeries = chart.addLineSeries({
          color: '#66e6ff',
          lineWidth: 2,
          lastPriceAnimation: 2,
        });
        mainSeriesTypeRef.current = 'line';
      } else if (chartType === 'area') {
        mainSeries = chart.addAreaSeries({
          lineColor: '#66e6ff',
          topColor: 'rgba(102, 230, 255, 0.35)',
          bottomColor: 'rgba(102, 230, 255, 0.02)',
          lineWidth: 2,
          lastPriceAnimation: 2,
        });
        mainSeriesTypeRef.current = 'area';
      } else {
        mainSeries = chart.addCandlestickSeries({
          upColor: '#3ef5b5',
          downColor: '#ff5f84',
          borderDownColor: '#ff5f84',
          borderUpColor: '#3ef5b5',
          wickDownColor: 'rgba(255, 95, 132, 0.5)',
          wickUpColor: 'rgba(62, 245, 181, 0.5)',
          lastPriceAnimation: 2,
        });
        mainSeriesTypeRef.current = 'candlestick';
      }

      // Add volume series
      const volumeSeries = chart.addHistogramSeries({
        color: 'rgba(62, 245, 181, 0.5)',
        lineWidth: 2,
        priceFormat: {
          type: 'volume'
        },
        priceScaleId: 'volume'
      });

      chart.priceScale('volume').applyOptions({
        scaleMargins: {
          top: 0.78,
          bottom: 0,
        },
      });

      const maSeries = chart.addLineSeries({
        color: '#ffd166',
        lineWidth: 1.5,
        priceLineVisible: false,
      });

      const emaSeries = chart.addLineSeries({
        color: '#b388ff',
        lineWidth: 1.5,
        priceLineVisible: false,
      });

      const livePriceSeries = chart.addLineSeries({
        color: 'rgba(102, 230, 255, 0.85)',
        lineWidth: 1,
        lineStyle: 2,
        crosshairMarkerVisible: false,
        lastValueVisible: true,
      });

      mainSeriesRef.current = mainSeries;
      volumeSeriesRef.current = volumeSeries;
      maSeriesRef.current = maSeries;
      emaSeriesRef.current = emaSeries;
      livePriceSeriesRef.current = livePriceSeries;
      
      chart.timeScale().fitContent();
      chartRef.current = chart;

      // Handle resize
      const handleResize = () => {
        if (containerRef.current && chartRef.current) {
          chartRef.current.applyOptions({
            width: containerRef.current.offsetWidth,
          });
        }
      };
      
      window.addEventListener('resize', handleResize);
      
      return () => {
        window.removeEventListener('resize', handleResize);
        if (wsRef.current) {
          wsRef.current.close();
          wsRef.current = null;
        }
        chart.remove();
        chartRef.current = null;
        mainSeriesRef.current = null;
        volumeSeriesRef.current = null;
        maSeriesRef.current = null;
        emaSeriesRef.current = null;
        livePriceSeriesRef.current = null;
        latestCandlesRef.current = [];
      };
    } catch (err) {
      console.error('Chart error:', err);
    }
  }, [chartType]);

  // Seed chart from REST history using setData(...)
  useEffect(() => {
    if (!mainSeriesRef.current || !volumeSeriesRef.current) return;

    const chartData = data
      .map((d) => {
        const tRaw = Number(d.time);
        const t = tRaw > 10_000_000_000 ? Math.floor(tRaw / 1000) : Math.floor(tRaw);
        return {
          time: t,
          open: Number(d.open),
          high: Number(d.high),
          low: Number(d.low),
          close: Number(d.close),
          volume: Number(d.volume || 0),
        };
      })
      .filter((d) => Number.isFinite(d.time) && d.time > 0 && Number.isFinite(d.open) && Number.isFinite(d.high) && Number.isFinite(d.low) && Number.isFinite(d.close))
      .sort((a, b) => a.time - b.time);

    latestCandlesRef.current = chartData;

    const isCandlestick = mainSeriesTypeRef.current === 'candlestick';
    const mainPoints = isCandlestick
      ? chartData.map((d) => ({
          time: d.time,
          open: d.open,
          high: d.high,
          low: d.low,
          close: d.close,
        }))
      : chartData.map((d) => ({
          time: d.time,
          value: d.close,
        }));

    const volumePoints = chartData.map((d) => ({
      time: d.time,
      value: d.volume,
      color: d.close >= d.open ? 'rgba(62, 245, 181, 0.3)' : 'rgba(255, 95, 132, 0.3)',
    }));

    mainSeriesRef.current.setData(mainPoints);
    volumeSeriesRef.current.setData(volumePoints);

    const closes = chartData.map((d) => d.close);
    const sma20 = buildSMA(closes, 20);
    const ema20 = buildEMA(closes, 20);
    const maPoints = sma20
      .map((v, i) => (v === null ? null : { time: chartData[i].time, value: v }))
      .filter(Boolean);
    const emaPoints = ema20
      .map((v, i) => (v === null ? null : { time: chartData[i].time, value: v }))
      .filter(Boolean);

    maSeriesRef.current?.setData(showMA ? maPoints : []);
    emaSeriesRef.current?.setData(showEMA ? emaPoints : []);
    livePriceSeriesRef.current?.setData(
      chartData.map((d) => ({
        time: d.time,
        value: d.close,
      }))
    );

    chartRef.current?.timeScale().fitContent();
  }, [data, showMA, showEMA]);

  // Live update from AVE WSS price stream using token-id (or pair-id fallback).
  useEffect(() => {
    if (!chain || !mainSeriesRef.current) return;

    const chainNorm = String(chain || '').trim().toLowerCase();
    const tokenAddr = String(tokenAddress || '').trim();
    const pairId = String(pairAddress || '').trim();
    const preferredId = tokenAddr
      ? `${tokenAddr}-${chainNorm}`
      : pairId
        ? (pairId.toLowerCase().endsWith(`-${chainNorm}`) ? pairId : `${pairId}-${chainNorm}`)
        : '';

    if (!preferredId) {
      setStreamState('no-source');
      return;
    }

    discoveredPairRef.current = '';
    lastTickMsRef.current = 0;
    setStreamState('connecting');

    const ws = new WebSocket('wss://wss.ave-api.xyz');
    wsRef.current = ws;

    const healthTimer = window.setInterval(() => {
      if (!lastTickMsRef.current) return;
      if (Date.now() - lastTickMsRef.current > STALE_AFTER_MS) {
        setStreamState((prev) => (prev === 'stale' ? prev : 'stale'));
      }
    }, 5000);

    ws.onopen = () => {
      setStreamState('subscribed');
      const subscribe = {
        jsonrpc: '2.0',
        method: 'subscribe',
        params: ['price', [preferredId]],
        id: 1,
      };
      ws.send(JSON.stringify(subscribe));
      console.log('ws subscribe', subscribe);
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        const item = msg?.result?.prices?.[0];
        if (!item) return;

        const streamPair = String(item.pair || '').trim();
        if (streamPair && streamPair !== discoveredPairRef.current) {
          discoveredPairRef.current = streamPair;
          onPairDiscoveredRef.current?.(streamPair);
        }

        const price = Number(item.uprice || item.last_price || 0);
        const tRaw = Number(item.time || 0);
        const time = tRaw > 10_000_000_000 ? Math.floor(tRaw / 1000) : Math.floor(tRaw);
        if (!Number.isFinite(price) || price <= 0) return;
        if (!Number.isFinite(time) || time <= 0) return;

        lastTickMsRef.current = Date.now();
        setStreamState((prev) => (prev === 'live' ? prev : 'live'));

        const intervalSeconds = Math.max(60, Number(intervalMinutes || 60) * 60);
        const candleTime = Math.floor(time / intervalSeconds) * intervalSeconds;
        livePriceSeriesRef.current?.update({ time: candleTime, value: price });

        const candles = latestCandlesRef.current.slice();
        if (!candles.length) {
          candles.push({
            time: candleTime,
            open: price,
            high: price,
            low: price,
            close: price,
            volume: 0,
          });
        } else {
          const last = candles[candles.length - 1];
          if (last.time === candleTime) {
            candles[candles.length - 1] = {
              ...last,
              high: Math.max(last.high, price),
              low: Math.min(last.low, price),
              close: price,
            };
          } else if (last.time < candleTime) {
            candles.push({
              time: candleTime,
              open: last.close,
              high: Math.max(last.close, price),
              low: Math.min(last.close, price),
              close: price,
              volume: 0,
            });
          }
        }

        if (candles.length > MAX_LIVE_CANDLES) {
          candles.splice(0, candles.length - MAX_LIVE_CANDLES);
        }
        latestCandlesRef.current = candles;

        if (mainSeriesTypeRef.current === 'candlestick') {
          const last = candles[candles.length - 1];
          mainSeriesRef.current?.update({
            time: last.time,
            open: last.open,
            high: last.high,
            low: last.low,
            close: last.close,
          });
        } else {
          mainSeriesRef.current?.update({ time: candleTime, value: price });
        }

        if (showMARef.current) {
          const last20 = candles.slice(-20).map((x) => x.close);
          if (last20.length === 20) {
            const maValue = last20.reduce((acc, v) => acc + v, 0) / 20;
            maSeriesRef.current?.update({ time: candleTime, value: maValue });
          }
        }
        if (showEMARef.current) {
          const closeValues = candles.map((x) => x.close);
          const emaSeries = buildEMA(closeValues, 20);
          const emaValue = emaSeries[emaSeries.length - 1];
          if (Number.isFinite(emaValue)) {
            emaSeriesRef.current?.update({ time: candleTime, value: emaValue });
          }
        }
      } catch (err) {
        console.error('ws parse error', err);
      }
    };

    ws.onerror = (err) => {
      console.error('ws error', err);
      setStreamState('error');
    };

    ws.onclose = () => {
      setStreamState((prev) => (prev === 'error' ? prev : 'disconnected'));
    };

    return () => {
      window.clearInterval(healthTimer);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [tokenAddress, pairAddress, chain, intervalMinutes, chartType]);

  const statusLabelMap = {
    idle: 'Idle',
    'no-source': 'No ID',
    connecting: 'Connecting',
    subscribed: 'Subscribed',
    live: 'Live',
    stale: 'Stale',
    disconnected: 'Disconnected',
    error: 'Error',
  };

  const statusColorMap = {
    idle: 'rgba(143, 162, 201, 0.85)',
    'no-source': 'rgba(255, 184, 77, 0.9)',
    connecting: 'rgba(114, 217, 255, 0.9)',
    subscribed: 'rgba(114, 217, 255, 0.9)',
    live: 'rgba(67, 255, 189, 0.9)',
    stale: 'rgba(255, 184, 77, 0.95)',
    disconnected: 'rgba(255, 95, 132, 0.95)',
    error: 'rgba(255, 95, 132, 0.95)',
  };

  return (
    <div style={{ position: 'relative', width: '100%', height: '500px' }}>
      <div 
        ref={containerRef} 
        style={{ 
          width: '100%', 
          height: '500px',
          borderRadius: '8px',
          overflow: 'hidden',
          background: 'rgba(10, 10, 10, 0.9)'
        }} 
      />
      <div
        style={{
          position: 'absolute',
          right: '10px',
          top: '10px',
          borderRadius: '999px',
          border: `1px solid ${statusColorMap[streamState] || statusColorMap.idle}`,
          color: statusColorMap[streamState] || statusColorMap.idle,
          background: 'rgba(4, 10, 22, 0.78)',
          padding: '4px 10px',
          fontSize: '11px',
          letterSpacing: '0.03em',
          textTransform: 'uppercase',
          pointerEvents: 'none',
        }}
      >
        {statusLabelMap[streamState] || 'Idle'}
      </div>
    </div>
  );
}
