# -*- coding: utf-8 -*-
# delivery_app.py — Streamlit (браузер)
# Калькулятор доставки (розница) с:
# - логотипом/фавиконом
# - точками выхода (в т.ч. Точка 7)
# - определением принадлежности к рейсам (по дороге)
# - проверкой "в пределах адм. границ Твери"
# - ORS для расстояний по дорогам + кэширование
# - автосбросом тарифа 15 руб./км при смене адреса/даты
# - автопушем cache.json в GitHub

import os
import io
import json
import math
import time
import hashlib
import datetime as dt
from typing import Dict, Tuple, List, Optional

import requests
import streamlit as st

# ============ БАЗОВЫЕ НАСТРОЙКИ СТРАНИЦЫ ============
st.set_page_config(
    page_title="Калькулятор доставки (розница)",
    page_icon="static/favicon.png",  # ваш favicon
    layout="centered"
)

# Центровка логотипа
try:
    st.markdown(
        """
        <div style="display:flex;justify-content:center;margin:6px 0 2px 0;">
            <img src="static/logo.png" alt="logo" style="height:68px;"/>
        </div>
        """,
        unsafe_allow_html=True
    )
except Exception:
    pass

# ================== КОНСТАНТЫ И КОНФИГ ==================
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
ORS_API_KEY = os.environ.get("ORS_API_KEY", "").strip()

GIT_REPO = os.environ.get("GIT_REPO", "").strip()  # https://github.com/<user>/<repo>.git
GIT_USER = os.environ.get("GIT_USER", "").strip()
GIT_TOKEN = os.environ.get("GIT_TOKEN", "").strip()

# Файлы кэшей
CACHE_FILE = "cache.json"              # кэш расстояний до НП
ROUTES_FILE = "routes_cache.json"      # кэш геокодинга рейсов и их полилиний
BOUNDARY_FILE = "boundary_cache.json"  # кэш полигона админ. границ Твери

# Точки выхода (ЛОН, ШИР) — используем точный порядок как у вас (lon, lat)
EXIT_POINTS = [
    (36.055364, 56.795587),  # 1
    (35.871802, 56.808677),  # 2
    (35.804913, 56.831684),  # 3
    (36.020937, 56.850973),  # 4
    (35.797443, 56.882207),  # 5
    (35.932805, 56.902966),  # 6
    # Новая Точка 7: пользователь прислал (56.831684, 35.804913) — это (lat, lon).
    # В приложении точки всегда (lon, lat), значит корректное добавление:
    (35.804913, 56.831684),  # 7 (географически совпадает с точкой 3; добавляем по просьбе)
]

# Базовые тарифы
BASE_PRICES = {
    "маленький": 350,
    "средний": 600,
    "большой": 900,
}
TARIFF_DEFAULT = 32.0
TARIFF_ROUTE = 15.0

# Таблица заранее известных расстояний (пример; сохраните свою как в старом коде)
# Формат: "НП": км_туда_и_обратно, и опционально source="таблица"
DISTANCES_TABLE = {
    "Завидово": {"distance": 107.36, "source": "таблица"},
    "Конаково": {"distance": 134.00, "source": "таблица"},
    # ... добавьте ваши постоянные записи (как было в прежнем варианте)
}

# Рейсы (списки городов в порядке следования). Имена — как вы предложили.
ROUTE_GROUPS = {
    "КВ_КЛ": ["Конаково", "Редкино", "Мокшино", "Новозавидовский", "Клин"],
    "ЛШ_ШХ_ВК_РЗ": ["Руза", "Волоколамск", "Шаховская", "Лотошино"],
    "РЖ_СЦ_ЗБ_ЗД_ЖК_ТЦ_ВЛ_НЛ_ОЛ_ВЛ": [
        "Великие Луки", "Жарковский", "Торопец", "Западная Двина",
        "Нелидово", "Оленино", "Зубцов", "Ржев", "Старица"
    ],
    "КМ_ДБ": ["Дубна", "Кимры"],
    "ТО_СП_ВВ_БГ_УД": ["Бологое", "Вышний Волочек", "Спирово", "Торжок", "Лихославль", "Удомля"],
    "РШ_МХ_ЛС_СД": ["Сандово", "Лесное", "Максатиха", "Рамешки"],
    "БК_СН_КХ_ВГ": ["Весьегонск", "Красный Холм", "Сонково", "Бежецк"],
    "КШ_КЗ_КГ": ["Кесова Гора", "Калязин", "Кашин"],
    "СЛЖ_ОСТ_КУВ": ["Кувшиново", "Осташков", "Селижарово"],  # Пено иногда отдельно
}

