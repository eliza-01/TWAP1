from __future__ import annotations

import os

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter(tags=["site"])


def _bot_username() -> str:
    return (os.getenv("TELEGRAM_BOT_USERNAME") or "stage_twap_parser_bot").strip().lstrip("@")


@router.get("/", response_class=HTMLResponse)
async def index() -> str:
    return _layout(
        "TWAP",
        """
        <section class="hero">
          <h1>TWAP Signal Client</h1>
          <p>Личный кабинет, активация доступа и скачивание локального клиента. Сделки открывает только локальный exe-клиент на компьютере пользователя.</p>
          <div class="row">
            <a class="button" href="/register">Регистрация</a>
            <a class="button secondary" href="/login">Вход в ЛК</a>
            <a class="button secondary" href="/admin">Admin</a>
          </div>
        </section>
        <section class="card">
          <h2>Как это работает</h2>
          <ol>
            <li>Регистрируетесь на сайте и подтверждаете Telegram кодом из бота.</li>
            <li>Активируете ключ времени работы.</li>
            <li>Запускаете TWAP Desktop Client.exe, входите логином/паролем и кодом из Telegram.</li>
            <li>Биржевые API-ключи и фильтры сделок остаются локально в клиенте.</li>
          </ol>
        </section>
        """,
    )


@router.get("/register", response_class=HTMLResponse)
async def register_page() -> str:
    bot = _bot_username()
    return _layout(
        "Регистрация",
        f"""
        <section class="card">
          <h1>Регистрация</h1>
          <p class="muted">Сначала получите одноразовый код в Telegram-боте, затем заполните форму.</p>
          <p><a class="button" target="_blank" rel="noopener" href="https://t.me/{bot}?start=register">Получить код в @{bot}</a></p>
          <label>Логин</label><input id="login" autocomplete="username" />
          <label>Пароль</label><input id="password" type="password" autocomplete="new-password" />
          <label>Код из Telegram-бота</label><input id="code" inputmode="numeric" />
          <button onclick="register()">Создать аккаунт</button>
          <pre id="out"></pre>
          <p class="muted">Уже есть аккаунт? <a href="/login">Войти</a></p>
        </section>
        <script>
        async function register() {{
          const out = document.getElementById('out');
          out.textContent = 'Отправка...';
          try {{
            const res = await fetch('/api/auth/register', {{method:'POST', headers:{{'content-type':'application/json'}}, body: JSON.stringify({{
              login: document.getElementById('login').value,
              password: document.getElementById('password').value,
              code: document.getElementById('code').value
            }})}});
            const data = await res.json();
            if (!res.ok || data.success === false) throw new Error(data.detail || data.message || 'Ошибка регистрации');
            out.textContent = 'Аккаунт создан. Теперь можно войти в ЛК.';
            setTimeout(() => location.href='/login', 1200);
          }} catch(e) {{ out.textContent = e.message; }}
        }}
        </script>
        """,
    )


@router.get("/login", response_class=HTMLResponse)
async def login_page() -> str:
    bot = _bot_username()
    return _layout(
        "Вход",
        f"""
        <section class="card">
          <h1>Вход в личный кабинет</h1>
          <p class="muted">Для каждого входа нужен свежий код Telegram-бота.</p>
          <p><a class="button" target="_blank" rel="noopener" href="https://t.me/{bot}?start=login">Получить код входа в @{bot}</a></p>
          <label>Логин</label><input id="login" autocomplete="username" />
          <label>Пароль</label><input id="password" type="password" autocomplete="current-password" />
          <label>Код из Telegram-бота</label><input id="code" inputmode="numeric" />
          <button onclick="login()">Войти</button>
          <pre id="out"></pre>
          <p class="muted">Нет аккаунта? <a href="/register">Регистрация</a></p>
        </section>
        <script>
        async function login() {{
          const out = document.getElementById('out');
          out.textContent = 'Вход...';
          try {{
            const res = await fetch('/api/auth/login', {{method:'POST', headers:{{'content-type':'application/json'}}, body: JSON.stringify({{
              login: document.getElementById('login').value,
              password: document.getElementById('password').value,
              code: document.getElementById('code').value,
              device_id: 'web-cabinet',
              device_name: 'web-cabinet'
            }})}});
            const data = await res.json();
            if (!res.ok || data.success === false) throw new Error(data.detail || data.message || 'Ошибка входа');
            localStorage.setItem('twap_session_token', data.token);
            location.href = '/cabinet';
          }} catch(e) {{ out.textContent = e.message; }}
        }}
        </script>
        """,
    )


