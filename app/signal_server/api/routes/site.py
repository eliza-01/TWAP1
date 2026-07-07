from __future__ import annotations

import os

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter(tags=["site"])


def _bot_username() -> str:
    return (os.getenv("TELEGRAM_BOT_USERNAME") or "stage_twap_parser_bot").strip().lstrip("@")


@router.get("/", response_class=HTMLResponse)
async def index() -> str:
    bot = _bot_username()
    return _layout(
        "TWAP — доступ к сигналам",
        """
        <section class="hero">
          <div class="hero-copy">
            <p class="eyebrow">TWAP Signal Client</p>
            <h1>Доступ к сигналам и локальному торговому клиенту</h1>
            <p class="lead">Зарегистрируйтесь через Telegram, активируйте ключ и используйте desktop-клиент на своём компьютере или VPS. Биржевые ключи остаются только у Вас.</p>
            <div class="actions">
              <a class="button" href="/register">Начать регистрацию</a>
              <a class="button secondary" href="/login">Войти</a>
            </div>
          </div>
          <div class="hero-panel" aria-label="Что нужно сделать">
            <div class="panel-row"><span>1</span><b>Получите код в Telegram</b></div>
            <div class="panel-row"><span>2</span><b>Создайте аккаунт на сайте</b></div>
            <div class="panel-row"><span>3</span><b>Активируйте ключ</b></div>
            <div class="panel-row"><span>4</span><b>Запустите клиент</b></div>
          </div>
        </section>

        <section class="feature-grid">
          <article class="card soft">
            <div class="icon-badge">🔐</div>
            <h2>Вход через одноразовый код</h2>
            <p>Для регистрации и каждого входа используется свежий код из Telegram-бота. Мы заботимся о Вашей безопасности.</p>
          </article>
          <article class="card soft">
            <div class="icon-badge">⏱️</div>
            <h2>Баланс (время)</h2>
            <p>Оставшееся время доступа можно проверить в личном кабинете или кнопкой «Проверить баланс» в Telegram-боте.</p>
          </article>
          <article class="card soft">
            <div class="icon-badge">💻</div>
            <h2>Сделки только локально</h2>
            <p>Сайт отвечает за аккаунт и доступ. Торговля выполняется локальным exe-клиентом, а Ваши API-ключи хранятся только на Вашем ПК.</p>
          </article>
        </section>

        <section class="card guide-card">
          <div>
            <p class="eyebrow">Telegram-бот</p>
            <h2>В боте всегда есть две кнопки</h2>
            <p>«Получить код» выдаёт код регистрации или входа, а «Проверить баланс» показывает, сколько времени использования осталось.</p>
          </div>
          <a class="button secondary" target="_blank" rel="noopener" href="https://t.me/__BOT__">Открыть бота</a>
        </section>
        """.replace("__BOT__", bot),
    )


@router.get("/register", response_class=HTMLResponse)
async def register_page() -> str:
    bot = _bot_username()
    return _layout(
        "Регистрация — TWAP",
        """
        <section class="auth-shell">
          <aside class="auth-aside">
            <p class="eyebrow">Новый аккаунт</p>
            <h1>Создайте доступ за пару минут</h1>
            <p>Сначала нажмите «Получить код» в поле кода. Telegram-бот пришлёт одноразовый код регистрации.</p>
            <ol class="steps">
              <li>Откройте Telegram-бота.</li>
              <li>Получите код регистрации.</li>
              <li>Введите логин, пароль и код на этой странице.</li>
            </ol>
          </aside>

          <section class="card auth-card">
            <h2>Регистрация</h2>
            <p class="muted">После создания аккаунта можно будет войти и активировать ключ.</p>

            <label for="login">Логин</label>
            <input id="login" autocomplete="username" placeholder="например, trader01" />

            <label for="password">Пароль</label>
            <input id="password" type="password" autocomplete="new-password" placeholder="минимум 6 символов" />

            <label for="code">Код из Telegram</label>
            <div class="input-with-action">
              <input id="code" inputmode="numeric" autocomplete="one-time-code" placeholder="Введите код" />
              <a class="field-action" target="_blank" rel="noopener" href="https://t.me/__BOT__?start=register">Получить код</a>
            </div>

            <button class="button wide" onclick="register()">Создать аккаунт</button>
            <div id="out" class="notice" role="status"></div>
            <p class="form-footer">Уже есть аккаунт? <a href="/login">Войти</a></p>
          </section>
        </section>

        <script>
        async function register() {
          const out = document.getElementById('out');
          showMessage(out, 'Создаём аккаунт...');
          try {
            const res = await fetch('/api/auth/register', {
              method: 'POST',
              headers: {'content-type': 'application/json'},
              body: JSON.stringify({
                login: readValue('login'),
                password: readValue('password'),
                code: readValue('code')
              })
            });
            const data = await res.json();
            if (!res.ok || data.success === false) throw new Error(data.detail || data.message || 'Ошибка регистрации');
            showMessage(out, 'Аккаунт создан. Сейчас откроем страницу входа.', 'success');
            setTimeout(() => location.href = '/login', 1200);
          } catch (e) {
            showMessage(out, e.message, 'error');
          }
        }
        </script>
        """.replace("__BOT__", bot),
    )