# График дней: какой набор маршрутов действует в какой день (0=ПН ... 6=ВС)
ROUTES_BY_WEEKDAY = {
    0: ["РЖ_СЦ_ЗБ_ЗД_ЖК_ТЦ_ВЛ_НЛ_ОЛ_ВЛ", "КШ_КЗ_КГ"],  # ПН
    1: ["КВ_КЛ", "ЛШ_ШХ_ВК_РЗ"],                        # ВТ
    2: ["КМ_ДБ", "РЖ_СЦ_ЗБ_ЗД_ЖК_ТЦ_ВЛ_НЛ_ОЛ_ВЛ", "СЛЖ_ОСТ_КУВ"],  # СР (+ Пено иногда)
    3: ["РЖ_СЦ_ЗБ_ЗД_ЖК_ТЦ_ВЛ_НЛ_ОЛ_ВЛ", "ТО_СП_ВВ_БГ_УД"],        # ЧТ (ВЛ часть)
    4: ["ТО_СП_ВВ_БГ_УД", "РШ_МХ_ЛС_СД", "БК_СН_КХ_ВГ"],            # ПТ
    5: [],  # СБ
    6: [],  # ВС
}

# Нормализация «Тверская область, …»
DEFAULT_PREFIX = "Тверская область, "


# ================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==================
def load_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    # Расстояние по прямой (для оценки и сэмплинга)
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2 +
         math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


def nearest_exit_point(lat: float, lon: float) -> Tuple[Tuple[float, float], float]:
    # Возвращает (lon,lat) точки выхода и расстояние по прямой до неё (км)
    best = None
    best_d = 1e9
    for (ex_lon, ex_lat) in EXIT_POINTS:
        d = haversine_km(lat, lon, ex_lat, ex_lon)
        if d < best_d:
            best_d = d
            best = (ex_lon, ex_lat)
    return best, best_d


def geocode_nominatim(place: str) -> Optional[Tuple[float, float, str]]:
    # Минимальный устойчивый геокодер (без API-ключа)
    url = "https://nominatim.openstreetmap.org/search"
    try:
        resp = requests.get(
            url,
            params={
                "q": place,
                "format": "json",
                "limit": 1,
                "addressdetails": 0,
            },
            headers={"User-Agent": "delivery-calc/1.0"}
        )
        if resp.status_code != 200:
            return None
        j = resp.json()
        if not j:
            return None
        lat = float(j[0]["lat"])
        lon = float(j[0]["lon"])
        display = j[0].get("display_name", place)
        return (lat, lon, display)
    except Exception:
        return None


def get_tver_boundary_polygon() -> List[List[Tuple[float, float]]]:
    """
    Получаем полигон административных границ Твери (список контуров),
    кэшируем в boundary_cache.json.
    """
    cache = load_json(BOUNDARY_FILE, default={})
    if "tver_boundary" in cache:
        return cache["tver_boundary"]

    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": "Тверь, Россия",
        "format": "json",
        "polygon_geojson": 1,
        "limit": 1,
    }
    try:
        resp = requests.get(url, params=params, headers={"User-Agent": "delivery-calc/1.0"})
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return []
        geo = data[0].get("geojson", {})
        rings = []
        def parse_coords(coords):
            # Возвращаем список (lon,lat)
            return [(float(x), float(y)) for x, y in coords]

        if geo.get("type") == "Polygon":
            for ring in geo["coordinates"]:
                rings.append(parse_coords(ring))
        elif geo.get("type") == "MultiPolygon":
            for poly in geo["coordinates"]:
                for ring in poly:
                    rings.append(parse_coords(ring))
        if rings:
            cache["tver_boundary"] = rings
            save_json(BOUNDARY_FILE, cache)
        return rings
    except Exception:
        return []


