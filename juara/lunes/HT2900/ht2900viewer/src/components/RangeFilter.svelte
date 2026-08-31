<script lang="ts">
  interface Props {
    label: string;
    min: number;
    max: number;
    valueMin: number;
    valueMax: number;
    format?: (v: number) => string;
    onchange: (min: number, max: number) => void;
  }

  let {
    label,
    min,
    max,
    valueMin,
    valueMax,
    format = (v) => String(v),
    onchange,
  }: Props = $props();

  function handleMinInput(event: Event) {
    const v = Number((event.currentTarget as HTMLInputElement).value);
    onchange(Math.min(v, valueMax), valueMax);
  }

  function handleMaxInput(event: Event) {
    const v = Number((event.currentTarget as HTMLInputElement).value);
    onchange(valueMin, Math.max(v, valueMin));
  }
</script>

<div class="range-filter">
  <div class="header">
    <span class="label">{label}</span>
    <span class="values">{format(valueMin)} – {format(valueMax)}</span>
  </div>
  <div class="sliders">
    <input
      type="range"
      min={min}
      max={max}
      step="any"
      value={valueMin}
      oninput={handleMinInput}
    />
    <input
      type="range"
      min={min}
      max={max}
      step="any"
      value={valueMax}
      oninput={handleMaxInput}
    />
  </div>
</div>

<style>
  .range-filter {
    margin-bottom: 1rem;
  }

  .header {
    display: flex;
    justify-content: space-between;
    font-size: 0.85rem;
    margin-bottom: 0.25rem;
  }

  .label {
    color: var(--text-h);
    font-weight: 500;
  }

  .values {
    color: var(--text);
    font-family: var(--mono);
    font-size: 0.8rem;
  }

  .sliders {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }

  input[type='range'] {
    width: 100%;
    accent-color: var(--accent);
  }
</style>