@router.get("/login", response_class=HTMLResponse)
async def login_page() -> str:
    bot = _bot_username()
    return _layout(
        "Вход — TWAP",
        """
        <section class="auth-shell">
          <aside class="auth-aside">
            <p class="eyebrow">Вход</p>
            <h1>Войдите в аккаунт</h1>
            <p>Для каждого входа нужен свежий Telegram-код. Нажмите кнопку прямо в поле кода и вернитесь сюда.</p>
            <div class="mini-card">
              <b>Подсказка</b>
              <span>Код действует 5 минут. Если он истёк, просто получите новый.</span>
            </div>
          </aside>

          <section class="card auth-card">
            <h2>Вход</h2>
            <p class="muted">Введите логин, пароль и одноразовый код из Telegram-бота.</p>

            <label for="login">Логин</label>
            <input id="login" autocomplete="username" placeholder="Ваш логин" />

            <label for="password">Пароль</label>
            <input id="password" type="password" autocomplete="current-password" placeholder="Ваш пароль" />

            <label for="code">Код из Telegram</label>
            <div class="input-with-action">
              <input id="code" inputmode="numeric" autocomplete="one-time-code" placeholder="Введите код" />
              <a class="field-action" target="_blank" rel="noopener" href="https://t.me/__BOT__?start=login">Получить код</a>
            </div>

            <button class="button wide" onclick="login()">Войти</button>
            <div id="out" class="notice" role="status"></div>
            <p class="form-footer">Нет аккаунта? <a href="/register">Зарегистрироваться</a></p>
          </section>
        </section>

        <script>
        async function login() {
          const out = document.getElementById('out');
          showMessage(out, 'Проверяем данные...');
          try {
            const res = await fetch('/api/auth/login', {
              method: 'POST',
              headers: {'content-type': 'application/json'},
              body: JSON.stringify({
                login: readValue('login'),
                password: readValue('password'),
                code: readValue('code'),
                device_id: 'web-cabinet',
                device_name: 'web-cabinet'
              })
            });
            const data = await res.json();
            if (!res.ok || data.success === false) throw new Error(data.detail || data.message || 'Ошибка входа');
            localStorage.setItem('twap_session_token', data.token);
            location.href = '/cabinet';
          } catch (e) {
            showMessage(out, e.message, 'error');
          }
        }
        </script>
        """.replace("__BOT__", bot),
    )