def point_in_polygon(lon: float, lat: float, polygon: List[Tuple[float, float]]) -> bool:
    """
    Классический ray-casting для одного контура (lon,lat).
    """
    inside = False
    n = len(polygon)
    if n < 3:
        return False
    x, y = lon, lat
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if ((y1 > y) != (y2 > y)) and \
           (x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1):
            inside = not inside
    return inside


def is_inside_tver(lat: float, lon: float) -> bool:
    # Проверяем по всем контурам
    rings = get_tver_boundary_polygon()
    for ring in rings:
        if point_in_polygon(lon, lat, ring):
            return True
    return False


def ors_route_distance_km(lat1, lon1, lat2, lon2) -> Optional[float]:
    if not ORS_API_KEY:
        return None
    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {"Authorization": ORS_API_KEY, "Content-Type": "application/json"}
    body = {
        "coordinates": [[lon1, lat1], [lon2, lat2]],
        "units": "km",
        "geometry": False,
    }
    try:
        r = requests.post(url, headers=headers, json=body, timeout=30)
        r.raise_for_status()
        j = r.json()
        meters = j["routes"][0]["summary"]["distance"]
        return float(meters) / 1000.0
    except Exception:
        return None


def ors_route_polyline(lon1, lat1, lon2, lat2) -> Optional[List[Tuple[float, float]]]:
    """ Геометрия маршрута между двумя точками (lon,lat). """
    if not ORS_API_KEY:
        return None
    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {"Authorization": ORS_API_KEY, "Content-Type": "application/json"}
    body = {
        "coordinates": [[lon1, lat1], [lon2, lat2]],
        "units": "km",
        "geometry": True,
        "elevation": False,
    }
    try:
        r = requests.post(url, headers=headers, json=body, timeout=45)
        r.raise_for_status()
        j = r.json()
        coords = j["routes"][0]["geometry"]["coordinates"]  # [[lon,lat],...]
        return [(float(x), float(y)) for x, y in coords]
    except Exception:
        return None


def sample_polyline(poly: List[Tuple[float, float]], step_km: float = 2.0) -> List[Tuple[float, float]]:
    """ Сэмплинг полилинии по шагу step_km (в lon,lat), равномерно вдоль длины. """
    if not poly or len(poly) < 2:
        return poly or []
    pts = [poly[0]]
    acc = 0.0
    for i in range(1, len(poly)):
        lon1, lat1 = poly[i - 1]
        lon2, lat2 = poly[i]
        seg = haversine_km(lat1, lon1, lat2, lon2)
        acc += seg
        if acc >= step_km:
            pts.append((lon2, lat2))
            acc = 0.0
    if pts[-1] != poly[-1]:
        pts.append(poly[-1])
    return pts


def normalize_np_name(name: str) -> str:
    return name.strip().lower()


def show_status(msg: str):
    st.caption(msg)


def ensure_cache_files():
    for path, default in [
        (CACHE_FILE, {}),
        (ROUTES_FILE, {"geocoded": {}, "routes": {}}),
        (BOUNDARY_FILE, {}),
    ]:
        if not os.path.exists(path):
            save_json(path, default)


