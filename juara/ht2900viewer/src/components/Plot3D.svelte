<script lang="ts">
  import { drag } from 'd3-drag';
  import { pointer, select } from 'd3-selection';
  import { scaleLinear, scaleSequential } from 'd3-scale';
  import { interpolatePlasma } from 'd3-scale-chromatic';
  import { extent } from 'd3-array';
  import { project3d } from '../lib/project3d';
  import {
    AXES,
    floorGrid,
    formatAxisValue,
    formatGanancia,
    WIRE_EDGES,
  } from '../lib/plotScene';
  import type { AggregatedPoint, Rotation } from '../lib/types';
  import { pointKey } from '../lib/gainCurve';

  interface Props {
    points: AggregatedPoint[];
    selectedPoint?: AggregatedPoint | null;
    onselect?: (point: AggregatedPoint | null) => void;
  }

  let { points, selectedPoint = null, onselect }: Props = $props();

  let frameEl: HTMLDivElement | undefined = $state();
  let width = $state(800);
  let height = $state(600);
  let rotation = $state<Rotation>({ yaw: 0.85, pitch: 0.45 });
  let overlayEl: SVGRectElement | undefined = $state();
  let tooltipAnchor = $state<{ x: number; y: number } | null>(null);
  let zoom = $state(1);

  const margin = 40;
  const MIN_ZOOM = 0.5;
  const MAX_ZOOM = 2.5;
  const ZOOM_STEP = 1.12;
  const basePlotScale = $derived(Math.min(width, height) * 0.28);
  const plotScale = $derived(basePlotScale * zoom);

  function zoomIn() {
    zoom = Math.min(MAX_ZOOM, zoom * ZOOM_STEP);
  }

  function zoomOut() {
    zoom = Math.max(MIN_ZOOM, zoom / ZOOM_STEP);
  }

  function resetZoom() {
    zoom = 1;
  }

  function applyWheelZoom(deltaY: number) {
    const factor = deltaY > 0 ? 1 / ZOOM_STEP : ZOOM_STEP;
    zoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom * factor));
  }

  const selectedKey = $derived(
    selectedPoint ? pointKey(selectedPoint) : null,
  );

  function findPointAt(svgX: number, svgY: number) {
    const hitPad = 8;
    const sorted = [...projected].sort((a, b) => b.screen.z - a.screen.z);

    for (const item of sorted) {
      const dx = item.screen.x - svgX;
      const dy = item.screen.y - svgY;
      if (Math.hypot(dx, dy) <= item.radius + hitPad) return item;
    }

    return null;
  }

  function selectPoint(item: (typeof projected)[number] | null) {
    onselect?.(item?.point ?? null);
  }

  type SceneScales = {
    xExtent: [number, number];
    yExtent: [number, number];
    zExtent: [number, number];
    xScale: (v: number) => number;
    yScale: (v: number) => number;
    zScale: (v: number) => number;
    colorScale: (v: number) => string;
    colorExtent: [number, number];
  };

  const sceneScales = $derived.by((): SceneScales | null => {
    if (points.length === 0) return null;

    const xExtent = extent(points, (d) => d.minsplit) as [number, number];
    const yExtent = extent(points, (d) => d.maxdepth) as [number, number];
    const zExtent = extent(points, (d) => d.minbucket) as [number, number];
    const colorExtent = extent(points, (d) => d.ganancia_test_mean) as [
      number,
      number,
    ];

    return {
      xExtent,
      yExtent,
      zExtent,
      xScale: scaleLinear().domain(xExtent).range([-1, 1]),
      yScale: scaleLinear().domain(yExtent).range([-1, 1]),
      zScale: scaleLinear().domain(zExtent).range([-1, 1]),
      colorScale: scaleSequential(interpolatePlasma).domain(colorExtent),
      colorExtent,
    };
  });

  function projectNorm(
    x: number,
    y: number,
    z: number,
  ): { x: number; y: number; z: number } {
    return project3d({ x, y, z }, rotation, width, height, plotScale);
  }

  const wireframe = $derived.by(() => {
    if (!sceneScales) return [];

    return WIRE_EDGES.map(([a, b]) => {
      const p1 = projectNorm(a.x, a.y, a.z);
      const p2 = projectNorm(b.x, b.y, b.z);
      return {
        x1: p1.x,
        y1: p1.y,
        x2: p2.x,
        y2: p2.y,
        depth: (p1.z + p2.z) / 2,
      };
    });
  });

  const gridLines = $derived.by(() => {
    if (!sceneScales) return [];

    return floorGrid(6).map(([a, b]) => {
      const p1 = projectNorm(a.x, a.y, a.z);
      const p2 = projectNorm(b.x, b.y, b.z);
      return {
        x1: p1.x,
        y1: p1.y,
        x2: p2.x,
        y2: p2.y,
        depth: (p1.z + p2.z) / 2,
      };
    });
  });

  const axisScene = $derived.by(() => {
    if (!sceneScales) return [];

    const { xExtent, yExtent, zExtent } = sceneScales;

    return AXES.map((axis) => {
      const start = projectNorm(axis.from.x, axis.from.y, axis.from.z);
      const end = projectNorm(axis.to.x, axis.to.y, axis.to.z);
      const labelPos = projectNorm(
        axis.tickAt.x,
        axis.tickAt.y,
        axis.tickAt.z,
      );

      const extentMap = {
        minsplit: xExtent,
        maxdepth: yExtent,
        minbucket: zExtent,
      };
      const [lo, hi] = extentMap[axis.key];

      const originLabel = projectNorm(
        axis.from.x + 0.08,
        axis.from.y + 0.08,
        axis.from.z + 0.08,
      );

      return {
        ...axis,
        x1: start.x,
        y1: start.y,
        x2: end.x,
        y2: end.y,
        labelX: labelPos.x,
        labelY: labelPos.y,
        lo,
        hi,
        originX: originLabel.x,
        originY: originLabel.y,
      };
    });
  });

  const projected = $derived.by(() => {
    if (!sceneScales) return [];

    const { xScale, yScale, zScale, colorScale } = sceneScales;

    const items = points.map((p) => {
      const screen = projectNorm(
        xScale(p.minsplit),
        yScale(p.maxdepth),
        zScale(p.minbucket),
      );
      return {
        point: p,
        screen,
        color: colorScale(p.ganancia_test_mean),
      };
    });

    const zValues = items.map((d) => d.screen.z);
    const zMin = Math.min(...zValues);
    const zMax = Math.max(...zValues);
    const zSpan = zMax - zMin || 1;

    return items
      .map((item) => ({
        ...item,
        opacity: 0.45 + 0.55 * ((item.screen.z - zMin) / zSpan),
        radius: 2.5 + 2 * ((item.screen.z - zMin) / zSpan),
      }))
      .sort((a, b) => a.screen.z - b.screen.z);
  });

  const legend = $derived.by(() => {
    if (!sceneScales) return null;

    const { colorExtent } = sceneScales;
    const legendWidth = 200;
    const legendHeight = 14;
    const legendX = width - legendWidth - margin;
    const legendY = height - margin - 28;

    const stops = Array.from({ length: 12 }, (_, i) => {
      const t = i / 11;
      const value = colorExtent[0] + t * (colorExtent[1] - colorExtent[0]);
      const colorScale = scaleSequential(interpolatePlasma).domain(colorExtent);
      return { offset: `${t * 100}%`, color: colorScale(value) };
    });

    return { legendX, legendY, legendWidth, legendHeight, colorExtent, stops };
  });

  $effect(() => {
    points;
    zoom = 1;
  });

  $effect(() => {
    if (!selectedPoint || !sceneScales) {
      tooltipAnchor = null;
      return;
    }

    const { xScale, yScale, zScale } = sceneScales;
    const screen = projectNorm(
      xScale(selectedPoint.minsplit),
      yScale(selectedPoint.maxdepth),
      zScale(selectedPoint.minbucket),
    );
    tooltipAnchor = { x: screen.x, y: screen.y };
  });

  $effect(() => {
    if (!frameEl) return;

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const { width: w, height: h } = entry.contentRect;
      width = Math.max(320, Math.floor(w));
      height = Math.max(280, Math.floor(h));
    });

    observer.observe(frameEl);
    return () => observer.disconnect();
  });

  $effect(() => {
    if (!overlayEl) return;

    let dragged = false;

    const dragBehavior = drag<SVGRectElement, unknown>()
      .on('start', () => {
        dragged = false;
      })
      .on('drag', (event) => {
        dragged = true;
        rotation = {
          yaw: rotation.yaw + event.dx * 0.008,
          pitch: rotation.pitch + event.dy * 0.008,
        };
      })
      .on('end', (event) => {
        if (dragged) return;

        const [svgX, svgY] = pointer(event, overlayEl);
        selectPoint(findPointAt(svgX, svgY));
      });

    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      applyWheelZoom(event.deltaY);
    };

    const node = overlayEl;
    const el = select(node);
    el.call(dragBehavior);
    node.addEventListener('wheel', onWheel, { passive: false });

    return () => {
      el.on('.drag', null);
      node.removeEventListener('wheel', onWheel);
    };
  });
