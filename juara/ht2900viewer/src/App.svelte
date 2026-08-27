<script lang="ts">
  import FileLoader from './components/FileLoader.svelte';
  import RangeFilter from './components/RangeFilter.svelte';
  import Plot3D from './components/Plot3D.svelte';
  import GainCurvePlot from './components/GainCurvePlot.svelte';
  import {
    aggregateData,
    applyFilters,
    computeFilterRanges,
  } from './lib/aggregateData';
  import type { FilterRanges, GridSearchRow, AggregatedPoint } from './lib/types';

  let rawRows = $state<GridSearchRow[]>([]);
  let errorMessage = $state<string | null>(null);
  let selectedPoint = $state<AggregatedPoint | null>(null);

  const aggregated = $derived(aggregateData(rawRows));

  const fullExtents = $derived(
    aggregated.length > 0 ? computeFilterRanges(aggregated) : null,
  );

  let filterRanges = $state<FilterRanges | null>(null);

  $effect(() => {
    if (!fullExtents) {
      filterRanges = null;
      return;
    }

    filterRanges = {
      maxdepth: [...fullExtents.maxdepth],
      minsplit: [...fullExtents.minsplit],
      minbucket: [...fullExtents.minbucket],
      ganancia_test_mean: [...fullExtents.ganancia_test_mean],
    };
  });

  const filtered = $derived(
    filterRanges ? applyFilters(aggregated, filterRanges) : [],
  );

  $effect(() => {
    filtered;
    selectedPoint = null;
  });

  function handleSelect(point: AggregatedPoint | null) {
    selectedPoint = point;
  }

  function handleLoad(rows: GridSearchRow[]) {
    errorMessage = null;
    rawRows = rows;
  }

  function handleError(message: string) {
    errorMessage = message;
    rawRows = [];
  }

  function updateRange(
    key: keyof FilterRanges,
    min: number,
    max: number,
  ) {
    if (!filterRanges) return;
    filterRanges = { ...filterRanges, [key]: [min, max] };
  }

  function formatNumber(v: number) {
    return Number.isInteger(v) ? String(v) : v.toFixed(1);
  }
</script>

<div class="app">
  <header>
    <h1>HT2900 3D Viewer</h1>
    <p class="subtitle">
      gridsearch_detalle.txt · cp ≠ 0 · agrupado por maxdepth, minsplit, minbucket
    </p>
  </header>

  <div class="layout">
    <aside class="controls">
      <FileLoader onload={handleLoad} onerror={handleError} />

      {#if errorMessage}
        <p class="error">{errorMessage}</p>
      {/if}

      {#if aggregated.length > 0 && filterRanges && fullExtents}
        <p class="stats">
          {filtered.length} / {aggregated.length} puntos · {rawRows.length} filas
          crudas
        </p>

        <RangeFilter
          label="maxdepth"
          min={fullExtents.maxdepth[0]}
          max={fullExtents.maxdepth[1]}
          valueMin={filterRanges.maxdepth[0]}
          valueMax={filterRanges.maxdepth[1]}
          format={formatNumber}
          onchange={(min, max) => updateRange('maxdepth', min, max)}
        />
        <RangeFilter
          label="minsplit"
          min={fullExtents.minsplit[0]}
          max={fullExtents.minsplit[1]}
          valueMin={filterRanges.minsplit[0]}
          valueMax={filterRanges.minsplit[1]}
          format={formatNumber}
          onchange={(min, max) => updateRange('minsplit', min, max)}
        />
        <RangeFilter
          label="minbucket"
          min={fullExtents.minbucket[0]}
          max={fullExtents.minbucket[1]}
          valueMin={filterRanges.minbucket[0]}
          valueMax={filterRanges.minbucket[1]}
          format={formatNumber}
          onchange={(min, max) => updateRange('minbucket', min, max)}
        />
        <RangeFilter
          label="ganancia_test_mean"
          min={fullExtents.ganancia_test_mean[0]}
          max={fullExtents.ganancia_test_mean[1]}
          valueMin={filterRanges.ganancia_test_mean[0]}
          valueMax={filterRanges.ganancia_test_mean[1]}
          format={formatNumber}
          onchange={(min, max) => updateRange('ganancia_test_mean', min, max)}
        />
      {/if}
    </aside>

    <main class="plots">
      <Plot3D
        points={filtered}
        {selectedPoint}
        onselect={handleSelect}
      />
      <GainCurvePlot
        points={filtered}
        {selectedPoint}
        onselect={handleSelect}
      />
    </main>
  </div>
</div>

<style>
  .app {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    padding: 1rem 1.25rem;
  }

  header {
    flex-shrink: 0;
    margin-bottom: 1rem;
  }

  h1 {
    margin: 0 0 0.25rem;
    font-size: 1.5rem;
  }

  .subtitle {
    margin: 0;
    font-size: 0.85rem;
    color: var(--text);
  }

  .layout {
    display: flex;
    flex: 1;
    gap: 1.25rem;
    min-height: 0;
    align-items: stretch;
  }

  .controls {
    flex: 0 0 260px;
    min-width: 220px;
    overflow-y: auto;
  }

  main.plots {
    flex: 1;
    min-width: 0;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    width: 100%;
    max-width: 920px;
  }

  .stats {
    font-size: 0.85rem;
    color: var(--text);
    margin: 0 0 1rem;
    font-family: var(--mono);
  }

  .error {
    color: #e74c3c;
    font-size: 0.85rem;
    margin: 0 0 1rem;
  }

  @media (max-width: 900px) {
    .layout {
      flex-direction: column;
    }

    .controls {
      flex: none;
      width: 100%;
    }

    main.plots {
      min-height: 45vh;
    }

    :global(.plot-container:last-child .plot-frame) {
      min-height: 240px;
    }
  }
</style>
