from __future__ import annotations


def render_page() -> str:
    return """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>TWAPs</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0b111d;
      --panel: #111a2a;
      --panel-soft: #162235;
      --panel-deep: #08101c;
      --border: rgba(148, 163, 184, .18);
      --border-strong: rgba(148, 163, 184, .32);
      --text: #e8eef8;
      --muted: #8fa1bd;
      --accent: #6ee7b7;
      --accent-2: #60a5fa;
      --danger: #fb7185;
      --warn: #fbbf24;
      --ok: #34d399;
      --shadow: 0 20px 60px rgba(0, 0, 0, .28);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(circle at 12% 0%, rgba(96, 165, 250, .18), transparent 34%),
        radial-gradient(circle at 88% 10%, rgba(110, 231, 183, .10), transparent 28%),
        var(--bg);
      color: var(--text);
    }

    main { max-width: 1280px; margin: 0 auto; padding: 22px; }
    h1 { margin: 0; font-size: clamp(28px, 4vw, 52px); line-height: 1; letter-spacing: -.04em; }
    h2 { margin: 0 0 4px; font-size: 20px; letter-spacing: -.02em; }
    h3 { margin: 0; font-size: 15px; }
    code { color: #bfdbfe; background: rgba(96, 165, 250, .12); padding: 2px 6px; border-radius: 7px; }

    .topbar {
      position: sticky;
      top: 0;
      z-index: 20;
      backdrop-filter: blur(16px);
      background: rgba(11, 17, 29, .86);
      border-bottom: 1px solid var(--border);
    }
    .topbar-inner {
      max-width: 1280px;
      margin: 0 auto;
      padding: 14px 22px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 14px;
    }
    .brand { display: flex; align-items: center; gap: 12px; min-width: 0; }
    .brand-mark {
      width: 38px;
      height: 38px;
      border-radius: 13px;
      display: grid;
      place-items: center;
      color: #07111f;
      font-weight: 900;
      background: linear-gradient(135deg, var(--accent), var(--accent-2));
      box-shadow: 0 8px 28px rgba(96, 165, 250, .22);
    }
    .brand-title { font-weight: 900; letter-spacing: .04em; }
    .brand-subtitle { color: var(--muted); font-size: 12px; margin-top: 1px; }

    .hero {
      margin: 22px 0;
      display: grid;
      grid-template-columns: minmax(0, 1fr) 360px;
      gap: 16px;
      align-items: stretch;
    }
    .hero-card {
      min-height: 172px;
      border: 1px solid var(--border);
      border-radius: 28px;
      padding: 28px;
      background: linear-gradient(145deg, rgba(17, 26, 42, .95), rgba(8, 16, 28, .95));
      box-shadow: var(--shadow);
    }
    .hero-card .muted { max-width: 680px; margin-top: 12px; }

    .fallback-warning {
      display: none;
      margin: 0 0 14px;
      padding: 12px 14px;
      border-radius: 16px;
      border: 1px solid rgba(251, 113, 133, .42);
      background: rgba(251, 113, 133, .12);
      color: #fecdd3;
      font-weight: 800;
    }

    .signal-banner {
      height: 100%;
      min-height: 172px;
      display: flex;
      flex-direction: column;
      justify-content: center;
      gap: 8px;
      border: 1px solid var(--border);
      border-radius: 28px;
      padding: 24px;
      background: rgba(17, 26, 42, .92);
      box-shadow: var(--shadow);
    }
    .signal-banner b { display: block; font-size: 19px; letter-spacing: -.02em; }
    .signal-banner.connected { border-color: rgba(52, 211, 153, .38); background: rgba(16, 38, 33, .86); }
    .signal-banner.connecting, .signal-banner.reconnecting { border-color: rgba(251, 191, 36, .42); background: rgba(49, 35, 13, .86); }
    .signal-banner.error { border-color: rgba(251, 113, 133, .42); background: rgba(52, 19, 29, .86); }

    .sections { display: grid; gap: 14px; }
    details.section {
      border: 1px solid var(--border);
      border-radius: 24px;
      background: rgba(17, 26, 42, .88);
      box-shadow: 0 12px 36px rgba(0, 0, 0, .18);
      overflow: hidden;
    }
    details.section[open] { border-color: var(--border-strong); }
    details.section > summary {
      cursor: pointer;
      list-style: none;
      padding: 18px 22px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      user-select: none;
    }
    details.section > summary::-webkit-details-marker { display: none; }
    details.section > summary::after {
      content: "⌄";
      color: var(--muted);
      font-size: 18px;
      transition: transform .18s ease;
    }
    details.section[open] > summary::after { transform: rotate(180deg); }
    .summary-title { display: flex; align-items: center; gap: 12px; min-width: 0; }
    .num {
      width: 32px;
      height: 32px;
      border-radius: 12px;
      display: grid;
      place-items: center;
      color: #07111f;
      background: linear-gradient(135deg, var(--accent), var(--accent-2));
      font-weight: 900;
      flex: 0 0 auto;
    }
    .section-body {
      border-top: 1px solid var(--border);
      padding: 20px 22px 22px;
    }

    .hint {
      margin: 0 0 14px;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.45;
    }
    .muted { color: var(--muted); font-size: 14px; line-height: 1.45; }
    .small { font-size: 12px; }
    .ok { color: var(--ok); }
    .bad { color: var(--danger); }
    .warn { color: var(--warn); }

    .form-grid {
      display: grid;
      grid-template-columns: repeat(12, 1fr);
      gap: 12px;
      align-items: end;
    }
    .field {
      grid-column: span 3;
      min-width: 0;
      border: 1px solid var(--border);
      background: rgba(8, 16, 28, .62);
      border-radius: 16px;
      padding: 12px;
    }
    .field.wide { grid-column: span 6; }
    .field.full { grid-column: 1 / -1; }
    .field.critical {
      grid-column: 1 / -1;
      border-color: rgba(251, 191, 36, .34);
      background: rgba(49, 35, 13, .34);
    }
    label {
      display: block;
      margin: 0 0 7px;
      color: #c7d2fe;
      font-size: 12px;
      font-weight: 800;
      letter-spacing: .04em;
      text-transform: uppercase;
    }
    input, select, button {
      width: 100%;
      border: 1px solid var(--border-strong);
      border-radius: 12px;
      padding: 10px 12px;
      background: #08101c;
      color: var(--text);
      outline: none;
      font: inherit;
    }
    input:focus, select:focus { border-color: rgba(96, 165, 250, .74); box-shadow: 0 0 0 3px rgba(96, 165, 250, .14); }
    input[list]::-webkit-calendar-picker-indicator { display: none !important; }
    button {
      cursor: pointer;
      background: linear-gradient(135deg, #22c55e, #3b82f6);
      border-color: transparent;
      color: #06111f;
      font-weight: 900;
      white-space: nowrap;
    }
    button:hover { filter: brightness(1.06); }
    button:disabled { opacity: .55; cursor: not-allowed; }
    button.secondary { background: #1d293b; border-color: var(--border-strong); color: var(--text); }
    button.danger { background: #7f1d1d; border-color: rgba(251, 113, 133, .42); color: #ffe4e6; }

    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 14px;
    }
    .actions button { width: auto; min-width: 150px; }
    .actions .danger { margin-left: auto; }

    .status {
      margin: 14px 0 0;
      padding: 14px;
      border-radius: 16px;
      background: #07101d;
      border: 1px solid var(--border);
      color: #dbeafe;
      white-space: pre-wrap;
      max-height: 360px;
      overflow: auto;
      font-size: 13px;
      line-height: 1.45;
    }

    .trade-preview {
      margin-top: 14px;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 10px;
    }
    .trade-preview div {
      background: rgba(8, 16, 28, .7);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 12px;
    }
    .trade-preview b { display:block; margin-top: 5px; font-size: 16px; }

    .table-card {
      margin-top: 14px;
      border: 1px solid var(--border);
      border-radius: 18px;
      overflow: hidden;
      background: rgba(8, 16, 28, .55);
    }
    .table-toolbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      padding: 12px 14px;
      border-bottom: 1px solid var(--border);
      background: rgba(17, 26, 42, .72);
    }
    .table-title { font-weight: 900; }
    .rows-control {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 13px;
      white-space: nowrap;
    }
    .rows-control select { width: 92px; padding: 7px 9px; border-radius: 10px; }
    .table-scroll { max-height: 360px; overflow: auto; }
    table { width: 100%; border-collapse: collapse; }
    th, td {
      border-bottom: 1px solid var(--border);
      padding: 10px 12px;
      text-align: left;
      font-size: 13px;
      vertical-align: top;
    }
    th {
      position: sticky;
      top: 0;
      z-index: 2;
      background: #121d2f;
      color: #bfdbfe;
      font-size: 12px;
      letter-spacing: .03em;
      text-transform: uppercase;
    }
    tr:last-child td { border-bottom: none; }

    .pill {
      display: inline-flex;
      align-items: center;
      border: 1px solid var(--border-strong);
      border-radius: 999px;
      padding: 3px 8px;
      font-size: 12px;
      font-weight: 800;
      color: var(--text);
      background: rgba(255, 255, 255, .04);
    }
    .pill.ok { border-color: rgba(52, 211, 153, .46); background: rgba(52, 211, 153, .13); color: #bbf7d0; }
    .pill.bad { border-color: rgba(251, 113, 133, .46); background: rgba(251, 113, 133, .12); color: #fecdd3; }

    .search-row {
      display: grid;
      grid-template-columns: auto minmax(220px, 1fr);
      gap: 12px;
      align-items: end;
      margin-bottom: 14px;
    }

    @media (max-width: 1000px) {
      .hero { grid-template-columns: 1fr; }
      .field { grid-column: span 6; }
      .field.wide { grid-column: 1 / -1; }
    }
    @media (max-width: 680px) {
      main, .topbar-inner { padding-left: 14px; padding-right: 14px; }
      .hero-card, .signal-banner { border-radius: 20px; padding: 20px; }
      .field, .field.wide { grid-column: 1 / -1; }
      .actions button, .actions .danger { width: 100%; margin-left: 0; }
      .search-row { grid-template-columns: 1fr; }
      .table-toolbar { align-items: flex-start; flex-direction: column; }
    }
  </style>
</head>
<body>
<header class="topbar">
  <div class="topbar-inner">
    <div class="brand">
      <div class="brand-mark">TW</div>
      <div>
        <div class="brand-title">TWAPs</div>
        <div class="brand-subtitle">Локальная панель управления</div>
      </div>
    </div>
    <button class="secondary" style="width:auto" onclick="saveSettings()">Сохранить настройки</button>
  </div>
</header>

<main>
  <div id="fallbackWarning" class="fallback-warning">Страховка закрытия сделки по окончанию срока TWAP отключена!</div>

  <section class="hero">
    <div class="hero-card">
      <h1>Панель софта</h1>
      <div class="muted">Минимум текста, важные настройки разнесены по строкам. JSON-ответы оставлены без изменений.</div>
    </div>
    <div id="signalBanner" class="signal-banner">
      <b>Состояние неизвестно</b>
      <span class="muted">Статус ещё не загружен</span>
    </div>
  </section>

  <div class="sections">
    <details class="section" open>
      <summary>
        <span class="summary-title"><span class="num">1</span><span><h3>Аккаунт</h3><span class="muted small">Вход через Telegram-код</span></span></span>
      </summary>
      <div class="section-body">
        <div class="form-grid">
          <div class="field"><label>Логин</label><input id="authLogin" placeholder="login" /></div>
          <div class="field"><label>Пароль</label><input id="authPassword" placeholder="password" type="password" /></div>
          <div class="field"><label>Код</label><input id="authCode" placeholder="6 цифр" /></div>
          <div class="field"><label>Устройство</label><input id="authDeviceName" placeholder="local-client" /></div>
        </div>
        <div class="actions">
          <button onclick="loginAccount()">Войти</button>
          <button class="secondary" onclick="loadAuthStatus()">Статус</button>
          <button class="danger" onclick="logoutAccount()">Выйти</button>
        </div>
        <pre id="authStatus" class="status"></pre>
      </div>
    </details>

    <details class="section" open>
      <summary>
        <span class="summary-title"><span class="num">2</span><span><h3>Биржа</h3><span class="muted small">API-ключи и режим позиций</span></span></span>
      </summary>
      <div class="section-body">
        <div class="form-grid">
          <div class="field"><label>Биржа</label><select id="exchange"></select></div>
          <div class="field"><label>Binance включена</label><select id="binanceEnabled"><option value="true">Да</option><option value="false">Нет</option></select></div>
          <div class="field critical"><label>Режим позиций Binance</label><select id="binanceHedgeMode"><option value="true">Hedge Mode: Long и Short отдельно</option><option value="false">One-way Mode: Long закрывает Short</option></select></div>
          <div class="field wide"><label>Binance API key</label><input id="binanceApiKey" placeholder="API key" type="password" /></div>
          <div class="field wide"><label>Binance Secret key</label><input id="binanceSecretKey" placeholder="Secret key" type="password" /></div>
        </div>
        <div class="actions">
          <button onclick="saveSettings()">Сохранить</button>
          <button class="secondary" onclick="checkStatus()">Проверить</button>
          <button class="secondary" onclick="loadBalance()">Баланс</button>
        </div>
        <pre id="status" class="status"></pre>
      </div>
    </details>

    <details class="section">
      <summary>
        <span class="summary-title"><span class="num">3</span><span><h3>Futures активы</h3><span class="muted small">Поиск и параметры контрактов</span></span></span>
      </summary>
      <div class="section-body">
        <div class="search-row">
          <button class="secondary" onclick="loadAssets()">Загрузить список</button>
          <div class="field" style="padding:0;border:0;background:transparent">
            <label>Поиск</label>
            <input id="assetSearch" placeholder="BTC, HYPE, ETH..." oninput="renderAssets()" />
          </div>
        </div>
        <div class="table-card">
          <div class="table-toolbar">
            <span class="table-title">Активы</span>
            <label class="rows-control">Показывать строк: <select id="rowsAssets" data-table-rows="assets" onchange="saveUiSettingsFromControls(); renderAssets()"></select></label>
          </div>
          <div class="table-scroll">
            <table><thead><tr><th>Символ</th><th>Min vol</th><th>Шаг</th><th>Плечо</th><th>Contract size</th></tr></thead><tbody id="assets"></tbody></table>
          </div>
        </div>
      </div>
    </details>

    <details class="section" open>
      <summary>
        <span class="summary-title"><span class="num">4</span><span><h3>Ручная сделка</h3><span class="muted small">Market open / close</span></span></span>
      </summary>
      <div class="section-body">
        <div class="form-grid">
          <div class="field wide">
            <label>Символ</label>
            <input id="symbol" value="BTCUSDT" list="symbolOptions" oninput="onSymbolInput()" onchange="loadRules()" onblur="loadRules()" />
            <datalist id="symbolOptions"></datalist>
          </div>
          <div class="field"><label>Направление</label><select id="direction"><option value="long">Long</option><option value="short">Short</option></select></div>
          <div class="field critical"><label>Объем, USDT</label><input id="amountUsdt" type="number" step="0.01" min="0.01" value="10" oninput="updateManualPreview()" /></div>
          <div class="field"><label>Округление объема</label><select id="notionalRounding" onchange="updateManualPreview()"><option value="down">В меньшую сторону</option><option value="up">В большую сторону</option></select></div>
          <div class="field"><label>Плечо</label><input id="leverage" type="number" min="1" value="1" /></div>
        </div>
        <div class="actions">
          <button onclick="openOrder()">Открыть market</button>
          <button class="danger" onclick="closeOrder()">Закрыть market</button>
          <button class="secondary" onclick="loadPositions()">Позиции</button>
          <button class="secondary" onclick="setMinManualAmount()">Минимальный объем</button>
        </div>
        <div id="manualPreview" class="trade-preview"></div>
        <pre id="rules" class="status"></pre>
        <pre id="tradeResult" class="status"></pre>
        <div class="table-card">
          <div class="table-toolbar">
            <span class="table-title">Позиции</span>
            <label class="rows-control">Показывать строк: <select id="rowsPositions" data-table-rows="positions" onchange="saveUiSettingsFromControls(); renderPositions()"></select></label>
          </div>
          <div class="table-scroll">
            <table><thead><tr><th>Символ</th><th>Сторона</th><th>Объем</th><th>Entry</th><th>PnL</th><th>Position ID</th></tr></thead><tbody id="positions"></tbody></table>
          </div>
        </div>
      </div>
    </details>

    <details class="section" open>
      <summary>
        <span class="summary-title"><span class="num">5</span><span><h3>Автоторговля</h3><span class="muted small">Фильтры, объемы, страховка</span></span></span>
      </summary>
      <div class="section-body">
        <div class="form-grid">
          <div class="field critical"><label>Автоторговля</label><select id="autoTradingEnabled"><option value="false">Выключена</option><option value="true">Включена</option></select></div>
          <div class="field critical"><label>Страховка закрытия TWAP</label><select id="fallbackCloseEnabled" onchange="updateFallbackWarning()"><option value="false">Выключена</option><option value="true">Включена</option></select></div>
          <div class="field"><label>Задержка страховки, сек</label><input id="fallbackCloseGraceSeconds" type="number" step="1" min="0" value="5" /></div>

          <div class="field critical"><label>Входить минимальным объемом</label><select id="useMinVolume" onchange="applyMinVolumeFlag()"><option value="false">Нет</option><option value="true">Да, плечо 1x</option></select></div>
          <div class="field"><label>Объем сделки, USDT</label><input id="autoOrderUsdt" type="number" step="0.01" min="0.01" value="10" /></div>
          <div class="field"><label>Базовое плечо</label><input id="autoLeverage" type="number" min="1" value="1" /></div>
          <div class="field"><label>Авто-плечо</label><select id="autoLeverageEnabled"><option value="true">Да</option><option value="false">Нет</option></select></div>
          <div class="field"><label>Макс. авто-плечо</label><input id="maxAutoLeverage" type="number" min="1" value="20" /></div>

          <div class="field critical"><label>Локальные фильтры входа</label><select id="localSignalFiltersEnabled"><option value="true">Включены</option><option value="false">Отключены, входить по всем сигналам</option></select></div>
          <div class="field"><label>Мин. TWAP объем, USD</label><input id="filterMinUsd" type="number" step="1000" min="0" value="300000" /></div>
          <div class="field"><label>Макс. длительность, мин</label><input id="filterMaxDuration" type="number" step="1" min="1" value="30" /></div>
          <div class="field"><label>Макс. market volume, USD</label><input id="filterMaxMarketVolume" type="number" step="1000000" min="1" value="100000000" /></div>
          <div class="field"><label>Мин. TWAP share, %</label><input id="filterMinShare" type="number" step="0.01" min="0" value="0.5" /></div>
          <div class="field critical"><label>Игнорировать min USD по доле рынка</label><select id="ignoreMinUsdByShare"><option value="false">Нет</option><option value="true">Да, только min USD</option></select></div>
          <div class="field"><label>Порог TWAP share, %</label><input id="minUsdOverrideShare" type="number" step="0.01" min="0.01" value="1" /></div>
        </div>
        <div class="actions">
          <button onclick="saveSettings()">Сохранить автоторговлю</button>
          <button class="secondary" onclick="loadTradingLogs()">Логи</button>
          <button class="secondary" onclick="loadOpenTrades()">Открытые</button>
          <button class="secondary" onclick="loadFallbackReports()">Страховка</button>
        </div>
        <pre id="autoStatus" class="status"></pre>

        <div class="table-card">
          <div class="table-toolbar">
            <span class="table-title">Логи</span>
            <label class="rows-control">Показывать строк: <select id="rowsTradeLogs" data-table-rows="trade_logs" onchange="saveUiSettingsFromControls(); loadTradingLogs()"></select></label>
          </div>
          <div class="table-scroll">
            <table><thead><tr><th>Время</th><th>Signal ID</th><th>Тип</th><th>Действие</th><th>Символ</th><th>Сообщение</th></tr></thead><tbody id="tradeLogs"></tbody></table>
          </div>
        </div>

        <div class="table-card">
          <div class="table-toolbar">
            <span class="table-title">Открытые авто-сделки</span>
            <label class="rows-control">Показывать строк: <select id="rowsOpenTrades" data-table-rows="open_trades" onchange="saveUiSettingsFromControls(); renderOpenTrades()"></select></label>
          </div>
          <div class="table-scroll">
            <table><thead><tr><th>Trade key</th><th>Символ</th><th>Сторона</th><th>Маржа</th><th>Объем USDT</th><th>Quantity</th><th>Плечо</th><th>TWAP deadline</th><th>Открыт</th><th>Order</th></tr></thead><tbody id="openTrades"></tbody></table>
          </div>
        </div>

        <div class="table-card">
          <div class="table-toolbar">
            <span class="table-title">Отчеты страховки</span>
            <label class="rows-control">Показывать строк: <select id="rowsFallbackReports" data-table-rows="fallback_reports" onchange="saveUiSettingsFromControls(); loadFallbackReports()"></select></label>
          </div>
          <div class="table-scroll">
            <table><thead><tr><th>ID</th><th>Время</th><th>Статус</th><th>Trade key</th><th>Символ</th><th>Сообщение</th></tr></thead><tbody id="fallbackReports"></tbody></table>
          </div>
        </div>
      </div>
    </details>

    <details class="section" open>
      <summary>
        <span class="summary-title"><span class="num">6</span><span><h3>Сигналы</h3><span class="muted small">WebSocket и последние события</span></span></span>
      </summary>
      <div class="section-body">
        <div class="actions" style="margin-top:0">
          <button id="signalCheckButton" class="secondary" onclick="checkSignalConnection()">Проверить соединение</button>
          <button class="secondary" onclick="loadSignals()">Последние локальные</button>
          <button class="secondary" onclick="signalStatus()">Обновить статус</button>
        </div>
        <pre id="signalStatus" class="status"></pre>
        <div class="table-card">
          <div class="table-toolbar">
            <span class="table-title">Последние сигналы</span>
            <label class="rows-control">Показывать строк: <select id="rowsSignals" data-table-rows="signals" onchange="saveUiSettingsFromControls(); loadSignals()"></select></label>
          </div>
          <div class="table-scroll">
            <table><thead><tr><th>ID</th><th>Тип</th><th>Актив</th><th>Сторона</th><th>Цена</th><th>Объем</th><th>Источник</th></tr></thead><tbody id="signals"></tbody></table>
          </div>
        </div>
      </div>
    </details>
  </div>
</main>

<script>
let selected = 'binance';
let assetsCache = [];
let positionsCache = [];
let openTradesCache = [];
let currentRules = null;
let uiSettings = {
  table_rows: {
    assets: 50,
    positions: 25,
    signals: 50,
    trade_logs: 50,
    open_trades: 25,
    fallback_reports: 50
  }
};
let uiSaveTimer = null;

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
const rowOptions = [10, 25, 50, 100, 200, 500];

async function api(url, opts = {}) {
  const res = await fetch(url, {headers: {'content-type': 'application/json'}, ...opts});
  const data = await res.json();
  if (!res.ok || data.success === false) throw new Error(data.message || 'Ошибка запроса');
  return data;
}
function boundedRows(value, fallback) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(500, Math.max(10, Math.floor(parsed)));
}
function normalizeUiSettings(raw) {
  const defaults = uiSettings.table_rows;
  const tableRows = raw?.table_rows || {};
  return {
    table_rows: Object.fromEntries(Object.entries(defaults).map(([key, value]) => [key, boundedRows(tableRows[key], value)]))
  };
}
function rowLimit(key) {
  return boundedRows(uiSettings.table_rows?.[key], 50);
}
function buildRowControls() {
  document.querySelectorAll('select[data-table-rows]').forEach(select => {
    select.innerHTML = rowOptions.map(value => `<option value="${value}">${value}</option>`).join('');
  });
}
function applyRowControls() {
  document.querySelectorAll('select[data-table-rows]').forEach(select => {
    const key = select.dataset.tableRows;
    select.value = String(rowLimit(key));
  });
}
function collectRowControls() {
  const table_rows = {};
  document.querySelectorAll('select[data-table-rows]').forEach(select => {
    table_rows[select.dataset.tableRows] = boundedRows(select.value, rowLimit(select.dataset.tableRows));
  });
  uiSettings = {table_rows: {...uiSettings.table_rows, ...table_rows}};
  return uiSettings;
}
function saveUiSettingsFromControls() {
  collectRowControls();
  clearTimeout(uiSaveTimer);
  uiSaveTimer = setTimeout(async () => {
    try {
      await api('/api/settings', {method:'PUT', body: JSON.stringify({ui: uiSettings})});
    } catch(e) {
      console.warn('Не удалось сохранить настройки интерфейса', e);
    }
  }, 250);
}

async function init() {
  buildRowControls();

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
  uiSettings = normalizeUiSettings(settings.ui || {});
  applyRowControls();

  $('authLogin').value = settings.account?.login || '';
  $('authDeviceName').value = settings.account?.device_name || 'local-client';
  await loadAuthStatus();

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

  const sf = settings.trading?.signal_filters || {};
  $('localSignalFiltersEnabled').value = String(sf.enabled ?? true);
  $('filterMinUsd').value = sf.min_usd ?? 300000;
  $('filterMaxDuration').value = sf.max_duration_minutes ?? 30;
  $('filterMaxMarketVolume').value = sf.max_market_volume_usd ?? 100000000;
  $('filterMinShare').value = sf.min_twap_share_percent ?? 0.5;
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
  collectRowControls();

  const patch = {
    selected_exchange: selected,
    ui: uiSettings,
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
      disable_signal_filters: true,
      signal_filters: {
        enabled: $('localSignalFiltersEnabled').value === 'true',
        min_usd: Number($('filterMinUsd').value || 0),
        max_duration_minutes: Number($('filterMaxDuration').value || 30),
        max_market_volume_usd: Number($('filterMaxMarketVolume').value || 100000000),
        min_twap_share_percent: Number($('filterMinShare').value || 0)
      },
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

async function loadAuthStatus() {
  try {
    const data = await api('/api/auth/status');
    show('authStatus', data);
    return data;
  } catch(e) {
    show('authStatus', e.message);
    return null;
  }
}
async function loginAccount() {
  try {
    const data = await api('/api/auth/login', {
      method:'POST',
      body: JSON.stringify({
        login: $('authLogin').value,
        password: $('authPassword').value,
        code: $('authCode').value,
        device_name: $('authDeviceName').value
      })
    });
    $('authPassword').value = '';
    $('authCode').value = '';
    show('authStatus', data);
    await signalStatus();
  } catch(e) {
    show('authStatus', e.message);
  }
}
async function logoutAccount() {
  try {
    const data = await api('/api/auth/logout', {method:'POST', body: JSON.stringify({})});
    show('authStatus', data);
    await signalStatus();
  } catch(e) {
    show('authStatus', e.message);
  }
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
  const items = assetsCache
    .filter(x => !query || String(x.symbol || '').includes(query) || String(x.base_coin || '').toUpperCase().includes(query))
    .slice(0, rowLimit('assets'));
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
  positionsCache = data.items || [];
  renderPositions();
}
function renderPositions() {
  $('positions').innerHTML = positionsCache.slice(0, rowLimit('positions')).map(x => `<tr><td>${esc(x.symbol)}</td><td>${esc(x.direction)}</td><td>${x.volume}</td><td>${fmt(x.entry_price)}</td><td>${fmt(x.pnl)}</td><td>${fmt(x.position_id)}</td></tr>`).join('');
}

async function loadSignals() {
  const data = await api(`/api/signals/recent?limit=${rowLimit('signals')}`);
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
  const data = await api(`/api/trading/logs?limit=${rowLimit('trade_logs')}`);
  $('tradeLogs').innerHTML = data.items.map(x => `<tr><td>${x.time || ''}</td><td>${x.signal_id || ''}</td><td><span class="pill ${x.level === 'success' ? 'ok' : (x.level === 'error' ? 'bad' : '')}">${esc(x.level || '')}</span></td><td>${esc(x.action || '')}</td><td>${esc(x.symbol || '')}</td><td>${esc(x.message || '')}</td></tr>`).join('');
}
async function loadOpenTrades() {
  const data = await api('/api/trading/open-trades');
  openTradesCache = data.items || [];
  renderOpenTrades();
}
function renderOpenTrades() {
  $('openTrades').innerHTML = openTradesCache.slice(0, rowLimit('open_trades')).map(x => `<tr><td>${esc(x.trade_key || '')}</td><td>${esc(x.symbol || '')}</td><td>${esc(x.direction || '')}</td><td>${fmtMoney(x.estimated_margin_usdt)}</td><td>${fmtMoney(x.notional_usdt)}</td><td>${x.volume || ''}</td><td>${x.leverage || ''}x${x.auto_leverage_used ? ' ⚡' : ''}</td><td>${x.twap_deadline_at || ''}</td><td>${x.opened_at || ''}</td><td>${x.open_order_id || ''}</td></tr>`).join('');
}
async function loadFallbackReports() {
  const data = await api(`/api/trading/fallback-reports?limit=${rowLimit('fallback_reports')}`);
  $('fallbackReports').innerHTML = data.items.map(x => `<tr><td>${x.id || ''}</td><td>${x.triggered_at || x.created_at || ''}</td><td><span class="pill ${x.status === 'success' ? 'ok' : (x.status === 'error' ? 'bad' : '')}">${esc(x.status || '')}</span></td><td>${esc(x.trade_key || '')}</td><td>${esc(x.symbol || '')}</td><td>${esc(x.message || '')}</td></tr>`).join('');
}
init();
</script>
</body>
</html>"""
