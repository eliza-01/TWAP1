from __future__ import annotations


def render_page() -> str:
    return """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>TWAP Local Client</title>
  <style>
    :root { color-scheme: dark; font-family: Arial, sans-serif; }
    body { margin: 0; background: #0d1117; color: #e6edf3; }
    main { max-width: 1220px; margin: 0 auto; padding: 24px; }
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
    .status { padding: 10px; border-radius: 10px; background: #0d1117; border: 1px solid #30363d; white-space: pre-wrap; max-height: 360px; overflow: auto; }
    table { width: 100%; border-collapse: collapse; margin-top: 10px; }
    th, td { border-bottom: 1px solid #30363d; padding: 8px; text-align: left; font-size: 13px; vertical-align: top; }
    .ok { color: #3fb950; }
    .bad { color: #f85149; }
    .warn { color: #d29922; }
    .muted { color: #8b949e; }
    .pill { display: inline-block; border: 1px solid #30363d; border-radius: 999px; padding: 2px 8px; font-size: 12px; }
    .pill.ok { border-color: #238636; background: rgba(35,134,54,.14); }
    .pill.bad { border-color: #da3633; background: rgba(218,54,51,.12); }
    code { background:#0d1117; border:1px solid #30363d; border-radius:6px; padding:1px 4px; }
  </style>
</head>
<body>
<main>
  <h1>TWAP Local Client</h1>
  <p class="muted">Биржевые токены, сигналы и сделки сохраняются локально в <code>local_data/</code>.</p>

  <details open>
    <summary>1. Биржа и подключение</summary>
    <div class="grid">
      <div><label>Биржа</label><select id="exchange"></select></div>
      <div><label>MEXC WEB token</label><input id="mexcToken" placeholder="WEB..." type="password" /></div>
      <div><label>Включить MEXC</label><select id="mexcEnabled"><option value="true">Да</option><option value="false">Нет</option></select></div>
    </div>
    <div class="row" style="margin-top:10px">
      <button onclick="saveSettings()">Сохранить настройки</button>
      <button class="secondary" onclick="checkStatus()">Проверить подключение</button>
      <button class="secondary" onclick="loadBalance()">Баланс</button>
    </div>
    <pre id="status" class="status"></pre>
  </details>

  <details>
    <summary>2. Futures активы</summary>
    <button class="secondary" onclick="loadAssets()">Загрузить список</button>
    <table><thead><tr><th>Символ</th><th>Min vol</th><th>Шаг</th><th>Плечо</th><th>Contract size</th></tr></thead><tbody id="assets"></tbody></table>
  </details>

  <details open>
    <summary>3. Ручная сделка</summary>
    <div class="grid">
      <div><label>Символ</label><input id="symbol" value="BTC_USDT" onblur="loadRules()" /></div>
      <div><label>Направление</label><select id="direction"><option value="long">Long</option><option value="short">Short</option></select></div>
      <div><label>Объем</label><input id="volume" type="number" step="0.0001" value="1" /></div>
      <div><label>Плечо</label><input id="leverage" type="number" min="1" value="1" /></div>
    </div>
    <div class="row" style="margin-top:10px">
      <button onclick="openOrder()">Открыть market</button>
      <button class="danger" onclick="closeOrder()">Закрыть market</button>
      <button class="secondary" onclick="loadPositions()">Позиции</button>
      <button class="secondary" onclick="loadRules()">Минимальный объем</button>
    </div>
    <pre id="rules" class="status"></pre>
    <pre id="tradeResult" class="status"></pre>
    <table><thead><tr><th>Символ</th><th>Сторона</th><th>Объем</th><th>Entry</th><th>PnL</th><th>Position ID</th></tr></thead><tbody id="positions"></tbody></table>
  </details>

  <details open>
    <summary>4. Автоторговля по сигналам</summary>
    <p class="muted">
      Автоторговля открывает сделки только по новым <code>twap_created</code> после момента включения.
      По умолчанию берутся только сигналы, прошедшие фильтр. Опция отключения фильтра разрешает вход и по rejected-сигналам.
      Отдельный флаг может игнорировать только <code>TWAPX_MIN_USD</code>, если <code>TWAPX_MIN_TWAP_SHARE_PERCENT</code> выше заданного порога.
      Закрытие выполняется по связанному <code>twap_result</code>. Маржа isolated: <code>openType=1</code>.
      Объем сделки задаётся в USDT как notional. Если свободной маржи не хватает, клиент подберёт минимальное плечо, но не выше лимита.
    </p>
    <div class="grid">
      <div><label>Автоторговля</label><select id="autoTradingEnabled"><option value="false">Выключена</option><option value="true">Включена</option></select></div>
      <div><label>Входить минимальным объемом</label><select id="useMinVolume" onchange="applyMinVolumeFlag()"><option value="false">Нет</option><option value="true">Да, плечо 1x</option></select></div>
      <div><label>Объем сделки, USDT</label><input id="autoOrderUsdt" type="number" step="0.01" min="0.01" value="10" /></div>
      <div><label>Базовое плечо</label><input id="autoLeverage" type="number" min="1" value="1" /></div>
      <div><label>Авто-плечо при нехватке средств</label><select id="autoLeverageEnabled"><option value="true">Да</option><option value="false">Нет</option></select></div>
      <div><label>Максимальное авто-плечо</label><input id="maxAutoLeverage" type="number" min="1" value="20" /></div>
      <div><label>Отключить фильтр сигналов</label><select id="disableSignalFilters"><option value="false">Нет</option><option value="true">Да, входить и по rejected</option></select></div>
      <div><label>Игнорировать TWAPX_MIN_USD по доле рынка</label><select id="ignoreMinUsdByShare"><option value="false">Нет</option><option value="true">Да, только min USD</option></select></div>
      <div><label>Порог TWAP share, %</label><input id="minUsdOverrideShare" type="number" step="0.01" min="0.01" value="1" /></div>
    </div>
    <div class="row" style="margin-top:10px">
      <button onclick="saveSettings()">Сохранить автоторговлю</button>
      <button class="secondary" onclick="loadTradingLogs()">Обновить логи</button>
      <button class="secondary" onclick="loadOpenTrades()">Открытые авто-сделки</button>
    </div>
    <pre id="autoStatus" class="status"></pre>
    <table><thead><tr><th>Время</th><th>Тип</th><th>Действие</th><th>Символ</th><th>Сообщение</th></tr></thead><tbody id="tradeLogs"></tbody></table>
    <table><thead><tr><th>Trade key</th><th>Символ</th><th>Сторона</th><th>Маржа</th><th>Объем USDT</th><th>Контракты</th><th>Плечо</th><th>Открыт</th><th>Order</th></tr></thead><tbody id="openTrades"></tbody></table>
  </details>

  <details>
    <summary>5. Сервер сигналов</summary>
    <p class="muted">Если local и signal-server запущены в Docker Compose, используй <code>ws://signal-server:8090/ws/signals</code> и <code>http://signal-server:8090</code>. Для удалённого устройства нужен публичный <code>wss://...</code> и <code>https://...</code>.</p>
    <div class="grid">
      <div><label>WebSocket URL</label><input id="serverWs" placeholder="ws://signal-server:8090/ws/signals" /></div>
      <div><label>HTTP URL</label><input id="serverHttp" placeholder="http://signal-server:8090" /></div>
      <div><label>Device token</label><input id="deviceToken" type="password" /></div>
      <div><label>Слушать сигналы</label><select id="signalsEnabled"><option value="true">Да</option><option value="false">Нет</option></select></div>
    </div>
    <div class="row" style="margin-top:10px">
      <button onclick="saveSettings()">Сохранить</button>
      <button class="secondary" onclick="syncSignals()">Синхронизировать с сервера</button>
      <button class="secondary" onclick="loadSignals()">Последние локальные</button>
      <button class="secondary" onclick="signalStatus()">Статус</button>
    </div>
    <pre id="signalStatus" class="status"></pre>
    <table><thead><tr><th>ID</th><th>Тип</th><th>Актив</th><th>Сторона</th><th>Цена</th><th>Объем</th><th>Источник</th></tr></thead><tbody id="signals"></tbody></table>
  </details>
</main>
<script>
let selected = 'mexc';
const $ = id => document.getElementById(id);
const show = (id, data) => $(id).textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
const fmt = value => value === null || value === undefined ? '' : value;
const fmtMoney = value => value === null || value === undefined || value === '' ? '' : `$${Number(value).toFixed(2)}`;
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
  $('autoTradingEnabled').value = String(settings.trading?.auto_trading_enabled || false);
  $('useMinVolume').value = String(settings.trading?.use_min_volume || false);
  $('autoOrderUsdt').value = settings.trading?.auto_order_usdt || settings.trading?.auto_margin_usdt || 10;
  $('autoLeverage').value = settings.trading?.default_leverage || 1;
  $('autoLeverageEnabled').value = String(settings.trading?.auto_leverage_enabled ?? true);
  $('maxAutoLeverage').value = settings.trading?.max_auto_leverage || 20;
  $('disableSignalFilters').value = String(settings.trading?.disable_signal_filters || false);
  $('ignoreMinUsdByShare').value = String(settings.trading?.ignore_min_usd_by_market_share || false);
  $('minUsdOverrideShare').value = settings.trading?.min_usd_override_twap_share_percent || 1;
  applyMinVolumeFlag();
  await checkStatus();
  await signalStatus();
  await loadSignals();
  await loadTradingLogs();
  await loadOpenTrades();
}
function applyMinVolumeFlag() {
  const useMin = $('useMinVolume').value === 'true';
  $('autoOrderUsdt').disabled = useMin;
  $('autoLeverage').disabled = useMin;
  $('autoLeverageEnabled').disabled = useMin;
  $('maxAutoLeverage').disabled = useMin;
  if (useMin) {
    $('autoLeverage').value = 1;
    $('autoLeverageEnabled').value = 'false';
    $('maxAutoLeverage').value = 1;
  }
}
async function saveSettings() {
  applyMinVolumeFlag();
  const patch = {
    selected_exchange: selected,
    exchanges: { mexc: { enabled: $('mexcEnabled').value === 'true' } },
    trading: {
      default_volume: Number($('volume').value || 1),
      default_leverage: $('useMinVolume').value === 'true' ? 1 : Number($('autoLeverage').value || $('leverage').value),
      default_direction: $('direction').value,
      auto_trading_enabled: $('autoTradingEnabled').value === 'true',
      use_min_volume: $('useMinVolume').value === 'true',
      auto_order_usdt: Number($('autoOrderUsdt').value || 10),
      auto_leverage_enabled: $('useMinVolume').value === 'true' ? false : $('autoLeverageEnabled').value === 'true',
      max_auto_leverage: $('useMinVolume').value === 'true' ? 1 : Number($('maxAutoLeverage').value || 20),
      disable_signal_filters: $('disableSignalFilters').value === 'true',
      ignore_min_usd_by_market_share: $('ignoreMinUsdByShare').value === 'true',
      min_usd_override_twap_share_percent: Number($('minUsdOverrideShare').value || 1)
    },
    signals: { enabled: $('signalsEnabled').value === 'true', server_ws_url: $('serverWs').value, server_http_url: $('serverHttp').value }
  };
  if ($('mexcToken').value) patch.exchanges.mexc.auth_token = $('mexcToken').value;
  if ($('deviceToken').value) patch.signals.device_token = $('deviceToken').value;
  const saved = await api('/api/settings', {method:'PUT', body: JSON.stringify(patch)});
  show('status', saved);
  show('autoStatus', saved.trading);
  await signalStatus();
}
async function checkStatus() { try { show('status', await api(`/api/exchanges/${selected}/status`)); } catch(e) { show('status', e.message); } }
async function loadBalance() { try { show('status', await api(`/api/exchanges/${selected}/balance`)); } catch(e) { show('status', e.message); } }
async function loadAssets() {
  const data = await api(`/api/exchanges/${selected}/futures/assets`);
  $('assets').innerHTML = data.items.map(x => `<tr><td><button class="secondary" onclick="pickSymbol('${x.symbol}')">${x.symbol}</button></td><td>${fmt(x.min_vol)}</td><td>${fmt(x.vol_unit)}</td><td>${fmt(x.min_leverage)}-${fmt(x.max_leverage)}</td><td>${fmt(x.contract_size)}</td></tr>`).join('');
}
async function loadRules(symbol = null) {
  const current = symbol || $('symbol').value;
  try {
    const data = await api(`/api/exchanges/${selected}/futures/rules?symbol=${encodeURIComponent(current)}`);
    show('rules', {
      symbol: data.symbol,
      min_volume: data.min_volume,
      volume_step: data.volume_step,
      max_volume: data.max_volume,
      leverage: `${data.min_leverage}x-${data.max_leverage}x`,
      price: data.price,
      min_notional_usdt: data.min_notional_usdt
    });
    return data;
  } catch(e) {
    show('rules', e.message);
  }
}
async function pickSymbol(symbol) {
  $('symbol').value = symbol;
  const rules = await loadRules(symbol);
  if (rules && $('useMinVolume').value === 'true') $('volume').value = rules.min_volume;
}
function orderPayload() { return { symbol: $('symbol').value, direction: $('direction').value, volume: Number($('volume').value), leverage: Number($('leverage').value), open_type: 1 }; }
async function openOrder() { try { show('tradeResult', await api(`/api/exchanges/${selected}/orders/open`, {method:'POST', body: JSON.stringify(orderPayload())})); await loadPositions(); } catch(e) { show('tradeResult', e.message); } }
async function closeOrder() { try { show('tradeResult', await api(`/api/exchanges/${selected}/orders/close`, {method:'POST', body: JSON.stringify(orderPayload())})); await loadPositions(); } catch(e) { show('tradeResult', e.message); } }
async function loadPositions() {
  const data = await api(`/api/exchanges/${selected}/positions`);
  $('positions').innerHTML = data.items.map(x => `<tr><td>${x.symbol}</td><td>${x.direction}</td><td>${x.volume}</td><td>${fmt(x.entry_price)}</td><td>${fmt(x.pnl)}</td><td>${fmt(x.position_id)}</td></tr>`).join('');
}
async function loadSignals() {
  const data = await api('/api/signals/recent');
  $('signals').innerHTML = data.items.map(x => `<tr><td>${x.signal_id || x.id || ''}</td><td>${x.kind || 'twap_created'}</td><td>${x.asset || x.symbol || ''}</td><td>${x.side || ''}</td><td>${fmt(x.price)}</td><td>${fmt(x.amount_usd)}</td><td>${x.source || x.group_name || ''}</td></tr>`).join('');
}
async function syncSignals() {
  try {
    const data = await api('/api/signals/sync', {method:'POST'});
    show('signalStatus', data);
    await loadSignals();
    await loadTradingLogs();
    await loadOpenTrades();
  } catch(e) { show('signalStatus', e.message); }
}
async function signalStatus() { try { show('signalStatus', await api('/api/signals/status')); } catch(e) { show('signalStatus', e.message); } }
async function loadTradingLogs() {
  const data = await api('/api/trading/logs?limit=100');
  $('tradeLogs').innerHTML = data.items.map(x => `<tr><td>${x.time || ''}</td><td><span class="pill ${x.level === 'success' ? 'ok' : (x.level === 'error' ? 'bad' : '')}">${x.level || ''}</span></td><td>${x.action || ''}</td><td>${x.symbol || ''}</td><td>${x.message || ''}</td></tr>`).join('');
}
async function loadOpenTrades() {
  const data = await api('/api/trading/open-trades');
  $('openTrades').innerHTML = data.items.map(x => `<tr><td>${x.trade_key || ''}</td><td>${x.symbol || ''}</td><td>${x.direction || ''}</td><td>${fmtMoney(x.estimated_margin_usdt)}</td><td>${fmtMoney(x.notional_usdt)}</td><td>${x.volume || ''}</td><td>${x.leverage || ''}x${x.auto_leverage_used ? ' ⚡' : ''}</td><td>${x.opened_at || ''}</td><td>${x.open_order_id || ''}</td></tr>`).join('');
}
init();
</script>
</body>
</html>"""
