from __future__ import annotations

def render_page() -> str:
    return """<!doctype html><html lang="ru"><head>  <meta charset="utf-8" />  <meta name="viewport" content="width=device-width, initial-scale=1" />  <title>TWAP Local Client</title>  <style>    :root { color-scheme: dark; font-family: Arial, sans-serif; }    body { margin: 0; background: #0d1117; color: #e6edf3; }    main { max-width: 1220px; margin: 0 auto; padding: 24px; }    h1 { margin: 0 0 16px; }    details { background: #161b22; border: 1px solid #30363d; border-radius: 12px; margin: 12px 0; padding: 12px 16px; }    summary { cursor: pointer; font-weight: 700; }    label { display: block; font-size: 13px; color: #8b949e; margin: 10px 0 4px; }    input, select, button { border-radius: 8px; border: 1px solid #30363d; padding: 9px 10px; background: #0d1117; color: #e6edf3; }    input[list]::-webkit-calendar-picker-indicator { display: none !important; }    button { cursor: pointer; background: #238636; border-color: #238636; font-weight: 700; }    button:disabled { opacity: .55; cursor: not-allowed; }    button.secondary { background: #21262d; border-color: #30363d; }    button.danger { background: #da3633; border-color: #da3633; }    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; }    .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: end; }    .status { padding: 10px; border-radius: 10px; background: #0d1117; border: 1px solid #30363d; white-space: pre-wrap; max-height: 360px; overflow: auto; }    .trade-preview { margin-top:10px; display:grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap:8px; }    .trade-preview div { background:#0d1117; border:1px solid #30363d; border-radius:10px; padding:10px; }    .trade-preview b { display:block; margin-top:4px; font-size:15px; }    .assets-panel { max-width: 680px; }    .assets-tools { max-width: 540px; margin-top: 10px; }    .assets-tools input { width: 100%; box-sizing: border-box; }    .assets-scroll { max-width: 680px; max-height: 320px; overflow: auto; border: 1px solid #30363d; border-radius: 10px; margin-top: 10px; }    .assets-scroll table { margin-top: 0; }    .assets-scroll th { position: sticky; top: 0; background: #161b22; z-index: 1; }    table { width: 100%; border-collapse: collapse; margin-top: 10px; }    th, td { border-bottom: 1px solid #30363d; padding: 8px; text-align: left; font-size: 13px; vertical-align: top; }    .ok { color: #3fb950; }    .bad { color: #f85149; }    .warn { color: #d29922; }
    .muted { color: #8b949e; }
    .pill { display: inline-block; border: 1px solid #30363d; border-radius: 999px; padding: 2px 8px; font-size: 12px; }
    .pill.ok { border-color: #238636; background: rgba(35,134,54,.14); }
    .pill.bad { border-color: #da3633; background: rgba(218,54,51,.12); }
    .signal-banner { margin: 10px 0; padding: 12px; border: 1px solid #30363d; border-radius: 10px; background: #0d1117; }
    .signal-banner b { display:block; font-size:16px; margin-bottom:4px; }
    .signal-banner.connected { border-color:#238636; background: rgba(35,134,54,.12); }
    .signal-banner.connecting, .signal-banner.reconnecting { border-color:#d29922; background: rgba(210,153,34,.10); }
    .signal-banner.error { border-color:#da3633; background: rgba(218,54,51,.10); }
    .fallback-warning { display:none; position:sticky; top:0; z-index:10; margin:0 0 12px; padding:12px 14px; border:1px solid #f85149; border-radius:10px; background:rgba(248,81,73,.18); color:#ffdcd7; font-weight:700; }
    code { background:#0d1117; border:1px solid #30363d; border-radius:6px; padding:1px 4px; }
  </style>
</head>
<body>
<main>
  <h1>TWAP Local Client</h1>
  <div id="fallbackWarning" class="fallback-warning">страховка закрытия сделки по окончанию срока TWAP - отключена!</div>
  <p class="muted">Биржевые токены, сигналы и сделки сохраняются локально в <code>local_data/</code>.</p>

  <details open>
    <summary>1. Биржа и подключение</summary>
    <div class="grid">
      <div><label>Биржа</label><select id="exchange"></select></div>
      <div><label>Binance API key</label><input id="binanceApiKey" placeholder="API key" type="password" /></div>
      <div><label>Binance Secret key</label><input id="binanceSecretKey" placeholder="Secret key" type="password" /></div>
      <div><label>Включить Binance</label><select id="binanceEnabled"><option value="true">Да</option><option value="false">Нет</option></select></div>
      <div><label>Binance режим позиций</label><select id="binanceHedgeMode"><option value="true">Hedge Mode: Long и Short отдельно</option><option value="false">One-way Mode: Long закрывает Short</option></select></div>
    </div>
    <p class="muted">По умолчанию выбран Hedge Mode. Перед открытием сделки софт синхронизирует режим на Binance; переключение невозможно, если на аккаунте есть открытые позиции или ордера.</p>
    <div class="row" style="margin-top:10px">
      <button onclick="saveSettings()">Сохранить настройки</button>
      <button class="secondary" onclick="checkStatus()">Проверить подключение</button>
      <button class="secondary" onclick="loadBalance()">Баланс</button>
    </div>
    <pre id="status" class="status"></pre>
  </details>

  <details>
    <summary>2. Futures активы</summary>
    <div class="assets-panel">
      <div class="row assets-tools">
        <button class="secondary" onclick="loadAssets()">Загрузить список</button>
        <div style="flex:1; min-width:220px">
          <label>Поиск</label>
          <input id="assetSearch" placeholder="BTC, HYPE, ETH..." oninput="renderAssets()" />
        </div>
      </div>
      <div class="assets-scroll">
        <table><thead><tr><th>Символ</th><th>Min vol</th><th>Шаг</th><th>Плечо</th><th>Contract size</th></tr></thead><tbody id="assets"></tbody></table>
      </div>
    </div>
  </details>

  <details open>
    <summary>3. Ручная сделка</summary>
    <div class="grid">
      <div>
        <label>Символ</label>
        <input id="symbol" value="BTCUSDT" list="symbolOptions" oninput="onSymbolInput()" onchange="loadRules()" onblur="loadRules()" />
        <datalist id="symbolOptions"></datalist>
      </div>
      <div><label>Направление</label><select id="direction"><option value="long">Long</option><option value="short">Short</option></select></div>
      <div><label>Объем, USDT</label><input id="amountUsdt" type="number" step="0.01" min="0.01" value="10" oninput="updateManualPreview()" /></div>
      <div><label>Округление объема</label><select id="notionalRounding" onchange="updateManualPreview()"><option value="down">В меньшую сторону</option><option value="up">В большую сторону</option></select></div>
      <div><label>Плечо</label><input id="leverage" type="number" min="1" value="1" /></div>
    </div>
    <div class="row" style="margin-top:10px">
      <button onclick="openOrder()">Открыть market</button>
      <button class="danger" onclick="closeOrder()">Закрыть market</button>
      <button class="secondary" onclick="loadPositions()">Позиции</button>
      <button class="secondary" onclick="setMinManualAmount()">Минимальный объем</button>
    </div>
    <div id="manualPreview" class="trade-preview"></div>
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
      Закрытие выполняется по связанному <code>twap_result</code>. Маржа isolated задаётся через Binance marginType=ISOLATED.
      Объем сделки задаётся в USDT как notional. Если свободной маржи не хватает, клиент подберёт минимальное плечо, но не выше лимита.
      Страховка закрытия проверяет открытые авто-сделки локально и закрывает их после окончания TWAP, если закрывающий сигнал не пришёл.
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
      <div><label>Страховка закрытия TWAP</label><select id="fallbackCloseEnabled" onchange="updateFallbackWarning()"><option value="false">Выключена</option><option value="true">Включена</option></select></div>
      <div><label>Задержка страховки после TWAP, сек</label><input id="fallbackCloseGraceSeconds" type="number" step="1" min="0" value="5" /></div>
    </div>
    <div class="row" style="margin-top:10px">
      <button onclick="saveSettings()">Сохранить автоторговлю</button>
      <button class="secondary" onclick="loadTradingLogs()">Обновить логи</button>
      <button class="secondary" onclick="loadOpenTrades()">Открытые авто-сделки</button>
      <button class="secondary" onclick="loadFallbackReports()">Отчеты страховки</button>
    </div>
    <pre id="autoStatus" class="status"></pre>
    <table><thead><tr><th>Время</th><th>Тип</th><th>Действие</th><th>Символ</th><th>Сообщение</th></tr></thead><tbody id="tradeLogs"></tbody></table>
    <table><thead><tr><th>Trade key</th><th>Символ</th><th>Сторона</th><th>Маржа</th><th>Объем USDT</th><th>Quantity</th><th>Плечо</th><th>TWAP deadline</th><th>Открыт</th><th>Order</th></tr></thead><tbody id="openTrades"></tbody></table>
    <table><thead><tr><th>ID</th><th>Время</th><th>Статус</th><th>Trade key</th><th>Символ</th><th>Сообщение</th></tr></thead><tbody id="fallbackReports"></tbody></table>
  </details>

  <details open>
    <summary>5. Сервер сигналов</summary>
    <p class="muted">
      Сигналы слушаются всегда через WebSocket. Адреса берутся из <code>LOCAL_SIGNAL_WS_URL</code> и <code>LOCAL_SIGNAL_HTTP_URL</code> в <code>.env</code>, вручную в интерфейсе не вводятся.
      Защитный ключ тоже берётся только из <code>LOCAL_SIGNAL_ACCESS_KEY</code> / <code>SIGNAL_SERVER_ACCESS_KEY</code> и в UI не показывается.
    </p>
    <div id="signalBanner" class="signal-banner">
      <b>Состояние неизвестно</b>
      <span class="muted">Статус ещё не загружен</span>
    </div>
    <div class="row" style="margin-top:10px">
      <button id="signalCheckButton" class="secondary" onclick="checkSignalConnection()">Проверить соединение</button>
      <button class="secondary" onclick="loadSignals()">Последние локальные</button>
      <button class="secondary" onclick="signalStatus()">Обновить статус</button>
    </div>
    <pre id="signalStatus" class="status"></pre>
    <table><thead><tr><th>ID</th><th>Тип</th><th>Актив</th><th>Сторона</th><th>Цена</th><th>Объем</th><th>Источник</th></tr></thead><tbody id="signals"></tbody></table>
  </details>
</main>
<script>
let selected = 'binance';
let assetsCache = [];
let currentRules = null;
const $ = id => document.getElementById(id);
const show = (id, data) => $(id).textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
const fmt = value => value === null || value === undefined ? '' : value;
const fmtMoney = value => value === null || value === undefined || value === '' ? '' : `$${Number(value).toFixed(2)}`;
const esc = value => String(value ?? '').replace(/[&<>"']/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[s]));
const amountInput = value => {
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0) return '';
  const fixed = number < 1 ? number.toFixed(6) : number.toFixed(2);
  return fixed.replace(/0+$/, '').replace(/\\.$/, '');
};
async function api(url, opts = {}) {
  const res = await fetch(url, {headers: {'content-type': 'application/json'}, ...opts});
  const data = await res.json();
  if (!res.ok || data.success === false) throw new Error(data.message || 'Ошибка запроса');
  return data;
}
async function init() {
  const exchanges = await api('/api/exchanges');
  selected = exchanges.selected || 'binance';
  $('exchange').innerHTML = exchanges.items.map(e => `<option value="${esc(e.name)}">${esc(e.title)}</option>`).join('');
  $('exchange').value = selected;
  $('exchange').onchange = async () => {
    selected = $('exchange').value;
    assetsCache = [];
    await api('/api/exchanges/select', {method:'POST', body: JSON.stringify({name:selected})});
    await loadAssets(false);
  };
  const settings = await api('/api/settings');
  $('binanceEnabled').value = String(settings.exchanges?.binance?.enabled || false);
  $('binanceHedgeMode').value = String(settings.exchanges?.binance?.hedge_mode_enabled ?? true);
  $('amountUsdt').value = settings.trading?.default_volume || 10;
  $('leverage').value = settings.trading?.default_leverage || 1;
  $('direction').value = settings.trading?.default_direction || 'long';
  $('notionalRounding').value = 'down';
  $('autoTradingEnabled').value = String(settings.trading?.auto_trading_enabled || false);
  $('useMinVolume').value = String(settings.trading?.use_min_volume || false);
  $('autoOrderUsdt').value = settings.trading?.auto_order_usdt || settings.trading?.auto_margin_usdt || 10;
  $('autoLeverage').value = settings.trading?.default_leverage || 1;
  $('autoLeverageEnabled').value = String(settings.trading?.auto_leverage_enabled ?? true);
  $('maxAutoLeverage').value = settings.trading?.max_auto_leverage || 20;
  $('disableSignalFilters').value = String(settings.trading?.disable_signal_filters || false);
  $('ignoreMinUsdByShare').value = String(settings.trading?.ignore_min_usd_by_market_share || false);
  $('minUsdOverrideShare').value = settings.trading?.min_usd_override_twap_share_percent || 1;
  $('fallbackCloseEnabled').value = String(settings.trading?.fallback_close_enabled || false);
  $('fallbackCloseGraceSeconds').value = settings.trading?.fallback_close_grace_seconds ?? 5;
  updateFallbackWarning();
  applyMinVolumeFlag();
  await checkStatus();
  try { await loadAssets(false); await loadRules(); } catch(e) { show('rules', e.message); }
  await signalStatus();
  await loadSignals();
  await loadTradingLogs();
  await loadOpenTrades();
  await loadFallbackReports();
  setInterval(signalStatus, 5000);
  setInterval(loadSignals, 5000);
  setInterval(loadTradingLogs, 10000);
  setInterval(loadOpenTrades, 10000);
  setInterval(loadFallbackReports, 10000);
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
    exchanges: { binance: { enabled: $('binanceEnabled').value === 'true', hedge_mode_enabled: $('binanceHedgeMode').value === 'true' } },
    trading: {
      default_volume: Number($('amountUsdt').value || 10),
      default_leverage: $('useMinVolume').value === 'true' ? 1 : Number($('autoLeverage').value || $('leverage').value),
      default_direction: $('direction').value,
      auto_trading_enabled: $('autoTradingEnabled').value === 'true',
      use_min_volume: $('useMinVolume').value === 'true',
      auto_order_usdt: Number($('autoOrderUsdt').value || 10),
      auto_leverage_enabled: $('useMinVolume').value === 'true' ? false : $('autoLeverageEnabled').value === 'true',
      max_auto_leverage: $('useMinVolume').value === 'true' ? 1 : Number($('maxAutoLeverage').value || 20),
      disable_signal_filters: $('disableSignalFilters').value === 'true',
      ignore_min_usd_by_market_share: $('ignoreMinUsdByShare').value === 'true',
      min_usd_override_twap_share_percent: Number($('minUsdOverrideShare').value || 1),
      fallback_close_enabled: $('fallbackCloseEnabled').value === 'true',
      fallback_close_grace_seconds: Number($('fallbackCloseGraceSeconds').value || 5)
    }
  };
  if ($('binanceApiKey').value) patch.exchanges.binance.api_key = $('binanceApiKey').value;
  if ($('binanceSecretKey').value) patch.exchanges.binance.secret_key = $('binanceSecretKey').value;
  const saved = await api('/api/settings', {method:'PUT', body: JSON.stringify(patch)});
  show('status', saved);
  show('autoStatus', saved.trading);
  updateFallbackWarning();
  await signalStatus();
}
function updateFallbackWarning() {
  const banner = $('fallbackWarning');
  if (!banner) return;
  const enabled = $('fallbackCloseEnabled')?.value === 'true';
  banner.style.display = enabled ? 'none' : 'block';
}
async function checkStatus() { try { show('status', await api(`/api/exchanges/${selected}/status`)); } catch(e) { show('status', e.message); } }
async function loadBalance() { try { show('status', await api(`/api/exchanges/${selected}/balance`)); } catch(e) { show('status', e.message); } }
async function loadAssets(renderStatus = true) {
  const data = await api(`/api/exchanges/${selected}/futures/assets`);
  assetsCache = data.items || [];
  renderAssets();
  renderSymbolOptions($('symbol').value);
  if (renderStatus) show('rules', `Загружено активов: ${assetsCache.length}`);
}
function renderAssets() {
  const query = ($('assetSearch')?.value || '').trim().toUpperCase();
  const items = assetsCache.filter(x => !query || String(x.symbol || '').includes(query) || String(x.base_coin || '').toUpperCase().includes(query)).slice(0, 200);
  $('assets').innerHTML = items.map(x => `<tr><td><button class="secondary" onclick="pickSymbol('${esc(x.symbol)}')">${esc(x.symbol)}</button></td><td>${fmt(x.min_vol)}</td><td>${fmt(x.vol_unit)}</td><td>${fmt(x.min_leverage)}-${fmt(x.max_leverage)}</td><td>${fmt(x.contract_size)}</td></tr>`).join('');
}
async function ensureAssetsLoaded() {
  if (!assetsCache.length) await loadAssets(false);
}
async function onSymbolInput() {
  await ensureAssetsLoaded();
  renderSymbolOptions($('symbol').value);
}
function renderSymbolOptions(value = '') {
  const query = String(value || '').trim().toUpperCase();
  const items = assetsCache
    .filter(x => !query || String(x.symbol || '').includes(query) || String(x.base_coin || '').toUpperCase().includes(query))
    .slice(0, 30);
  $('symbolOptions').innerHTML = items.map(x => `<option value="${esc(x.symbol)}">${esc(x.display_name || x.symbol)}</option>`).join('');
}
async function loadRules(symbol = null) {
  const current = String(symbol || $('symbol').value || '').trim().toUpperCase();
  if (!current) return null;
  $('symbol').value = current;
  try {
    const data = await api(`/api/exchanges/${selected}/futures/rules?symbol=${encodeURIComponent(current)}`);
    currentRules = data;
    show('rules', {
      symbol: data.symbol,
      min_order_usdt: data.min_notional_usdt,
      min_volume_contracts: data.min_volume,
      volume_step_contracts: data.volume_step,
      max_volume_contracts: data.max_volume,
      leverage: `${data.min_leverage}x-${data.max_leverage}x`,
      price: data.price,
      contract_size: data.contract_size
    });
    updateManualPreview();
    return data;
  } catch(e) {
    currentRules = null;
    updateManualPreview();
    show('rules', e.message);
    return null;
  }
}
async function setMinManualAmount() {
  const rules = await loadRules();
  if (rules?.min_notional_usdt) $('amountUsdt').value = amountInput(rules.min_notional_usdt);
  updateManualPreview();
}
async function pickSymbol(symbol) {
  $('symbol').value = symbol;
  renderSymbolOptions(symbol);
  await loadRules(symbol);
}
function manualVolumePreview() {
  const amount = Number($('amountUsdt').value || 0);
  if (!currentRules || !Number.isFinite(amount) || amount <= 0) return null;
  const price = Number(currentRules.price || 0);
  const contractSize = Number(currentRules.contract_size || 1) || 1;
  const step = Number(currentRules.volume_step || 1) || 1;
  const minVolume = Number(currentRules.min_volume || 0) || 0;
  if (!Number.isFinite(price) || price <= 0 || !Number.isFinite(step) || step <= 0) return null;

  const oneContractUsdt = price * contractSize;
  const rawVolume = amount / oneContractUsdt;
  const units = rawVolume / step;
  const roundUp = $('notionalRounding').value === 'up';
  let contracts = (roundUp ? Math.ceil(units) : Math.floor(units)) * step;
  if (minVolume > 0 && contracts < minVolume) contracts = minVolume;
  const maxVolume = Number(currentRules.max_volume || 0) || 0;
  const overMax = maxVolume > 0 && contracts > maxVolume;
  const openedUsdt = contracts * oneContractUsdt;
  return {amount, oneContractUsdt, rawVolume, contracts, openedUsdt, diff: openedUsdt - amount, roundUp, overMax, maxVolume};
}
function updateManualPreview() {
  const box = $('manualPreview');
  if (!box) return;
  const preview = manualVolumePreview();
  if (!preview) {
    box.innerHTML = `<div><span class="muted">Предупреждение по объему</span><b>Выбери символ и загрузи правила</b></div>`;
    return;
  }
  const diffClass = preview.diff > 0 ? 'warn' : (preview.diff < 0 ? 'bad' : 'ok');
  const direction = preview.roundUp ? 'в большую сторону' : 'в меньшую сторону';
  const cards = [
    `<div><span class="muted">Размер 1 контракта</span><b>${fmtMoney(preview.oneContractUsdt)}</b></div>`,
    `<div><span class="muted">Биржа получит объем</span><b>${fmt(preview.contracts)} quantity</b></div>`,
    `<div><span class="muted">Сделка будет открыта в объеме</span><b>${fmtMoney(preview.openedUsdt)}</b></div>`,
    `<div><span class="muted">Отклонение от ввода</span><b class="${diffClass}">${preview.diff >= 0 ? '+' : '-'}${fmtMoney(Math.abs(preview.diff))}</b><span class="muted">Округление ${direction}</span></div>`
  ];
  if (preview.overMax) cards.push(`<div><span class="muted">Предупреждение</span><b class="bad">Больше максимума ${fmt(preview.maxVolume)} quantity</b></div>`);
  box.innerHTML = cards.join('');
}
function orderPayload() {
  return {
    symbol: $('symbol').value,
    direction: $('direction').value,
    amount_usdt: Number($('amountUsdt').value),
    notional_rounding: $('notionalRounding').value,
    leverage: Number($('leverage').value),
    open_type: 1
  };
}
async function openOrder() { try { show('tradeResult', await api(`/api/exchanges/${selected}/orders/open`, {method:'POST', body: JSON.stringify(orderPayload())})); await loadPositions(); } catch(e) { show('tradeResult', e.message); } }
async function closeOrder() { try { show('tradeResult', await api(`/api/exchanges/${selected}/orders/close`, {method:'POST', body: JSON.stringify(orderPayload())})); await loadPositions(); } catch(e) { show('tradeResult', e.message); } }
async function loadPositions() {
  const data = await api(`/api/exchanges/${selected}/positions`);
  $('positions').innerHTML = data.items.map(x => `<tr><td>${esc(x.symbol)}</td><td>${esc(x.direction)}</td><td>${x.volume}</td><td>${fmt(x.entry_price)}</td><td>${fmt(x.pnl)}</td><td>${fmt(x.position_id)}</td></tr>`).join('');
}
async function loadSignals() {
  const data = await api('/api/signals/recent');
  $('signals').innerHTML = data.items.map(x => `<tr><td>${x.signal_id || x.id || ''}</td><td>${esc(x.kind || 'twap_created')}</td><td>${esc(x.asset || x.symbol || '')}</td><td>${esc(x.side || '')}</td><td>${fmt(x.price)}</td><td>${fmt(x.amount_usd)}</td><td>${esc(x.source || x.group_name || '')}</td></tr>`).join('');
}
function renderSignalState(data) {
  const state = data?.state || 'error';
  const title = state === 'connected' ? 'Подключено: сигналы слушаются' : state === 'connecting' ? 'Подключение к серверу сигналов' : state === 'reconnecting' ? 'Переподключение к серверу сигналов' : 'Нет соединения с сервером сигналов';
  const details = data?.message || data?.health_message || '';
  $('signalBanner').className = `signal-banner ${esc(state)}`;
  $('signalBanner').innerHTML = `<b>${esc(title)}</b><span class="muted">${esc(details)}</span>`;
}
async function signalStatus() {
  try {
    const data = await api('/api/signals/status');
    renderSignalState(data);
    show('signalStatus', data);
  } catch(e) {
    renderSignalState({state:'error', message:e.message});
    show('signalStatus', e.message);
  }
}
async function checkSignalConnection() {
  const button = $('signalCheckButton');
  if (button?.disabled) return;
  if (button) {
    button.disabled = true;
    button.textContent = 'Проверяем...';
  }
  try {
    const data = await api('/api/signals/check', {method:'POST'});
    renderSignalState(data.health_ok ? {...data, state: data.state || 'connected'} : {...data, state:'error'});
    show('signalStatus', data);
  } catch(e) {
    renderSignalState({state:'error', message:e.message});
    show('signalStatus', e.message);
  } finally {
    setTimeout(() => {
      if (button) {
        button.disabled = false;
        button.textContent = 'Проверить соединение';
      }
    }, 5000);
  }
}
async function loadTradingLogs() {
  const data = await api('/api/trading/logs?limit=100');
  $('tradeLogs').innerHTML = data.items.map(x => `<tr><td>${x.time || ''}</td><td><span class="pill ${x.level === 'success' ? 'ok' : (x.level === 'error' ? 'bad' : '')}">${esc(x.level || '')}</span></td><td>${esc(x.action || '')}</td><td>${esc(x.symbol || '')}</td><td>${esc(x.message || '')}</td></tr>`).join('');
}
async function loadOpenTrades() {
  const data = await api('/api/trading/open-trades');
  $('openTrades').innerHTML = data.items.map(x => `<tr><td>${esc(x.trade_key || '')}</td><td>${esc(x.symbol || '')}</td><td>${esc(x.direction || '')}</td><td>${fmtMoney(x.estimated_margin_usdt)}</td><td>${fmtMoney(x.notional_usdt)}</td><td>${x.volume || ''}</td><td>${x.leverage || ''}x${x.auto_leverage_used ? ' ⚡' : ''}</td><td>${x.twap_deadline_at || ''}</td><td>${x.opened_at || ''}</td><td>${x.open_order_id || ''}</td></tr>`).join('');
}
async function loadFallbackReports() {
  const data = await api('/api/trading/fallback-reports?limit=100');
  $('fallbackReports').innerHTML = data.items.map(x => `<tr><td>${x.id || ''}</td><td>${x.triggered_at || x.created_at || ''}</td><td><span class="pill ${x.status === 'success' ? 'ok' : (x.status === 'error' ? 'bad' : '')}">${esc(x.status || '')}</span></td><td>${esc(x.trade_key || '')}</td><td>${esc(x.symbol || '')}</td><td>${esc(x.message || '')}</td></tr>`).join('');
}
init();
</script>
</body>
</html>"""

