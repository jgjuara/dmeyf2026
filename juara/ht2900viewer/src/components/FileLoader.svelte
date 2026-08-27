<script lang="ts">
  import { parseGridSearch } from '../lib/parseGridSearch';
  import type { GridSearchRow } from '../lib/types';

  interface Props {
    onload: (rows: GridSearchRow[]) => void;
    onerror: (message: string) => void;
  }

  let { onload, onerror }: Props = $props();

  let inputEl: HTMLInputElement | undefined = $state();

  function openPicker() {
    inputEl?.click();
  }

  async function handleChange(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    try {
      const text = await file.text();
      const rows = parseGridSearch(text);
      onload(rows);
    } catch (err) {
      onerror(err instanceof Error ? err.message : 'Error al leer el archivo.');
    }

    input.value = '';
  }
</script>

<div class="file-loader">
  <button type="button" onclick={openPicker}>
    Cargar gridsearch_detalle.txt
  </button>
  <input
    bind:this={inputEl}
    type="file"
    accept=".txt"
    class="hidden-input"
    onchange={handleChange}
  />
</div>

<style>
  .file-loader {
    margin-bottom: 1rem;
  }

  button {
    font: inherit;
    padding: 0.5rem 1rem;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--accent-bg);
    color: var(--text-h);
    cursor: pointer;
  }

  button:hover {
    border-color: var(--accent-border);
  }

  .hidden-input {
    display: none;
  }
</style>
