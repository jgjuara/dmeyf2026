<script lang="ts">
  import { area, line } from 'd3-shape';
  import { scaleLinear } from 'd3-scale';
  import { max, min } from 'd3-array';
  import { buildGainCurve, pointKey } from '../lib/gainCurve';
  import { formatGanancia } from '../lib/plotScene';
  import type { AggregatedPoint, RankedGainPoint } from '../lib/types';

  interface Props {
    points: AggregatedPoint[];
    selectedPoint?: AggregatedPoint | null;
    onselect?: (point: AggregatedPoint | null) => void;
  }

  let { points, selectedPoint = null, onselect }: Props = $props();

  let frameEl: HTMLDivElement | undefined = $state();
  let overlayEl: SVGRectElement | undefined = $state();
  let width = $state(800);
  let tooltipAnchor = $state<{ x: number; y: number } | null>(null);

  const height = 280;
  const margin = { top: 24, right: 24, bottom: 44, left: 56 };
  const plotWidth = $derived(Math.max(0, width - margin.left - margin.right));
  const plotHeight = $derived(Math.max(0, height - margin.top - margin.bottom));

  const curve = $derived(buildGainCurve(points));

  const scene = $derived.by(() => {
    if (curve.length === 0) return null;

    const yLo =
      min(curve, (d) => d.ganancia_test_mean - d.ganancia_test_std) ?? 0;
    const yHi =
      max(curve, (d) => d.ganancia_test_mean + d.ganancia_test_std) ?? 0;
    const yPad = (yHi - yLo) * 0.05 || 1;

    const xScale = scaleLinear()
      .domain([1, curve.length])
      .range([0, plotWidth]);

    const yScale = scaleLinear()
      .domain([yLo - yPad, yHi + yPad])
      .range([plotHeight, 0]);

    const areaPath = area<RankedGainPoint>()
      .x((d) => xScale(d.rank))
      .y0((d) => yScale(d.ganancia_test_mean - d.ganancia_test_std))
      .y1((d) => yScale(d.ganancia_test_mean + d.ganancia_test_std))(curve);

    const linePath = line<RankedGainPoint>()
      .x((d) => xScale(d.rank))
      .y((d) => yScale(d.ganancia_test_mean))(curve);

    const xTicks = xScale.ticks(Math.min(8, curve.length)).filter(Number.isInteger);
    const yTicks = yScale.ticks(5);

    return {
      xScale,
      yScale,
      areaPath,
      linePath,
      xTicks,
      yTicks,
      yExtent: [yLo - yPad, yHi + yPad] as [number, number],
    };
  });

  const projectedPoints = $derived.by(() => {
    if (!scene) return [];

    const { xScale, yScale } = scene;
    return curve.map((point) => ({
      point,
      cx: xScale(point.rank),
      cy: yScale(point.ganancia_test_mean),
      yLow: yScale(point.ganancia_test_mean - point.ganancia_test_std),
      yHigh: yScale(point.ganancia_test_mean + point.ganancia_test_std),
    }));
  });

  const selectedKey = $derived(
    selectedPoint ? pointKey(selectedPoint) : null,
  );

  const selectedCurveItem = $derived(
    selectedKey
      ? (projectedPoints.find((p) => pointKey(p.point) === selectedKey) ?? null)
      : null,
  );

  function findPointAt(plotX: number, plotY: number) {
    const hitPad = 10;
    let best: (typeof projectedPoints)[number] | null = null;
    let bestDist = Infinity;

    for (const item of projectedPoints) {
      const dist = Math.hypot(item.cx - plotX, item.cy - plotY);
      if (dist <= hitPad && dist < bestDist) {
        best = item;
        bestDist = dist;
      }
    }

    return best;
  }

  function selectPoint(item: (typeof projectedPoints)[number] | null) {
    onselect?.(item?.point ?? null);
  }

  function handlePlotClick(event: MouseEvent) {
    if (!overlayEl) return;
    const rect = overlayEl.getBoundingClientRect();
    const plotX = event.clientX - rect.left;
    const plotY = event.clientY - rect.top;
    selectPoint(findPointAt(plotX, plotY));
  }

  $effect(() => {
    if (!selectedCurveItem) {
      tooltipAnchor = null;
      return;
    }

    tooltipAnchor = {
      x: margin.left + selectedCurveItem.cx,
      y: margin.top + selectedCurveItem.cy,
    };
  });

  $effect(() => {
    if (!overlayEl) return;

    const onClick = (event: MouseEvent) => {
      handlePlotClick(event);
    };

    overlayEl.addEventListener('click', onClick);
    return () => overlayEl?.removeEventListener('click', onClick);
  });

  $effect(() => {
    if (!frameEl) return;

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      width = Math.max(320, Math.floor(entry.contentRect.width));
    });

    observer.observe(frameEl);
    return () => observer.disconnect();
  });