# ================== РАСЧЁТ «ПО РЕЙСУ» ==================
def build_routes_for_weekday(weekday: int, admin_mode: bool = False):
    """
    Для данного дня:
     - геокодируем города (если не закэшированы)
     - строим полилинии между соседними городами
     - возвращаем список узлов (lon,lat), сэмплированных через ~2 км
    """
    ensure_cache_files()
    routes_cache = load_json(ROUTES_FILE, {"geocoded": {}, "routes": {}})

    route_codes = ROUTES_BY_WEEKDAY.get(weekday, [])
    all_nodes: List[Tuple[float, float, str]] = []  # (lon,lat, route_code)

    for code in route_codes:
        cities = ROUTE_GROUPS.get(code, [])
        # Геокодируем все узловые города данного маршрута
        coords_list: List[Tuple[str, float, float]] = []
        for city in cities:
            if city not in routes_cache["geocoded"]:
                g = geocode_nominatim(f"{city}, Тверская область, Россия")
                if not g:
                    g = geocode_nominatim(f"{city}, Россия")
                if g:
                    lat, lon, _ = g
                    routes_cache["geocoded"][city] = {"lat": lat, "lon": lon}
                    save_json(ROUTES_FILE, routes_cache)
            info = routes_cache["geocoded"].get(city)
            if info:
                coords_list.append((city, info["lat"], info["lon"]))

        # Между соседями строим полилинии
        for i in range(len(coords_list) - 1):
            c1, lat1, lon1 = coords_list[i]
            c2, lat2, lon2 = coords_list[i + 1]
            key = f"{c1}__{c2}"
            if key not in routes_cache["routes"]:
                poly = ors_route_polyline(lon1, lat1, lon2, lat2)
                if poly:
                    routes_cache["routes"][key] = poly
                    save_json(ROUTES_FILE, routes_cache)

            poly = routes_cache["routes"].get(key)
            if poly:
                nodes = sample_polyline(poly, step_km=2.0)
                # Пометим каждый узел кодом маршрута
                for (lon, lat) in nodes:
                    all_nodes.append((lon, lat, code))

    if admin_mode:
        st.write("Собрано узлов по маршрутам на день:", len(all_nodes))
    return all_nodes


def road_distance_to_routes(lat: float, lon: float, weekday: int, max_nodes: int = 120, admin_mode: bool = False):
    """
    Ищем минимальную дорожную дистанцию от точки (lat,lon) до любого узла полилиний «дневных» рейсов.
    Ограничиваем количество узлов (для производительности).
    """
    all_nodes = build_routes_for_weekday(weekday, admin_mode=admin_mode)
    if not all_nodes:
        return None, None

    # Фильтруем ближайшие по прямой N узлов — затем считаем ORS-дистанцию только к ним
    nodes_sorted = sorted(
        all_nodes,
        key=lambda p: haversine_km(lat, lon, p[1], p[0])
    )
    nodes_subset = nodes_sorted[:max_nodes]

    best_km = None
    best_code = None
    with st.spinner("Проверяем отклонение от рейса (по дороге)..."):
        for (n_lon, n_lat, code) in nodes_subset:
            d_km = ors_route_distance_km(lat, lon, n_lat, n_lon)
            if d_km is None:
                continue
            if (best_km is None) or (d_km < best_km):
                best_km = d_km
                best_code = code

    return best_km, best_code


# ================== GIT: PUSH КЭША ==================
def git_autopush_cache(admin_mode: bool = False) -> str:
    """
    Пытаемся:
      - git init (если нужно)
      - git remote add origin <GIT_REPO> (если нет)
      - git switch -c main (или checkout main), при конфликте — авто-коммит
      - git add cache.json && git commit && git push origin main
    """
    if not (GIT_REPO and GIT_USER and GIT_TOKEN):
        return "Пропущен push: нет GIT_REPO/GIT_USER/GIT_TOKEN."

    def run(cmd: List[str]) -> Tuple[int, str]:
        try:
            import subprocess
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
            return res.returncode, res.stdout.strip()
        except Exception as e:
            return 1, str(e)

    # монтируем URL с токеном
    auth_repo = GIT_REPO
    if auth_repo.startswith("https://github.com/") and "@" not in auth_repo:
        auth_repo = auth_repo.replace("https://github.com/", f"https://{GIT_USER}:{GIT_TOKEN}@github.com/")

    rc, out = run(["git", "init"])
    if admin_mode:
        st.caption(f"git init: {out}")

    # remote
    rc, out = run(["git", "remote", "-v"])
    if "origin" not in out:
        rc, out = run(["git", "remote", "add", "origin", auth_repo])

    # пытаемся на main
    rc, out = run(["git", "checkout", "main"])
    if rc != 0:
        # пробуем создать main
        run(["git", "checkout", "-B", "main"])

    # add/commit/push
    run(["git", "add", CACHE_FILE])
    rc, out = run(["git", "commit", "-m", "Update cache.json"])
    if admin_mode:
        st.caption(f"git commit: {out}")

    rc, out = run(["git", "push", "-u", "origin", "main"])
    if rc != 0 and "non-fast-forward" in out:
        # обновимся и повторим
        run(["git", "pull", "--rebase", "origin", "main"])
        rc, out = run(["git", "push", "origin", "main"])

    return "Success" if rc == 0 else ("Failed: " + out[:300])