@router.get("/cabinet", response_class=HTMLResponse)
async def cabinet_page() -> str:
    bot = _bot_username()
    return _layout(
        "Профиль — TWAP",
        """
        <section class="cabinet-hero">
          <div>
            <p class="eyebrow">Профиль</p>
            <h1>Ваш доступ к TWAPs</h1>
            <p class="lead">Здесь видно остаток времени, статус доступа и активацию ключа.</p>
          </div>
          <button class="button secondary" onclick="logout()">Выйти</button>
        </section>

        <section class="dashboard-grid">
          <article class="card status-card">
            <div class="card-head">
              <div>
                <p class="eyebrow">Аккаунт</p>
                <h2 id="loginTitle">Загрузка...</h2>
              </div>
              <span id="accessBadge" class="badge">Проверяем</span>
            </div>
            <div class="stat-list">
              <div><span>Осталось</span><b id="timeLeft">—</b></div>
              <div><span>Доступ до</span><b id="accessUntil">—</b></div>
            </div>
            <button class="button secondary" onclick="loadMe()">Обновить баланс</button>
            <div id="userOut" class="notice" role="status"></div>
          </article>

          <article class="card">
            <p class="eyebrow">Активация</p>
            <h2>Добавить время работы</h2>
            <p class="muted">Введите ключ активации. Его также можно активировать в Telegram-боте командой <code>/activate TWAP-...</code>.</p>
            <label for="activationKey">Ключ активации</label>
            <input id="activationKey" placeholder="TWAP-..." />
            <button class="button wide" onclick="activate()">Активировать ключ</button>
            <div id="activationOut" class="notice" role="status"></div>
          </article>
        </section>

        <section class="card guide-card">
          <div>
            <p class="eyebrow">Локальный клиент</p>
            <h2>Торговля запускается в desktop-клиенте</h2>
            <p>Сайт нужен для аккаунта, кодов и доступа. Сделки открывает отдельный exe-клиент на компьютере/VPS пользователя.</p>
            <p class="muted">Для входа в exe используйте логин, пароль и свежий код через Telegram-бота.</p>
          </div>
          <a class="button secondary" target="_blank" rel="noopener" href="https://t.me/__BOT__?start=login">Получить код</a>
        </section>

        <script>
        const token = localStorage.getItem('twap_session_token') || '';
        if (!token) location.href = '/login';

        async function api(url, opts = {}) {
          const res = await fetch(url, {
            ...opts,
            headers: {'content-type': 'application/json', 'authorization': 'Bearer ' + token, ...(opts.headers || {})}
          });
          const data = await res.json();
          if (!res.ok || data.success === false) throw new Error(data.detail || data.message || res.statusText);
          return data;
        }

        async function loadMe() {
          const out = document.getElementById('userOut');
          try {
            const data = await api('/api/auth/me');
            const u = data.user || {};
            const access = accessInfo(u.access_until);
            document.getElementById('loginTitle').textContent = u.login || 'Аккаунт';
            document.getElementById('timeLeft').textContent = access.left;
            document.getElementById('accessUntil').textContent = access.until;
            const badge = document.getElementById('accessBadge');
            badge.textContent = access.active ? 'Активен' : 'Не активен';
            badge.className = 'badge ' + (access.active ? 'good' : 'bad');
            showMessage(out, 'Данные обновлены.', 'success');
          } catch (e) {
            showMessage(out, e.message, 'error');
          }
        }

        async function activate() {
          const out = document.getElementById('activationOut');
          showMessage(out, 'Активируем ключ...');
          try {
            const data = await api('/api/auth/activate', {method: 'POST', body: JSON.stringify({key: readValue('activationKey')})});
            const access = accessInfo(data.user?.access_until);
            showMessage(out, 'Ключ активирован. Осталось: ' + access.left, 'success');
            document.getElementById('activationKey').value = '';
            await loadMe();
          } catch (e) {
            showMessage(out, e.message, 'error');
          }
        }

        async function logout() {
          try { await api('/api/auth/logout', {method: 'POST'}); } catch (e) {}
          localStorage.removeItem('twap_session_token');
          location.href = '/login';
        }

        function accessInfo(value) {
          if (!value) return {active: false, left: 'Время не добавлено', until: '—'};
          const until = new Date(value);
          if (Number.isNaN(until.getTime())) return {active: false, left: 'Не удалось прочитать дату', until: String(value)};
          const diff = until.getTime() - Date.now();
          return {active: diff > 0, left: diff > 0 ? humanDuration(diff) : 'Время закончилось', until: until.toLocaleString('ru-RU')};
        }

        function humanDuration(ms) {
          let totalMinutes = Math.max(1, Math.floor(ms / 60000));
          const days = Math.floor(totalMinutes / 1440); totalMinutes -= days * 1440;
          const hours = Math.floor(totalMinutes / 60); totalMinutes -= hours * 60;
          const parts = [];
          if (days) parts.push(days + ' д.');
          if (hours) parts.push(hours + ' ч.');
          if (totalMinutes || parts.length === 0) parts.push(totalMinutes + ' мин.');
          return parts.slice(0, 3).join(' ');
        }

        loadMe();
        </script>
        """.replace("__BOT__", bot),
    )