</script>

<div class="plot-container">
  <div class="plot-frame" bind:this={frameEl}>
    <svg
      {width}
      {height}
      class="plot-svg"
      role="img"
      aria-label="Curva de ganancia ordenada por ranking"
    >
      <rect {width} {height} class="plot-bg" />

      {#if points.length === 0}
        <text x={width / 2} y={height / 2} text-anchor="middle" class="empty-hint">
          Sin datos
        </text>
      {:else if scene}
        <g transform="translate({margin.left}, {margin.top})">
          {#each scene.yTicks as tick (tick)}
            <line
              x1="0"
              x2={plotWidth}
              y1={scene.yScale(tick)}
              y2={scene.yScale(tick)}
              class="grid-line"
            />
          {/each}

          {#if scene.areaPath}
            <path d={scene.areaPath} class="uncertainty-band" />
          {/if}

          {#if scene.linePath}
            <path d={scene.linePath} class="gain-line" />
          {/if}

          {#if selectedCurveItem}
            <line
              x1={selectedCurveItem.cx}
              x2={selectedCurveItem.cx}
              y1={selectedCurveItem.yHigh}
              y2={selectedCurveItem.yLow}
              class="error-bar"
            />
            <line
              x1={selectedCurveItem.cx - 5}
              x2={selectedCurveItem.cx + 5}
              y1={selectedCurveItem.yHigh}
              y2={selectedCurveItem.yHigh}
              class="error-cap"
            />
            <line
              x1={selectedCurveItem.cx - 5}
              x2={selectedCurveItem.cx + 5}
              y1={selectedCurveItem.yLow}
              y2={selectedCurveItem.yLow}
              class="error-cap"
            />
            <circle
              cx={selectedCurveItem.cx}
              cy={selectedCurveItem.cy}
              r="4"
              class="selected-point"
            />
          {/if}

          <line
            x1="0"
            x2={plotWidth}
            y1={plotHeight}
            y2={plotHeight}
            class="axis-line"
          />
          <line x1="0" x2="0" y1="0" y2={plotHeight} class="axis-line" />

          {#each scene.xTicks as tick (tick)}
            <g transform="translate({scene.xScale(tick)}, {plotHeight})">
              <line y2="6" class="tick-line" />
              <text y="20" text-anchor="middle" class="axis-tick">{tick}</text>
            </g>
          {/each}

          {#each scene.yTicks as tick (tick)}
            <g transform="translate(0, {scene.yScale(tick)})">
              <line x2="-6" class="tick-line" />
              <text
                x="-10"
                dy="0.32em"
                text-anchor="end"
                class="axis-tick"
              >
                {formatGanancia(tick)}
              </text>
            </g>
          {/each}

          <text
            x={plotWidth / 2}
            y={plotHeight + 38}
            text-anchor="middle"
            class="axis-label"
          >
            Ranking
          </text>
          <text
            transform="translate(-42, {plotHeight / 2}) rotate(-90)"
            text-anchor="middle"
            class="axis-label"
          >
            ganancia_test_mean
          </text>

          <rect
            bind:this={overlayEl}
            width={plotWidth}
            height={plotHeight}
            class="plot-overlay"
          />
        </g>
      {/if}
    </svg>

    {#if selectedCurveItem && tooltipAnchor}
      <div
        class="tooltip"
        style:left="{tooltipAnchor.x}px"
        style:top="{tooltipAnchor.y}px"
      >
        <p class="tooltip-title">Ranking {selectedCurveItem.point.rank}</p>
        <dl>
          <div>
            <dt>ganancia_test_mean</dt>
            <dd>{formatGanancia(selectedCurveItem.point.ganancia_test_mean)}</dd>
          </div>
          <div>
            <dt>± std</dt>
            <dd>{formatGanancia(selectedCurveItem.point.ganancia_test_std)}</dd>
          </div>
          <div>
            <dt>maxdepth</dt>
            <dd>{selectedCurveItem.point.maxdepth}</dd>
          </div>
          <div>
            <dt>minsplit</dt>
            <dd>{selectedCurveItem.point.minsplit}</dd>
          </div>
          <div>
            <dt>minbucket</dt>
            <dd>{selectedCurveItem.point.minbucket}</dd>
          </div>
          <div>
            <dt>n</dt>
            <dd>{selectedCurveItem.point.n}</dd>
          </div>
        </dl>
      </div>
    {/if}
  </div>
  <p class="hint">
    <span class="hint-icon">◎</span> Clic en un punto para ver margen ± std
  </p>
</div>

<style>
  .plot-container {
    width: 100%;
    display: flex;
    flex-direction: column;
  }

  .plot-frame {
    position: relative;
    min-height: 280px;
    width: 100%;
  }

  .plot-svg {
    display: block;
    width: 100%;
    height: 280px;
  }

  .plot-bg {
    fill: var(--plot-surface);
  }

  .plot-overlay {
    fill: transparent;
    cursor: crosshair;
  }

  .grid-line {
    stroke: var(--plot-grid);
    stroke-width: 0.75;
    opacity: 0.5;
  }

  .uncertainty-band {
    fill: var(--accent-bg);
    stroke: none;
  }

  .gain-line {
    fill: none;
    stroke: var(--accent);
    stroke-width: 2;
    stroke-linejoin: round;
    stroke-linecap: round;
  }

  .error-bar {
    stroke: var(--accent);
    stroke-width: 2;
    pointer-events: none;
  }

  .error-cap {
    stroke: var(--accent);
    stroke-width: 2;
    pointer-events: none;
  }

  .selected-point {
    fill: var(--accent);
    stroke: var(--bg);
    stroke-width: 1.5;
    pointer-events: none;
  }

  .axis-line {
    stroke: var(--plot-wire);
    stroke-width: 1.25;
  }

  .tick-line {
    stroke: var(--plot-wire);
    stroke-width: 1;
  }

  .axis-tick {
    font-size: 10px;
    font-family: var(--mono);
    fill: var(--text);
  }

  .axis-label {
    font-size: 11px;
    font-weight: 600;
    fill: var(--text-h);
    letter-spacing: 0.03em;
  }

  .empty-hint {
    fill: var(--plot-muted);
    font-size: 0.9rem;
  }

  .tooltip {
    position: absolute;
    z-index: 4;
    transform: translate(-50%, calc(-100% - 12px));
    min-width: 11rem;
    padding: 0.55rem 0.65rem;
    border-radius: 8px;
    border: 1px solid var(--plot-panel-stroke);
    background: var(--plot-panel-bg);
    box-shadow: 0 4px 16px rgba(8, 6, 13, 0.12);
    pointer-events: none;
    font-size: 0.78rem;
  }

  .tooltip-title {
    margin: 0 0 0.35rem;
    font-weight: 600;
    color: var(--text-h);
  }

  dl {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 0.15rem 0.65rem;
    margin: 0;
  }

  dt {
    color: var(--text);
    margin: 0;
  }

  dd {
    margin: 0;
    font-family: var(--mono);
    color: var(--text-h);
    text-align: right;
  }

  .hint {
    margin: 0.45rem 0 0;
    font-size: 0.78rem;
    color: var(--plot-muted);
  }

  .hint-icon {
    margin-right: 0.25rem;
  }
</style>