</script>

<div class="plot-container">
  <div class="plot-frame" bind:this={frameEl}>
  {#if points.length > 0}
    <div class="zoom-controls" aria-label="Controles de zoom">
      <button type="button" class="zoom-btn" onclick={zoomOut} title="Alejar">−</button>
      <span class="zoom-label">{Math.round(zoom * 100)}%</span>
      <button type="button" class="zoom-btn" onclick={zoomIn} title="Acercar">+</button>
      <button type="button" class="zoom-reset" onclick={resetZoom}>Restablecer</button>
    </div>
  {/if}
  <svg
    {width}
    {height}
    class="plot-svg"
    role="img"
    aria-label="Scatter 3D de hiperparámetros"
  >
    <defs>
      <filter id="point-shadow" x="-50%" y="-50%" width="200%" height="200%">
        <feDropShadow dx="0" dy="1" stdDeviation="1.5" flood-opacity="0.25" />
      </filter>
    </defs>

    <rect width={width} height={height} class="plot-bg" />

    {#if points.length === 0}
      <text x={width / 2} y={height / 2} text-anchor="middle" class="empty-hint">
        Cargue un archivo para visualizar
      </text>
    {:else}
      <g class="grid-layer">
        {#each gridLines as line, i (i)}
          <line
            x1={line.x1}
            y1={line.y1}
            x2={line.x2}
            y2={line.y2}
            class="grid-line"
            opacity={0.15 + 0.2 * ((line.depth + 2) / 4)}
          />
        {/each}
      </g>

      <g class="wireframe-layer">
        {#each wireframe as edge, i (i)}
          <line
            x1={edge.x1}
            y1={edge.y1}
            x2={edge.x2}
            y2={edge.y2}
            class="wire-edge"
            opacity={0.35 + 0.35 * ((edge.depth + 2) / 4)}
          />
        {/each}
      </g>

      <g class="axes-layer">
        {#each axisScene as axis (axis.key)}
          <line
            x1={axis.x1}
            y1={axis.y1}
            x2={axis.x2}
            y2={axis.y2}
            stroke={axis.color}
            stroke-width="2.5"
            stroke-linecap="round"
            opacity="0.9"
          />
          <circle
            cx={axis.x2}
            cy={axis.y2}
            r="3"
            fill={axis.color}
            opacity="0.95"
          />
          <g transform="translate({axis.labelX}, {axis.labelY})">
            <rect
              x="-42"
              y="-22"
              width="84"
              height="18"
              rx="4"
              class="axis-label-bg"
            />
            <text text-anchor="middle" dy="-8" class="axis-label" fill={axis.color}>
              {axis.label}
            </text>
          </g>
          <text
            x={axis.originX}
            y={axis.originY}
            class="axis-tick"
            fill={axis.color}
            opacity="0.75"
          >
            {formatAxisValue(axis.lo)}
          </text>
          <text
            x={axis.labelX}
            y={axis.labelY + 14}
            text-anchor="middle"
            class="axis-tick"
            fill={axis.color}
          >
            {formatAxisValue(axis.hi)}
          </text>
        {/each}
      </g>

      <g class="points-layer" filter="url(#point-shadow)">
        {#each projected as item (pointKey(item.point))}
          <circle
            cx={item.screen.x}
            cy={item.screen.y}
            r={item.radius}
            fill={item.color}
            stroke={pointKey(item.point) === selectedKey ? 'var(--accent)' : 'rgba(255,255,255,0.5)'}
            stroke-width={pointKey(item.point) === selectedKey ? 2.25 : 0.75}
            opacity={item.opacity}
            class:selected={pointKey(item.point) === selectedKey}
          />
        {/each}
      </g>

      {#if legend}
        <g class="legend" transform="translate({legend.legendX}, {legend.legendY})">
          <rect
            x="-8"
            y="-22"
            width={legend.legendWidth + 16}
            height="52"
            rx="8"
            class="legend-bg"
          />
          <text x="0" y="-8" class="legend-title">ganancia_test_mean</text>
          <defs>
            <linearGradient id="color-legend" x1="0%" y1="0%" x2="100%" y2="0%">
              {#each legend.stops as stop}
                <stop offset={stop.offset} stop-color={stop.color} />
              {/each}
            </linearGradient>
          </defs>
          <rect
            x="0"
            y="0"
            width={legend.legendWidth}
            height={legend.legendHeight}
            rx="3"
            fill="url(#color-legend)"
            stroke="var(--plot-panel-stroke)"
          />
          <text x="0" y="32" class="legend-tick">
            {formatGanancia(legend.colorExtent[0])}
          </text>
          <text
            x={legend.legendWidth}
            y="32"
            text-anchor="end"
            class="legend-tick"
          >
            {formatGanancia(legend.colorExtent[1])}
          </text>
        </g>
      {/if}

      <rect
        bind:this={overlayEl}
        x="0"
        y="0"
        width={width}
        height={height}
        fill="transparent"
        class="drag-overlay"
      />
    {/if}
  </svg>
  {#if selectedPoint && tooltipAnchor}
    <div
      class="point-tooltip"
      style:left="{tooltipAnchor.x}px"
      style:top="{tooltipAnchor.y}px"
      role="status"
    >
      <dl>
        <div>
          <dt>maxdepth</dt>
          <dd>{formatAxisValue(selectedPoint.maxdepth)}</dd>
        </div>
        <div>
          <dt>minsplit</dt>
          <dd>{formatAxisValue(selectedPoint.minsplit)}</dd>
        </div>
        <div>
          <dt>minbucket</dt>
          <dd>{formatAxisValue(selectedPoint.minbucket)}</dd>
        </div>
        <div>
          <dt>ganancia_test_mean</dt>
          <dd>{formatGanancia(selectedPoint.ganancia_test_mean)}</dd>
        </div>
        <div>
          <dt>n</dt>
          <dd>{selectedPoint.n}</dd>
        </div>
      </dl>
    </div>
  {/if}
  </div>
  <p class="hint">
    <span class="hint-icon">↻</span> Arrastre para rotar · rueda para zoom · clic en un punto para ver valores
  </p>
</div>

<style>
  .plot-container {
    flex: 1;
    min-width: 0;
    min-height: 0;
    max-width: 920px;
    display: flex;
    flex-direction: column;
  }

  .plot-frame {
    position: relative;
    flex: 1;
    min-height: 280px;
    max-height: min(68vh, 580px);
    min-width: 0;
  }

  .plot-svg {
    display: block;
    width: 100%;
    height: 100%;
  }

  .zoom-controls {
    position: absolute;
    top: 0.65rem;
    right: 0.65rem;
    z-index: 3;
    display: flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.3rem 0.45rem;
    border-radius: 8px;
    border: 1px solid var(--plot-panel-stroke);
    background: var(--plot-panel-bg);
    font-size: 0.78rem;
  }

  .zoom-btn,
  .zoom-reset {
    border: 1px solid var(--border);
    background: var(--bg);
    color: var(--text-h);
    border-radius: 5px;
    cursor: pointer;
    font: inherit;
    line-height: 1;
  }

  .zoom-btn {
    width: 1.6rem;
    height: 1.6rem;
    padding: 0;
  }

  .zoom-reset {
    padding: 0.2rem 0.45rem;
    margin-left: 0.15rem;
  }

  .zoom-btn:hover,
  .zoom-reset:hover {
    border-color: var(--accent-border);
    background: var(--accent-bg);
  }

  .zoom-label {
    min-width: 2.75rem;
    text-align: center;
    font-family: var(--mono);
    color: var(--text);
  }

  .plot-bg {
    fill: var(--plot-surface);
  }

  .grid-line {
    stroke: var(--plot-grid);
    stroke-width: 0.75;
  }

  .wire-edge {
    stroke: var(--plot-wire);
    stroke-width: 1.25;
  }

  .axis-label-bg {
    fill: var(--plot-panel-bg);
    stroke: var(--plot-panel-stroke);
  }

  .axis-label {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.03em;
    text-transform: uppercase;
  }

  .axis-tick {
    font-size: 10px;
    font-family: var(--mono);
  }

  .legend-bg {
    fill: var(--plot-panel-bg);
    stroke: var(--plot-panel-stroke);
  }

  .legend-title {
    font-size: 10px;
    fill: var(--plot-muted);
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .legend-tick {
    font-size: 10px;
    fill: var(--plot-muted);
    font-family: var(--mono);
  }

  .drag-overlay {
    cursor: grab;
  }

  .drag-overlay:active {
    cursor: grabbing;
  }

  .points-layer circle {
    pointer-events: none;
  }

  .points-layer circle.selected {
    filter: drop-shadow(0 0 4px var(--accent-border));
  }

  .point-tooltip {
    position: absolute;
    z-index: 2;
    transform: translate(12px, -50%);
    max-width: min(240px, calc(100% - 1rem));
    padding: 0.65rem 0.75rem;
    border-radius: 8px;
    border: 1px solid var(--plot-panel-stroke);
    background: var(--plot-panel-bg);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
    pointer-events: none;
    font-size: 0.8rem;
  }

  .point-tooltip dl {
    margin: 0;
    display: grid;
    gap: 0.35rem;
  }

  .point-tooltip div {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
  }

  .point-tooltip dt {
    margin: 0;
    color: var(--plot-muted);
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .point-tooltip dd {
    margin: 0;
    font-family: var(--mono);
    color: var(--text-h);
    text-align: right;
  }

  .empty-hint {
    fill: var(--plot-muted);
    font-size: 14px;
  }

  .hint {
    flex-shrink: 0;
    margin: 0.5rem 0 0;
    font-size: 0.8rem;
    color: var(--text);
    display: flex;
    align-items: center;
    gap: 0.35rem;
  }

  .hint-icon {
    opacity: 0.6;
    font-size: 0.9rem;
  }
</style>