# ================== UI / СОСТОЯНИЕ ==================
st.title("Калькулятор стоимости доставки по Твери и области для розничных клиентов")

# Админ-режим
with st.expander("Админ режим", expanded=False):
    admin_pass = st.text_input("Админ пароль", type="password")
    admin_mode = (admin_pass == ADMIN_PASSWORD)
    if admin_mode:
        st.success("Админ режим активирован")
    else:
        st.info("Введите пароль для доступа к расширенным настройкам.")

# Настройки рейсов/кэша для админа
if admin_mode:
    with st.expander("Настройки рейсов/кэш/гит", expanded=False):
        max_dev_km = st.number_input("Макс. отклонение адреса от графика рейса (по дороге), км",
                                     min_value=2.0, max_value=80.0, value=float(st.session_state.get("max_dev_km", 10.0)),
                                     step=1.0, format="%.2f")
        st.session_state["max_dev_km"] = max_dev_km
        st.caption("При отклонении ≤ этого порога предложим доставку «по рейсу» (тариф 15 руб./км).")

        if st.button("Очистить кэш маршрутов (routes_cache.json)"):
            save_json(ROUTES_FILE, {"geocoded": {}, "routes": {}})
            st.success("Кэш маршрутов очищен.")

        if st.button("Обновить полигон границ Твери (boundary_cache.json)"):
            try:
                if os.path.exists(BOUNDARY_FILE):
                    os.remove(BOUNDARY_FILE)
                _ = get_tver_boundary_polygon()
                st.success("Полигон границ Твери обновлён.")
            except Exception as e:
                st.error(f"Ошибка: {e}")

        if st.button("Сделать git push кэша"):
            res = git_autopush_cache(admin_mode=True)
            st.write("Git push:", res)

# Основной ввод
cargo_size = st.selectbox("Размер груза", ["маленький", "средний", "большой"])
addr_default = st.session_state.get("last_addr", DEFAULT_PREFIX)
address = st.text_input("Введите адрес доставки", value=addr_default, key="addr_input")

# Основной выбор даты (streamlit виджет)
date_default = st.session_state.get("last_date", dt.date.today())
date_obj = st.date_input("Выберите дату доставки", value=date_default, format="DD.MM.YYYY", key="date_input")

# Русифицированный календарь (вспомогательный — синхронизирует дату выше)
st.markdown("#### Дата доставки")
st.components.v1.html(
    f"""
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css">
    <script src="https://cdn.jsdelivr.net/npm/flatpickr"></script>
    <script src="https://cdn.jsdelivr.net/npm/flatpickr/dist/l10n/ru.js"></script>
    <input id="ru_date" style="font-size:16px;padding:6px 10px;border:1px solid #ddd;border-radius:6px;width:180px;" placeholder="выберите дату" />
    <script>
      const dflt = "{date_obj.strftime('%d.%m.%Y')}";
      const input = document.getElementById("ru_date");
      window.flatpickr.localize(window.flatpickr.l10ns.ru);
      const fp = window.flatpickr(input, {{
          dateFormat: "d.m.Y",
          defaultDate: dflt,
          locale: "ru",
          weekNumbers: false
      }});
      // отправляем выбранную дату обратно через hash (Streamlit перезагрузит страницу)
      input.addEventListener('change', () => {{
          const v = input.value; // dd.mm.yyyy
          if (v) {{
            const url = new URL(window.location.href);
            url.searchParams.set("ruDate", v);
            window.location.href = url.toString();
          }}
      }});
    </script>
    """,
    height=80
)