@router.get("/cabinet", response_class=HTMLResponse)
async def cabinet_page() -> str:
    bot = _bot_username()
    return _layout(
        "Личный кабинет",
        f"""
        <section class="card">
          <h1>Личный кабинет</h1>
          <div id="user" class="status">Загрузка...</div>
          <div class="row" style="margin-top:12px">
            <button class="secondary" onclick="loadMe()">Обновить</button>
            <button class="danger" onclick="logout()">Выйти</button>
          </div>
        </section>
        <section class="card">
          <h2>Активация времени работы</h2>
          <p class="muted">Ключ можно активировать здесь или в Telegram-боте командой <code>/activate TWAP-...</code>.</p>
          <label>Ключ активации</label><input id="activationKey" placeholder="TWAP-..." />
          <button onclick="activate()">Активировать</button>
          <pre id="activationOut"></pre>
        </section>
        <section class="card">
          <h2>Локальный клиент</h2>
          <p>Торговый интерфейс больше не публикуется по адресу сайта. Сделки открывает отдельный exe-клиент на компьютере/VPS пользователя.</p>
          <p class="muted">Для входа в exe используйте логин, пароль и свежий код через <a target="_blank" href="https://t.me/{bot}?start=login">@{bot}</a>.</p>
        </section>
        <script>
        const token = localStorage.getItem('twap_session_token') || '';
        if (!token) location.href = '/login';
        async function api(url, opts={{}}) {{
          const res = await fetch(url, {{...opts, headers: {{'content-type':'application/json', 'authorization':'Bearer '+token, ...(opts.headers||{{}})}} }});
          const data = await res.json();
          if (!res.ok || data.success === false) throw new Error(data.detail || data.message || res.statusText);
          return data;
        }}
        async function loadMe() {{
          try {{
            const data = await api('/api/auth/me');
            const u = data.user || {{}};
            document.getElementById('user').innerHTML = `Логин: <b>${{esc(u.login)}}</b><br>Доступ активен: <b>${{u.has_active_access ? 'да' : 'нет'}}</b><br>Доступ до: <b>${{esc(u.access_until || 'нет')}}</b>`;
          }} catch(e) {{ document.getElementById('user').textContent = e.message; }}
        }}
        async function activate() {{
          const out = document.getElementById('activationOut'); out.textContent = 'Активация...';
          try {{
            const data = await api('/api/auth/activate', {{method:'POST', body: JSON.stringify({{key: document.getElementById('activationKey').value}})}});
            out.textContent = 'Ключ активирован. Доступ до: ' + (data.user?.access_until || 'нет');
            await loadMe();
          }} catch(e) {{ out.textContent = e.message; }}
        }}
        async function logout() {{ try {{ await api('/api/auth/logout', {{method:'POST'}}); }} catch(e) {{}} localStorage.removeItem('twap_session_token'); location.href='/login'; }}
        function esc(v) {{ return String(v ?? '').replace(/[&<>"']/g, s => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}}[s])); }}
        loadMe();
        </script>
        """,
    )


@router.get("/admin", response_class=HTMLResponse)
async def admin_page() -> str:
    return _layout(
        "Admin",
        """
        <section class="card">
          <h1>Admin</h1>
          <p class="muted">Stub-авторизация: введите SIGNAL_SERVER_ADMIN_KEY. Ключ хранится только в localStorage браузера.</p>
          <label>Admin key</label><input id="adminKey" type="password" />
          <label>Дней доступа</label><input id="days" type="number" min="1" value="30" />
          <label>Срок действия самого ключа, дней (необязательно)</label><input id="expiresDays" type="number" min="1" placeholder="пусто = без срока" />
          <label>Заметка</label><input id="note" placeholder="кому / за что" />
          <button onclick="createKey()">Выпустить ключ</button>
          <pre id="out"></pre>
        </section>
        <script>
        document.getElementById('adminKey').value = localStorage.getItem('twap_admin_key') || '';
        async function createKey() {
          const key = document.getElementById('adminKey').value;
          localStorage.setItem('twap_admin_key', key);
          const payload = {days: Number(document.getElementById('days').value || 0), note: document.getElementById('note').value};
          const exp = document.getElementById('expiresDays').value;
          if (exp) payload.expires_days = Number(exp);
          const out = document.getElementById('out'); out.textContent = 'Создание...';
          try {
            const res = await fetch('/api/auth/activation-keys', {method:'POST', headers:{'content-type':'application/json','x-admin-key':key}, body: JSON.stringify(payload)});
            const data = await res.json();
            if (!res.ok || data.success === false) throw new Error(data.detail || data.message || 'Ошибка');
            out.textContent = JSON.stringify(data.activation_key, null, 2);
          } catch(e) { out.textContent = e.message; }
        }
        </script>
        """,
    )


@router.get("/local", include_in_schema=False)
async def no_public_local() -> RedirectResponse:
    return RedirectResponse("/cabinet", status_code=302)


def _layout(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>
    :root {{ color-scheme: dark; font-family: Arial, sans-serif; }}
    body {{ margin:0; background:#0d1117; color:#e6edf3; }}
    header {{ border-bottom:1px solid #30363d; background:#161b22; }}
    nav {{ max-width:980px; margin:0 auto; padding:14px 20px; display:flex; gap:14px; align-items:center; }}
    nav a {{ color:#e6edf3; text-decoration:none; }}
    nav a.brand {{ font-weight:800; margin-right:auto; }}
    main {{ max-width:980px; margin:0 auto; padding:26px 20px; }}
    .hero, .card {{ background:#161b22; border:1px solid #30363d; border-radius:16px; padding:22px; margin:14px 0; }}
    h1 {{ margin-top:0; }}
    .muted {{ color:#8b949e; }}
    .row {{ display:flex; gap:10px; flex-wrap:wrap; align-items:center; }}
    label {{ display:block; margin:12px 0 5px; color:#8b949e; font-size:13px; }}
    input {{ width:100%; box-sizing:border-box; border-radius:10px; border:1px solid #30363d; background:#0d1117; color:#e6edf3; padding:10px; }}
    button, .button {{ display:inline-block; border-radius:10px; border:1px solid #238636; background:#238636; color:#fff; padding:10px 14px; font-weight:700; cursor:pointer; text-decoration:none; }}
    .secondary {{ background:#21262d; border-color:#30363d; }}
    .danger {{ background:#da3633; border-color:#da3633; }}
    pre, .status {{ white-space:pre-wrap; background:#0d1117; border:1px solid #30363d; border-radius:12px; padding:12px; overflow:auto; }}
    code {{ background:#0d1117; border:1px solid #30363d; border-radius:6px; padding:2px 5px; }}
  </style>
</head>
<body>
  <header><nav><a class="brand" href="/">TWAP</a><a href="/register">Регистрация</a><a href="/login">Вход</a><a href="/cabinet">ЛК</a><a href="/admin">Admin</a></nav></header>
  <main>{body}</main>
</body>
</html>"""