@router.get("/admin", response_class=HTMLResponse)
async def admin_page() -> str:
    return _layout(
        "Admin",
        """
        <section class="card auth-card narrow">
          <p class="eyebrow">Служебная страница</p>
          <h1>Admin</h1>
          <p class="muted">Введите SIGNAL_SERVER_ADMIN_KEY. Ключ хранится только в localStorage браузера.</p>
          <label for="adminKey">Admin key</label><input id="adminKey" type="password" />
          <label for="days">Дней доступа</label><input id="days" type="number" min="1" value="30" />
          <label for="expiresDays">Срок действия самого ключа, дней</label><input id="expiresDays" type="number" min="1" placeholder="пусто = без срока" />
          <label for="note">Заметка</label><input id="note" placeholder="кому / за что" />
          <button class="button wide" onclick="createKey()">Выпустить ключ</button>
          <div id="out" class="notice" role="status"></div>
        </section>
        <script>
        document.getElementById('adminKey').value = localStorage.getItem('twap_admin_key') || '';
        async function createKey() {
          const key = document.getElementById('adminKey').value;
          localStorage.setItem('twap_admin_key', key);
          const payload = {days: Number(document.getElementById('days').value || 0), note: document.getElementById('note').value};
          const exp = document.getElementById('expiresDays').value;
          if (exp) payload.expires_days = Number(exp);
          const out = document.getElementById('out'); showMessage(out, 'Создаём ключ...');
          try {
            const res = await fetch('/api/auth/activation-keys', {method: 'POST', headers: {'content-type': 'application/json', 'x-admin-key': key}, body: JSON.stringify(payload)});
            const data = await res.json();
            if (!res.ok || data.success === false) throw new Error(data.detail || data.message || 'Ошибка');
            showMessage(out, JSON.stringify(data.activation_key, null, 2), 'success');
          } catch (e) { showMessage(out, e.message, 'error'); }
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
  <script>
    try {{ document.documentElement.classList.add(localStorage.getItem('twap_session_token') ? 'is-auth' : 'is-guest'); }}
    catch (e) {{ document.documentElement.classList.add('is-guest'); }}
  </script>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #08111f;
      --panel: rgba(17, 29, 49, .86);
      --panel-strong: #111d31;
      --border: rgba(148, 163, 184, .18);
      --text: #eef6ff;
      --muted: #9fb0c6;
      --brand: #4f8cff;
      --brand-2: #6ee7b7;
      --danger: #fb7185;
      --success: #34d399;
      --shadow: 0 24px 80px rgba(0, 0, 0, .36);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(circle at 20% 10%, rgba(79, 140, 255, .24), transparent 32rem),
        radial-gradient(circle at 86% 0%, rgba(110, 231, 183, .12), transparent 28rem),
        var(--bg);
      color: var(--text);
    }}
    a {{ color: inherit; }}
    .site-header {{ position: sticky; top: 0; z-index: 10; border-bottom: 1px solid var(--border); background: rgba(8, 17, 31, .78); backdrop-filter: blur(18px); }}
    .nav {{ max-width: 1120px; margin: 0 auto; padding: 16px 22px; display: flex; align-items: center; gap: 18px; }}
    .brand {{ display: inline-flex; gap: 10px; align-items: center; margin-right: auto; text-decoration: none; font-weight: 850; letter-spacing: .2px; }}
    .brand-mark {{ width: 34px; height: 34px; display: grid; place-items: center; border-radius: 12px; background: linear-gradient(135deg, var(--brand), var(--brand-2)); color: #06101e; font-size: 13px; }}
    .nav-links {{ display: flex; align-items: center; gap: 10px; }}
    .nav-links a {{ color: var(--muted); text-decoration: none; font-weight: 700; padding: 10px 12px; border-radius: 999px; }}
    .nav-links a:hover {{ color: var(--text); background: rgba(255,255,255,.06); }}
    .user-icon {{ width: 42px; height: 42px; display: grid; place-items: center; border-radius: 999px; border: 1px solid var(--border); background: rgba(255,255,255,.07); font-size: 19px; }}
    html.is-auth [data-guest], html.is-guest [data-auth] {{ display: none !important; }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 34px 22px 64px; }}
    .hero {{ min-height: 430px; display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(300px, .8fr); gap: 26px; align-items: center; padding: 34px; border: 1px solid var(--border); border-radius: 32px; background: linear-gradient(135deg, rgba(17,29,49,.94), rgba(17,29,49,.58)); box-shadow: var(--shadow); }}
    .hero h1, .auth-aside h1, .cabinet-hero h1 {{ margin: 0; font-size: clamp(34px, 5vw, 64px); line-height: .98; letter-spacing: -1.6px; }}
    .lead {{ color: #c6d5ea; font-size: 18px; line-height: 1.65; max-width: 690px; }}
    .eyebrow {{ margin: 0 0 10px; color: var(--brand-2); text-transform: uppercase; letter-spacing: .12em; font-size: 12px; font-weight: 850; }}
    .actions, .row {{ display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }}
    .button, button {{ display: inline-flex; align-items: center; justify-content: center; min-height: 46px; border-radius: 14px; border: 1px solid rgba(79, 140, 255, .72); background: linear-gradient(135deg, var(--brand), #7c3aed); color: #fff; padding: 12px 18px; font-weight: 850; cursor: pointer; text-decoration: none; box-shadow: 0 10px 30px rgba(79,140,255,.24); }}
    .button:hover, button:hover {{ transform: translateY(-1px); }}
    .button.secondary, button.secondary {{ background: rgba(255,255,255,.07); border-color: var(--border); color: var(--text); box-shadow: none; }}
    .button.wide {{ width: 100%; margin-top: 18px; }}
    .hero-panel, .card {{ border: 1px solid var(--border); border-radius: 26px; background: var(--panel); box-shadow: var(--shadow); }}
    .hero-panel {{ padding: 18px; display: grid; gap: 12px; }}
    .panel-row {{ display: flex; align-items: center; gap: 12px; padding: 15px; border-radius: 18px; background: rgba(255,255,255,.06); }}
    .panel-row span {{ width: 32px; height: 32px; display: grid; place-items: center; border-radius: 11px; color: #07111f; background: var(--brand-2); font-weight: 900; }}
    .feature-grid, .dashboard-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 18px; margin-top: 18px; }}
    .dashboard-grid {{ grid-template-columns: 1fr 1fr; }}
    .card {{ padding: 24px; }}
    .card h1, .card h2 {{ margin-top: 0; letter-spacing: -.35px; }}
    .card p {{ color: #c6d5ea; line-height: 1.6; }}
    .soft {{ box-shadow: none; }}
    .icon-badge {{ width: 44px; height: 44px; display: grid; place-items: center; border-radius: 15px; background: rgba(79,140,255,.16); margin-bottom: 14px; }}
    .guide-card {{ display: flex; display: none; margin-top: 18px; gap: 18px; align-items: center; justify-content: space-between; }}
    .auth-shell {{ display: grid; grid-template-columns: minmax(280px, .9fr) minmax(320px, 1fr); gap: 22px; align-items: stretch; }}
    .auth-aside {{ padding: 34px; border: 1px solid var(--border); border-radius: 32px; background: linear-gradient(160deg, rgba(79,140,255,.22), rgba(17,29,49,.7)); box-shadow: var(--shadow); }}
    .auth-aside p, .steps {{ color: #c6d5ea; line-height: 1.65; }}
    .steps {{ padding-left: 20px; }}
    .mini-card {{ margin-top: 18px; padding: 16px; border-radius: 18px; background: rgba(255,255,255,.07); display: grid; gap: 6px; color: #c6d5ea; }}
    .auth-card {{ max-width: 520px; width: 100%; justify-self: end; }}
    .auth-card.narrow {{ margin: 0 auto; }}
    .muted, .form-footer {{ color: var(--muted); }}
    label {{ display: block; margin: 16px 0 7px; color: #b9c8dd; font-size: 14px; font-weight: 750; }}
    input {{ width: 100%; height: 50px; border-radius: 15px; border: 1px solid var(--border); background: rgba(4, 11, 22, .72); color: var(--text); padding: 0 14px; outline: none; font-size: 15px; }}
    input:focus {{ border-color: rgba(79,140,255,.85); box-shadow: 0 0 0 4px rgba(79,140,255,.14); }}
    .input-with-action {{ position: relative; }}
    .input-with-action input {{ padding-right: 142px; }}
    .field-action {{ position: absolute; right: 6px; top: 6px; height: 38px; display: inline-flex; align-items: center; justify-content: center; border-radius: 12px; background: rgba(79,140,255,.17); border: 1px solid rgba(79,140,255,.42); padding: 0 12px; color: #dce8ff; font-size: 13px; font-weight: 850; text-decoration: none; }}
    .notice {{ display: none; margin-top: 14px; white-space: pre-wrap; border-radius: 16px; border: 1px solid var(--border); background: rgba(255,255,255,.06); padding: 13px 14px; color: #dbeafe; overflow: auto; }}
    .notice.visible {{ display: block; }}
    .notice.success {{ border-color: rgba(52,211,153,.42); background: rgba(52,211,153,.11); }}
    .notice.error {{ border-color: rgba(251,113,133,.45); background: rgba(251,113,133,.12); }}
    .form-footer {{ margin-bottom: 0; text-align: center; }}
    code {{ background: rgba(4,11,22,.72); border: 1px solid var(--border); border-radius: 8px; padding: 2px 6px; }}
    .cabinet-hero {{ display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 30px; border: 1px solid var(--border); border-radius: 32px; background: linear-gradient(135deg, rgba(17,29,49,.94), rgba(17,29,49,.58)); box-shadow: var(--shadow); margin-bottom: 18px; }}
    .card-head {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }}
    .badge {{ display: inline-flex; align-items: center; min-height: 30px; border-radius: 999px; padding: 6px 10px; font-size: 12px; font-weight: 900; color: #cbd5e1; background: rgba(255,255,255,.08); }}
    .badge.good {{ color: #052e1d; background: var(--success); }}
    .badge.bad {{ color: #3f0713; background: var(--danger); }}
    .stat-list {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 18px 0; }}
    .stat-list div {{ padding: 16px; border-radius: 18px; background: rgba(255,255,255,.06); }}
    .stat-list span {{ display: block; color: var(--muted); font-size: 13px; margin-bottom: 8px; }}
    .stat-list b {{ font-size: 18px; }}
    @media (max-width: 820px) {{
      .hero, .auth-shell, .feature-grid, .dashboard-grid {{ grid-template-columns: 1fr; }}
      .auth-card {{ max-width: none; justify-self: auto; }}
      .guide-card, .cabinet-hero {{ align-items: stretch; flex-direction: column; }}
      .nav {{ padding-inline: 14px; }}
      .nav-links a:not(.user-icon) {{ padding-inline: 9px; }}
      main {{ padding-inline: 14px; }}
    }}
    @media (max-width: 520px) {{
      .hero, .auth-aside, .card, .cabinet-hero {{ border-radius: 22px; padding: 20px; }}
      .input-with-action input {{ padding-right: 14px; padding-bottom: 46px; height: 92px; }}
      .field-action {{ left: 6px; right: 6px; top: auto; bottom: 6px; }}
      .stat-list {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header class="site-header">
    <nav class="nav">
      <a class="brand" href="/"><span class="brand-mark">TW</span><span>TWAPs</span></a>
      <div class="nav-links">
        <a href="/register" data-guest>Регистрация</a>
        <a href="/login" data-guest>Войти</a>
        <a class="user-icon" href="/cabinet" title="Профиль" aria-label="Профиль" data-auth>👤</a>
      </div>
    </nav>
  </header>
  <main>{body}</main>
  <script>
    function readValue(id) {{ return (document.getElementById(id)?.value || '').trim(); }}
    function showMessage(node, message, type = '') {{
      if (!node) return;
      node.textContent = message || '';
      node.className = 'notice visible' + (type ? ' ' + type : '');
    }}
  </script>
</body>
</html>"""
