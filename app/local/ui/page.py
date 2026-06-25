from __future__ import annotations


def render_page() -> str:
    return """<!doctype html>
<html lang=\"ru\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>TWAP Local Client</title>
  <style>
    :root { color-scheme: dark; font-family: Arial, sans-serif; }
    body { margin: 0; background: #0d1117; color: #e6edf3; }
    main { max-width: 1120px; margin: 0 auto; padding: 24px; }
    h1 { margin: 0 0 16px; }
    details { background: #161b22; border: 1px solid #30363d; border-radius: 12px; margin: 12px 0; padding: 12px 16px; }
    summary { cursor: pointer; font-weight: 700; }
    label { display: block; font-size: 13px; color: #8b949e; margin: 10px 0 4px; }
    input, select, button { border-radius: 8px; border: 1px solid #30363d; padding: 9px 10px; background: #0d1117; color: #e6edf3; }
    button { cursor: pointer; background: #238636; border-color: #238636; font-weight: 700; }
    button.secondary { background: #21262d; border-color: #30363d; }
    button.danger { background: #da3633; border-color: #da3633; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; }
    .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: end; }
    .status { padding: 10px; border-radius: 10px; background: #0d1117; border: 1px solid #30363d; white-space: pre-wrap; }
    table { width: 100%; border-collapse: collapse; margin-top: 10px; }
    th, td { border-bottom: 1px solid #30363d; padding: 8px; text-align: left; font-size: 13px; }
    .ok { color: #3fb950; } .bad { color: #f85149; } .muted { color: #8b949e; }
  </style>
</head>
<body>
<main>
  <h1>TWAP Local Client</h1>
  <p class=\"muted\">Биржевые токены и пользовательские настройки сохраняются локально в <code>local_data/settings.json</code>.</p>

  <details open>
    <summary>1. Биржа и подключение</summary>
    <div class=\"grid\">
      <div>
        <label>Биржа</label>
        <select id=\"exchange\"></select>
      </div>
      <div>
        <label>MEXC WEB token</label>
        <input id=\"mexcToken\" placeholder=\"WEB...\" type=\"password\" />
      </div>
      <div>
        <label>Включить MEXC</label>
        <select id=\"mexcEnabled\"><option value=\"true\">Да</option><option value=\"false\">Нет</option></select>
      </div>
    </div>
    <div class=\"row\" style=\"margin-top:10px\">
      <button onclick=\"saveSettings()\">Сохранить настройки</button>
      <button class=\"secondary\" onclick=\"checkStatus()\">Проверить подключение</button>
      <button class=\"secondary\" onclick=\"loadBalance()\">Баланс</button>
    </div>
    <pre id=\"status\" class=\"status\"></pre>
  </details>

  <details>
    <summary>2. Futures активы</summary>
    <button class=\"secondary\" onclick=\"loadAssets()\">Загрузить список</button>
    <table><thead><tr><th>Символ</th><th>Min vol</th><th>Leverage</th></tr></thead><tbody id=\"assets\"></tbody></table>
  </details>

  <details open>
    <summary>3. Ручная сделка</summary>
    <div class=\"grid\">
      <div><label>Символ</label><input id=\"symbol\" value=\"BTC_USDT\" /></div>
      <div><label>Направление</label><select id=\"direction\"><option value=\"long\">Long</option><option value=\"short\">Short</option></select></div>
      <div><label>Объем</label><input id=\"volume\" type=\"number\" step=\"0.0001\" value=\"1\" /></div>
      <div><label>Плечо</label><input id=\"leverage\" type=\"number\" min=\"1\" value=\"1\" /></div>
    </div>
    <div class=\"row\" style=\"margin-top:10px\">
      <button onclick=\"openOrder()\">Открыть market</button>
      <button class=\"danger\" onclick=\"closeOrder()\">Закрыть market</button>
      <button class=\"secondary\" onclick=\"loadPositions()\">Позиции</button>
    </div>
    <pre id=\"tradeResult\" class=\"status\"></pre>
    <table><thead><tr><th>Символ</th><th>Сторона</th><th>Объем</th><th>Entry</th><th>PnL</th><th>Position ID</th></tr></thead><tbody id=\"positions\"></tbody></table>
  </details>

  <details>
    <summary>4. Сервер сигналов</summary>
    <div class=\"grid\">
      <div><label>WebSocket URL</label><input id=\"serverWs\" placeholder=\"ws://host:8090/ws/signals\" /></div>
      <div><label>HTTP URL</label><input id=\"serverHttp\" placeholder=\"http://host:8090\" /></div>
      <div><label>Device token</label><input id=\"deviceToken\" type=\"password\" /></div>
      <div><label>Слушать сигналы</label><select id=\"signalsEnabled\"><option value=\"true\">Да</option><option value=\"false\">Нет</option></select></div>
    </div>
    <div class=\"row\" style=\"margin-top:10px\">
      <button onclick=\"saveSettings()\">Сохранить</button>
      <button class=\"secondary\" onclick=\"loadSignals()\">Последние сигналы</button>
    </div>
    <table><thead><tr><th>ID</th><th>Актив</th><th>Сторона</th><th>Цена</th><th>Объем</th><th>Источник</th></tr></thead><tbody id=\"signals\"></tbody></table>
  </details>
</main>
<script>
let selected = 'mexc';
const $ = id => document.getElementById(id);
const show = (id, data) => $(id).textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
async function api(url, opts = {}) {
  const res = await fetch(url, {headers: {'content-type': 'application/json'}, ...opts});
  const data = await res.json();
  if (!res.ok || data.success === false) throw new Error(data.message || 'Ошибка запроса');
  return data;
}
async function init() {
  const exchanges = await api('/api/exchanges');
  selected = exchanges.selected || 'mexc';
  $('exchange').innerHTML = exchanges.items.map(e => `<option value="${e.name}">${e.title}</option>`).join('');
  $('exchange').value = selected;
  $('exchange').onchange = async () => { selected = $('exchange').value; await api('/api/exchanges/select', {method:'POST', body: JSON.stringify({name:selected})}); };
  const settings = await api('/api/settings');
  $('mexcEnabled').value = String(settings.exchanges?.mexc?.enabled || false);
  $('serverWs').value = settings.signals?.server_ws_url || '';
  $('serverHttp').value = settings.signals?.server_http_url || '';
  $('signalsEnabled').value = String(settings.signals?.enabled || false);
  $('volume').value = settings.trading?.default_volume || 1;
  $('leverage').value = settings.trading?.default_leverage || 1;
  $('direction').value = settings.trading?.default_direction || 'long';
  await checkStatus();
}
async function saveSettings() {
  const patch = {
    selected_exchange: selected,
    exchanges: { mexc: { enabled: $('mexcEnabled').value === 'true' } },
    trading: { default_volume: Number($('volume').value), default_leverage: Number($('leverage').value), default_direction: $('direction').value },
    signals: { enabled: $('signalsEnabled').value === 'true', server_ws_url: $('serverWs').value, server_http_url: $('serverHttp').value }
  };
  if ($('mexcToken').value) patch.exchanges.mexc.auth_token = $('mexcToken').value;
  if ($('deviceToken').value) patch.signals.device_token = $('deviceToken').value;
  show('status', await api('/api/settings', {method:'PUT', body: JSON.stringify(patch)}));
}
async function checkStatus() { try { show('status', await api(`/api/exchanges/${selected}/status`)); } catch(e) { show('status', e.message); } }
async function loadBalance() { try { show('status', await api(`/api/exchanges/${selected}/balance`)); } catch(e) { show('status', e.message); } }
async function loadAssets() {
  const data = await api(`/api/exchanges/${selected}/futures/assets`);
  $('assets').innerHTML = data.items.map(x => `<tr><td><button class="secondary" onclick="pickSymbol('${x.symbol}')">${x.symbol}</button></td><td>${x.min_vol ?? ''}</td><td>${x.min_leverage ?? ''}-${x.max_leverage ?? ''}</td></tr>`).join('');
}
function pickSymbol(symbol) { $('symbol').value = symbol; }
function orderPayload() { return { symbol: $('symbol').value, direction: $('direction').value, volume: Number($('volume').value), leverage: Number($('leverage').value), open_type: 1 }; }
async function openOrder() { try { show('tradeResult', await api(`/api/exchanges/${selected}/orders/open`, {method:'POST', body: JSON.stringify(orderPayload())})); await loadPositions(); } catch(e) { show('tradeResult', e.message); } }
async function closeOrder() { try { show('tradeResult', await api(`/api/exchanges/${selected}/orders/close`, {method:'POST', body: JSON.stringify(orderPayload())})); await loadPositions(); } catch(e) { show('tradeResult', e.message); } }
async function loadPositions() {
  const data = await api(`/api/exchanges/${selected}/positions`);
  $('positions').innerHTML = data.items.map(x => `<tr><td>${x.symbol}</td><td>${x.direction}</td><td>${x.volume}</td><td>${x.entry_price ?? ''}</td><td>${x.pnl ?? ''}</td><td>${x.position_id ?? ''}</td></tr>`).join('');
}
async function loadSignals() {
  const data = await api('/api/signals/recent');
  $('signals').innerHTML = data.items.map(x => `<tr><td>${x.signal_id || x.id || ''}</td><td>${x.asset || x.symbol || ''}</td><td>${x.side || ''}</td><td>${x.price || ''}</td><td>${x.amount_usd || ''}</td><td>${x.source || x.group_name || ''}</td></tr>`).join('');
}
init();
</script>
</body>
</html>"""