# Считываем дату из query string (если кликнули в рус. календаре)
qs = st.query_params
if "ruDate" in qs:
    try:
        d_ru = qs["ruDate"]
        dd, mm, yy = d_ru.split(".")
        new_date = dt.date(int(yy), int(mm), int(dd))
        # синхронизируем основной виджет
        if new_date != date_obj:
            date_obj = new_date
            st.session_state["date_input"] = new_date
    except Exception:
        pass

# Сброс «по рейсу» при смене адреса/даты
prev_key = st.session_state.get("prev_hash", "")
cur_key = hashlib.md5(f"{address}|{date_obj.isoformat()}".encode("utf-8")).hexdigest()
if cur_key != prev_key:
    st.session_state["use_route_tariff_confirmed"] = False
    st.session_state["show_route_offer"] = False
    st.session_state["prev_hash"] = cur_key

# Кнопка расчёта
calc = st.button("Рассчитать", type="primary")

# ================== ОСНОВНАЯ ЛОГИКА РАСЧЁТА ==================
if calc:
    ensure_cache_files()
    route_offer_shown = False

    # Нормализация адреса: при необходимости добавим префикс
    addr_clean = address.strip()
    if not addr_clean:
        st.error("Введите адрес.")
        st.stop()

    if not addr_clean.startswith(DEFAULT_PREFIX):
        # не навязываем пользователю, но для геокода используем полный, а в поле оставим как есть
        geo_query = DEFAULT_PREFIX + addr_clean
    else:
        geo_query = addr_clean

    # Геокод адреса
    with st.spinner("Поиск координат адреса..."):
        g = geocode_nominatim(geo_query)
    if not g:
        st.error("Не удалось геокодировать адрес. Попробуйте уточнить.")
        st.stop()
    lat, lon, disp = g

    # Проверим «в пределах Твери»
    inside_tver = False
    with st.spinner("Проверка границ города..."):
        inside_tver = is_inside_tver(lat, lon)

    # Находим ближайшую точку выхода
    ex_pt, dist_to_exit_direct = nearest_exit_point(lat, lon)  # по прямой
    ex_lon, ex_lat = ex_pt

    # Достаём расстояние туда-обратно (км) — приоритет: таблица -> кэш -> ORS
    src = None
    cache = load_json(CACHE_FILE, default={})
    np_name = disp.split(",")[0].strip()  # извлечём первое имя (как раньше)
    np_norm = normalize_np_name(np_name)

    # 1) Таблица
    if np_name in DISTANCES_TABLE:
        dist_km = float(DISTANCES_TABLE[np_name]["distance"])
        src = "таблица"
    # 2) Кэш
    elif np_name in cache:
        dist_km = float(cache[np_name]["distance"])
        src = "кэш"
        # подкорректируем ближайший выход (если сохранён)
        ex_info = cache[np_name].get("exit_point")
        if ex_info and isinstance(ex_info, (list, tuple)) and len(ex_info) == 2:
            ex_lon, ex_lat = ex_info[0], ex_info[1]
    else:
        # 3) ORS: от ближайшей точки выхода до адреса, умножаем на 2
        if not ORS_API_KEY:
            st.error("ORS_API_KEY не настроен в переменных окружения. Нельзя посчитать расстояние по дорогам.")
            st.stop()
        with st.spinner("Расчёт расстояния по дорогам (ORS)..."):
            oneway = ors_route_distance_km(ex_lat, ex_lon, lat, lon)
        if oneway is None:
            st.error("Не удалось получить расстояние от ORS.")
            st.stop()
        dist_km = round(oneway * 2.0, 3)
        src = "ors"
        # Сохраним в кэш
        cache[np_name] = {"distance": dist_km, "exit_point": [ex_lon, ex_lat]}
        save_json(CACHE_FILE, cache)
        if admin_mode:
            st.caption("Кэш обновлён, попытка git push…")
            res = git_autopush_cache(admin_mode=True)
            st.caption("Git push: " + res)

    # Если внутри Твери — километраж не берём
    if inside_tver:
        total = BASE_PRICES[cargo_size]
        st.subheader(f"Стоимость доставки: {total} руб.")
        st.write("")
        st.write(f"**Дата:** {date_obj.strftime('%d.%m.%Y')} ({['Понедельник','Вторник','Среда','Четверг','Пятница','Суббота','Воскресенье'][date_obj.weekday()]})")
        st.info("В пределах адм. границ Твери — доплата за километраж не начисляется.")
        st.write(f"**Координаты:** lat={lat:.6f}, lon={lon:.6f}")
        st.write(f"**Ближайшая точка выхода:** ({ex_lon:.6f}, {ex_lat:.6f})")
        st.write(f"**Расстояние до выхода (по прямой):** {dist_to_exit_direct:.2f} км")
        st.write(f"**Извлечённый населённый пункт:** {np_name}")
        st.stop()

    # Вне Твери — проверяем «по рейсу»
    weekday = date_obj.weekday()
    max_dev_km = float(st.session_state.get("max_dev_km", 10.0))

    # Ищем отклонение по дороге до узлов рейсов на этот день
    dev_km, route_code = road_distance_to_routes(lat, lon, weekday, admin_mode=admin_mode)

    offer_possible = (dev_km is not None) and (dev_km <= max_dev_km) and (route_code is not None)
    if offer_possible:
        # показываем предложение
        st.session_state["show_route_offer"] = True
        st.session_state["route_code_found"] = route_code
    else:
        st.session_state["show_route_offer"] = False
        st.session_state["route_code_found"] = None
        st.session_state["use_route_tariff_confirmed"] = False

    # Подсказка по рейсу
    if st.session_state.get("show_route_offer", False):
        with st.expander("Доставка по рейсу вместе с оптовыми заказами", expanded=True):
            st.write(f"Маршрут дня: **{st.session_state.get('route_code_found')}**")
            st.write(f"Отклонение по дороге до маршрута: **{dev_km:.2f} км** (порог: {max_dev_km:.2f} км)")
            if not st.session_state.get("use_route_tariff_confirmed", False):
                agree = st.selectbox(
                    "Вы уверены, что данный заказ можно доставить по рейсу вместе с оптовыми заказами?",
                    ["Нет", "Да"]
                )
                if agree == "Да":
                    st.session_state["use_route_tariff_confirmed"] = True

    # Выбор тарифа
    use_route_tariff = bool(st.session_state.get("use_route_tariff_confirmed", False))
    tariff = TARIFF_ROUTE if use_route_tariff else TARIFF_DEFAULT

    # Итоговая стоимость
    base = BASE_PRICES[cargo_size]
    extra = round(dist_km * tariff, 2)
    total = math.ceil(base + extra)

    st.subheader(f"Стоимость доставки: {total} руб.")
    st.write("")
    st.write(f"**Дата:** {date_obj.strftime('%d.%m.%Y')} ({['Понедельник','Вторник','Среда','Четверг','Пятница','Суббота','Воскресенье'][weekday]})")
    st.write(f"**Километраж:** {dist_km:.2f} км")
    st.write(f"**Тариф:** {int(tariff)} руб./км")
    st.write(f"**Рейс:** {'Да (' + st.session_state.get('route_code_found','') + ')' if use_route_tariff else 'Нет'}")

    st.write("")
    st.write(f"**Координаты:** lat={lat:.6f}, lon={lon:.6f}")
    st.write(f"**Ближайшая точка выхода:** ({ex_lon:.6f}, {ex_lat:.6f})")
    st.write(f"**Расстояние до выхода (по прямой):** {dist_to_exit_direct:.2f} км")
    st.write(f"**Извлечённый населённый пункт:** {np_name}")
    st.write(f"**Источник расстояния:** {src}")

    # Сохраняем последние значения для предзаполнения
    st.session_state["last_addr"] = address
    st.session_state["last_date"] = date_obj
