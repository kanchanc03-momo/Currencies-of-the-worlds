(async () => {
  const currencySelect = document.getElementById('currency');
  const pair = document.getElementById('pair');
  const rate = document.getElementById('rate');
  const change = document.getElementById('change');
  const forecast = document.getElementById('forecast');
  const download = document.getElementById('download');
  const currencyMetric = document.querySelector('.metrics div:first-child strong');
  const freshnessMetric = document.querySelector('.metrics div:nth-child(3) strong');

  async function api(path) {
    const response = await fetch(path);
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(`${response.status} ${detail}`);
    }
    return response.json();
  }

  function formatRate(value) {
    if (!Number.isFinite(value)) return '—';
    return value < 0.1 ? value.toFixed(4) : value.toFixed(2);
  }

  async function loadCurrency(code) {
    const [history, prediction] = await Promise.all([
      api(`/history/${encodeURIComponent(code)}`),
      api(`/forecast/${encodeURIComponent(code)}`),
    ]);
    const valid = history.filter(item => item.date && Number.isFinite(item.rate));
    const current = prediction.current_rate;
    const first = valid.length ? valid[0].rate : current;
    const movement = first ? ((current / first) - 1) * 100 : 0;

    pair.textContent = `${code} / USD`;
    rate.textContent = formatRate(current);
    change.textContent = `${movement >= 0 ? '▲' : '▼'} ${Math.abs(movement).toFixed(2)}%`;
    change.className = movement >= 0 ? 'positive' : '';
    forecast.textContent = formatRate(prediction.forecast_rate);

    if (valid.length) {
      const latest = new Date(valid[valid.length - 1].date);
      freshnessMetric.textContent = latest.toLocaleDateString(undefined, {month: 'short', year: 'numeric'});
    }
  }

  try {
    const currencies = await api('/currencies');
    currencyMetric.textContent = currencies.length;
    currencySelect.innerHTML = currencies.map(code => `<option value="${code}">${code}</option>`).join('');
    const preferred = currencies.includes('EUR') ? 'EUR' : currencies[0];
    currencySelect.value = preferred;
    currencySelect.onchange = () => loadCurrency(currencySelect.value).catch(showError);
    download.onclick = () => { window.location.href = '/dataset.csv'; };
    await loadCurrency(preferred);
  } catch (error) {
    showError(error);
  }

  function showError(error) {
    console.error('Dataset loading failed:', error);
    pair.textContent = 'Dataset connection error';
    rate.textContent = '—';
    change.textContent = 'Start the site with the command in backend/README.md';
    change.className = '';
  }
})();
