# -*- coding: utf-8 -*-
"""
Калькулятор доставки (розница) — Streamlit
Автоопределение "по рейсу" выполняется по ОРС-маршрутам (по дорогам),
кэшируется в cache.json и при необходимости пушится в GitHub (если заданы GIT_*)
Точки выхода из Твери учитываются (расчёт ведётся от ближайшей точки выхода).
Русифицированный календарь — отображается как грид (визуально), ввод даты через st.date_input.
"""

import os
import json
import math
import time
import hashlib
import datetime as dt
from pathlib import Path
from typing import Dict, Tuple, List, Optional

import requests
import streamlit as st
from PIL import Image

# --------------------------- Константы/настройки --------------------------- #

APP_TITLE_TAB = "Калькулятор доставки (розница)"
APP_TITLE_PAGE = "Калькулятор стоимости доставки по Твери и области для розничных клиентов"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")  # можно задать в Render
ORS_API_KEY = os.getenv("ORS_API_KEY", "")
GIT_REPO = os.getenv("GIT_REPO", "")
GIT_USER = os.getenv("GIT_USER", "")
GIT_TOKEN = os.getenv("GIT_TOKEN", "")

# Файлы статических ресурсов (логотип/иконка) — пути относительно корня проекта
FAVICON_PATH = "favicon.png"     # иконка, которую вы загрузили в репо
LOGO_PATH = "logo.png"           # ваш логотип в репо

CACHE_PATH = Path("cache.json")

# Точки выхода (формат lon, lat). В логах у вас пары были (lon, lat), сохраняю именно так.
EXIT_POINTS: List[Tuple[float, float]] = [
    (36.055364, 56.795587),  # 1
    (35.871802, 56.808677),  # 2
    (35.804913, 56.831684),  # 3
    (36.020937, 56.850973),  # 4
    (35.797443, 56.882207),  # 5
    (35.932805, 56.902966),  # 6
    # Точка 7 (пользователь прислал в виде (56.831684, 35.804913), но для единообразия меняем на (lon, lat))
    (35.804913, 56.831684),  # 7
]

# Тарифы
TARIFF_DEFAULT = 32
TARIFF_WHOLESALE_ROUTE = 15

# Базовые цены (пример — как раньше)
BASE_PRICE_SMALL = 350
BASE_PRICE_MEDIUM = 700
BASE_PRICE_LARGE = 1000

# Сопоставление рейсов по дням недели и названиям
# День недели: 0-ПН ... 6-ВС
ROUTE_GROUPS: Dict[int, Dict[str, List[str]]] = {
    0: {  # Понедельник
        "РЖ_СЦ_ЗБ_ЗД_ЖК_ТЦ_ВЛ_НЛ_ОЛ_ВЛ": [
            "Великие Луки", "Жарковский", "Торопец", "Западная Двина",
            "Нелидово", "Оленино", "Зубцов", "Ржев", "Старица"
        ],
        "КШ_КЗ_КГ": ["Кашин", "Калязин", "Кесова Гора"],
    },
    1: {  # Вторник
        "КВ_КЛ": ["Конаково", "Редкино", "Мокшино", "Новозавидовский", "Клин"],
        "ЛШ_ШХ_ВК_РЗ": ["Руза", "Волоколамск", "Шаховская", "Лотошино"],
    },
    2: {  # Среда
        "КМ_ДБ": ["Дубна", "Кимры"],
        "РЖ_СЦ_ЗБ_ЗД_ЖК_ТЦ_ВЛ_НЛ_ОЛ_ВЛ_часть": ["Старица", "Ржев", "Зубцов"],
        "СЛЖ_ОСТ_КУВ": ["Кувшиново", "Осташков", "Селижарово", "Пено"],
    },
    3: {  # Четверг
        "РЖ_СЦ_ЗБ_ЗД_ЖК_ТЦ_ВЛ_НЛ_ОЛ_ВЛ_часть": ["Великие Луки", "Жарковский", "Торопец", "Западная Двина", "Нелидово", "Оленино"],
        "БГ_only": ["Бологое"],
    },
    4: {  # Пятница
        "ТО_СП_ВВ_БГ_УД": ["Удомля", "Вышний Волочек", "Спирово", "Торжок", "Лихославль"],
        "РШ_МХ_ЛС_СД": ["Лесное", "Максатиха", "Рамешки", "Сандово", "Весьегонск", "Красный Холм", "Сонково", "Бежецк"],
    },
    5: {},  # Суббота
    6: {},  # Воскресенье
}

# --------------------------- Утилиты --------------------------- #

def load_cache() -> Dict:
    if CACHE_PATH.exists():
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(data: Dict) -> None:
    tmp = CACHE_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(CACHE_PATH)

def git_sync_cache():
    """Автопуш cache.json, если настроены GIT_* переменные окружения."""
    if not (GIT_REPO and GIT_USER and GIT_TOKEN):
        return "Git: переменные окружения не заданы — пропуск"
    try:
        # Настроить git (одноразово)
        os.system('git config user.email "{}@users.noreply.github.com"'.format(GIT_USER))
        os.system('git config user.name "{}"'.format(GIT_USER))
        # Добавить origin, если его нет
        os.system("git remote remove origin > /dev/null 2>&1 || true")
        os.system(f"git remote add origin {GIT_REPO}")
        # Зафиксировать изменения
        os.system("git add cache.json")
        os.system('git commit -m "Update cache.json [auto]" || true')
        # Обновиться и пушнуть
        os.system("git fetch origin")
        # Создать/обновить ветку main
        os.system("git branch -M main")
        # Попытаться подтянуть
        os.system("git pull --rebase origin main || true")
        # Пуш
        code = os.system("git push origin main")
        return "Git push: Success" if code == 0 else "Git push: Failed"
    except Exception as e:
        return f"Git push error: {e}"

def haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    p = math.radians
    dlat = p(lat2 - lat1)
    dlon = p(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(p(lat1)) * math.cos(p(lat2)) * math.sin(dlon/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def nearest_exit_point(lat: float, lon: float) -> Tuple[Tuple[float,float], float]:
    # EXIT_POINTS заданы в (lon, lat) — конвертируем при расчёте
    best = None
    best_d = 1e9
    for (xlon, xlat) in EXIT_POINTS:
        d = haversine_km(lat, lon, xlat, xlon)
        if d < best_d:
            best_d = d
            best = (xlon, xlat)
    return best, best_d

def yandex_geocode(query: str) -> Optional[Tuple[float,float,str]]:
    """Простой геокод через Nominatim как fallback, чтобы не падать на JSONDecodeError."""
    # Если есть YA_API_KEY — можно добавить Yandex, но оставим Nominatim, т.к. без ключа.
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": query, "format": "json", "addressdetails": 1, "accept-language": "ru"}
        r = requests.get(url, params=params, timeout=15, headers={"User-Agent": "delivery-calc/1.0"})
        r.raise_for_status()
        js = r.json()
        if not js:
            return None
        item = js[0]
        lat = float(item["lat"])
        lon = float(item["lon"])
        display = item.get("display_name", query)
        return lat, lon, display
    except Exception:
        return None

def inside_tver_city(lat: float, lon: float) -> bool:
    """Пытаемся определить, находится ли точка в адм. границах Твери — через reverse+адрес."""
    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {"lat": lat, "lon": lon, "format": "json", "zoom": 12, "addressdetails": 1, "accept-language": "ru"}
        r = requests.get(url, params=params, timeout=15, headers={"User-Agent": "delivery-calc/1.0"})
        r.raise_for_status()
        js = r.json()
        addr = js.get("address", {})
        # Любое поле, в котором встречается "Тверь"
        for key in ("city", "town", "municipality", "county"):
            val = addr.get(key, "")
            if isinstance(val, str) and "Твер" in val:
                return True
        display = js.get("display_name", "")
        if "Твер" in display:
            return True
    except Exception:
        pass
    return False

def ors_route(coords: List[Tuple[float,float]]) -> Optional[Dict]:
    """Маршрут ORS: coords в формате [(lon,lat), ...]. Возвращает geometry+distance (м)."""
    if not ORS_API_KEY:
        return None
    try:
        url = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
        headers = {"Authorization": ORS_API_KEY, "Content-Type": "application/json"}
        body = {"coordinates": coords, "instructions": False}
        r = requests.post(url, headers=headers, json=body, timeout=30)
        r.raise_for_status()
        js = r.json()
        feat = js["features"][0]
        dist_m = feat["properties"]["summary"]["distance"]
        geom = feat["geometry"]  # LineString
        return {"distance_m": dist_m, "geometry": geom}
    except Exception:
        return None

def ors_distance_between(a: Tuple[float,float], b: Tuple[float,float]) -> Optional[float]:
    """Короткий маршрут по дорогам между двумя точками (lon,lat) → км."""
    route = ors_route([a, b])
    if not route:
        return None
    return route["distance_m"] / 1000.0

def build_route_polyline_for_group(group_cities: List[str], cache: Dict) -> Optional[List[Tuple[float,float]]]:
    """
    Строим опорный полилин рейса: Тверь (ближайшая точка выхода) → города по порядку.
    Геокодируем города (кэшируем). Возвращаем список координат (lon,lat).
    """
    # Координаты "Тверь центр" для старта (приблизительно), но выходим из ближ. точки выхода.
    tver_center = (35.9077, 56.8584)  # lon,lat
    # Сначала точки выхода — берём условно точку 1 как "вход в сеть"
    start = EXIT_POINTS[0]

    poly: List[Tuple[float,float]] = [start]
    for name in group_cities:
        key = f"GEOCITY::{name}"
        if key in cache:
            lon, lat = cache[key]["lon"], cache[key]["lat"]
        else:
            g = yandex_geocode(f"Тверская область, {name}") or yandex_geocode(name)
            if not g:
                continue
            lat, lon, _ = g
            cache[key] = {"lon": lon, "lat": lat}
        poly.append((lon, lat))
    # Вернёмся в Тверь (стартовую) для типичности кольца
    poly.append(start)
    return poly if len(poly) >= 3 else None

def ensure_route_geometries_for_day(dow: int, cache: Dict) -> Dict[str, Dict]:
    """
    Для указанного дня недели — готовим геометрии маршрутов ORS и кэшируем их в cache.json.
    Возвращает словарь: {route_name: {cities:[], coords:[(lon,lat)], distance_km:float, geometry:GeoJSON}}
    """
    routes = {}
    groups = ROUTE_GROUPS.get(dow, {})
    for route_name, cities in groups.items():
        cache_key = f"ROUTE::{dow}::{route_name}"
        if cache_key in cache and "geometry" in cache[cache_key]:
            routes[route_name] = cache[cache_key]
            continue
        coords = build_route_polyline_for_group(cities, cache)
        if not coords:
            continue
        res = ors_route(coords)
        if not res:
            continue
        distance_km = res["distance_m"] / 1000.0
        routes[route_name] = {
            "cities": cities,
            "coords": coords,
            "distance_km": distance_km,
            "geometry": res["geometry"],
        }
        cache[cache_key] = routes[route_name]
    return routes

def road_deviation_to_route(addr_lonlat: Tuple[float,float], route_coords: List[Tuple[float,float]]) -> Optional[float]:
    """
    Приближённая "по дороге" дистанция от адреса до маршрута:
    берём 8 ближайших вершин полилинии по прямой и считаем по ORS
    расстояние до них, возвращаем минимум (км).
    """
    if not ORS_API_KEY:
        return None
    ax, ay = addr_lonlat
    # Отсортируем вершины маршрута по прямой
    pts = sorted(route_coords, key=lambda p: haversine_km(ay, ax, p[1], p[0]))
    candidates = pts[:8] if len(pts) > 8 else pts
    best = None
    for p in candidates:
        d = ors_distance_between((ax, ay), p)
        if d is None:
            continue
        if (best is None) or (d < best):
            best = d
    return best

def settlement_from_display_name(display: str) -> str:
    """
    Достаём короткое название населённого пункта из display_name Nominatim.
    Берём первое осмысленное слово до запятой, без «деревня/посёлок» и т.п.
    """
    if not display:
        return ""
    first = display.split(",")[0].strip()
    # Уберём типы
    garbage = ["деревня", "посёлок", "поселок", "село", "город", "рабочий посёлок", "станция", "мкр"]
    low = first.lower()
    for g in garbage:
        if low.startswith(g + " "):
            first = first[len(g):].strip(" ,")
            break
    return first

def base_price_by_size(size: str) -> int:
    size = (size or "").lower()
    if "мален" in size:
        return BASE_PRICE_SMALL
    if "сред" in size:
        return BASE_PRICE_MEDIUM
    return BASE_PRICE_LARGE

# --------------------------- UI и логика --------------------------- #

st.set_page_config(
    page_title=APP_TITLE_TAB,
    page_icon=FAVICON_PATH if Path(FAVICON_PATH).exists() else None,
    layout="centered",
)

# ЛОГОТИП по центру
if Path(LOGO_PATH).exists():
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.image(Image.open(LOGO_PATH), use_column_width=True)

st.title(APP_TITLE_PAGE)

# Инициализация session_state
for key, default in {
    "admin": False,
    "apply_wholesale_route": False,
    "last_address": "",
    "last_date": None,
    "confirm_modal_open": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

cache = load_cache()

# ----- Вводные поля -----
address = st.text_input("Введите адрес доставки", placeholder="Например: 'Тверь, ул. Советская, 10' или 'Тверская область, Вараксино'")
size = st.selectbox("Размер груза", ["маленький", "средний", "большой"])

# Руссифицированный ввод даты (format) и отдельный «визуальный календарь»
delivery_date = st.date_input("Выберите дату доставки", format="DD.MM.YYYY")
# Визуальный календарь (грид)
def ru_calendar_grid(d: dt.date):
    import calendar
    # Русские названия
    month_names = ["Январь","Февраль","Март","Апрель","Май","Июнь","Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"]
    st.markdown(f"**{month_names[d.month-1]} {d.year}**")
    calendar.setfirstweekday(calendar.MONDAY)
    md = calendar.monthcalendar(d.year, d.month)
    st.write("ПН  ВТ  СР  ЧТ  ПТ  СБ  ВС")
    # Выводим грид числами
    out = []
    for wk in md:
        row = []
        for x in wk:
            row.append(f"{x:>2}" if x != 0 else "  ")
        out.append("  ".join(row))
    st.code("\n".join(out), language="text")

ru_calendar_grid(delivery_date)

# ----- Админ-режим -----
with st.expander("Админ режим", expanded=False):
    pwd = st.text_input("Админ пароль", type="password")
    if pwd == ADMIN_PASSWORD:
        st.session_state.admin = True
        st.success("Админ режим активирован")
    else:
        if pwd:
            st.warning("Неверный админ пароль")

    if st.session_state.admin:
        st.write("**Настройки рейсов/кэш/гит**")
        route_tol_km = st.number_input(
            "Макс. отклонение адреса от графика рейса (по дороге), км",
            min_value=0.0, max_value=50.0, value=float(cache.get("ROUTE_TOL_KM", 10.0)), step=0.5
        )
        if st.button("Сохранить порог отклонения"):
            cache["ROUTE_TOL_KM"] = route_tol_km
            save_cache(cache)
            st.success("Порог отклонения сохранён")

        if st.button("Сбросить кэш маршрутов (только геометрии рейсов)"):
            # Удалим ключи ROUTE::*
            to_del = [k for k in cache.keys() if k.startswith("ROUTE::")]
            for k in to_del:
                cache.pop(k, None)
            save_cache(cache)
            st.success("Геометрии рейсов очищены")

        if st.button("Отправить cache.json в GitHub сейчас"):
            res = git_sync_cache()
            st.info(res)

# При смене адреса/даты — сбрасываем флаг «по рейсу»
addr_changed = address.strip() != st.session_state.last_address
date_changed = delivery_date != st.session_state.last_date
if addr_changed or date_changed:
    st.session_state.apply_wholesale_route = False

# Кнопка расчёта
if st.button("Рассчитать"):
    if not address.strip():
        st.warning("Введите адрес доставки.")
        st.stop()

    g = yandex_geocode(address.strip())
    if not g:
        st.error("Не удалось геокодировать адрес. Уточните формулировку.")
        st.stop()

    lat, lon, display_name = g
    short_name = settlement_from_display_name(display_name)

    # Границы города Твери — если внутри, километраж не считается
    in_tver = inside_tver_city(lat, lon)

    # Ближайшая точка выхода
    exit_ll, exit_dist_straight = nearest_exit_point(lat, lon)  # exit_ll: (lon,lat)
    exit_lonlat = exit_ll

    # Километраж туда-обратно по дорогам (через ORS)
    distance_km = 0.0
    price_km = 0
    tariff = TARIFF_DEFAULT
    route_name_used = "Нет"
    note_route_offer = False
    route_offer_name = None
    route_offer_dev_km = None

    if not in_tver:
        # Сначала расстояние от ближайшей точки выхода до адреса — по дорогам
        with st.spinner("Считаем расстояние по дорогам…"):
            road_km_oneway = ors_distance_between(exit_lonlat, (lon, lat))
        if road_km_oneway is None:
            # Fallback: по прямой (нежелательно, но чтобы не падать)
            road_km_oneway = haversine_km(exit_lonlat[1], exit_lonlat[0], lat, lon)
        distance_km = round(road_km_oneway * 2, 3)

        # Подготовка рейсов на выбранный день
        dow = delivery_date.weekday()  # 0-ПН…6-ВС
        tol_km = float(cache.get("ROUTE_TOL_KM", 10.0))

        if ORS_API_KEY and tol_km > 0 and (dow in ROUTE_GROUPS) and ROUTE_GROUPS[dow]:
            with st.spinner("Строим график рейсов на выбранный день…"):
                routes = ensure_route_geometries_for_day(dow, cache)
                save_cache(cache)  # сохранить возможные новые геокодировки/маршруты

            # Проверим близость адреса к какому-либо маршруту (по дороге)
            best_dev = None
            best_route = None
            for rname, rinfo in routes.items():
                dev = road_deviation_to_route((lon, lat), rinfo["coords"])
                if dev is None:
                    continue
                if (best_dev is None) or (dev < best_dev):
                    best_dev = dev
                    best_route = rname

            if best_route is not None and best_dev is not None and best_dev <= tol_km:
                # Адрес допустимо в "коридоре" рейса — предлагаем опцию
                note_route_offer = True
                route_offer_name = best_route
                route_offer_dev_km = round(best_dev, 2)

    # Чекбокс «по рейсу»
    if note_route_offer:
        st.info(f"Адрес находится в «коридоре» рейса **{route_offer_name}** (отклонение по дороге ≈ {route_offer_dev_km} км).")
        # Подтверждение
        colA, colB = st.columns([1,1])
        with colA:
            choose = st.checkbox("Доставка по рейсу вместе с оптовыми заказами", value=st.session_state.apply_wholesale_route, key="cb_route")
        if choose and not st.session_state.apply_wholesale_route:
            # запросим подтверждение
            st.warning("Вы уверены, что данный заказ можно доставить по рейсу вместе с оптовыми заказами?")
            cc1, cc2 = st.columns([1,1])
            with cc1:
                if st.button("Да"):
                    st.session_state.apply_wholesale_route = True
            with cc2:
                if st.button("Нет"):
                    st.session_state.apply_wholesale_route = False

        if st.session_state.apply_wholesale_route:
            tariff = TARIFF_WHOLESALE_ROUTE
            route_name_used = route_offer_name
        else:
            tariff = TARIFF_DEFAULT
            route_name_used = "Нет"

    # Стоимость
    base = base_price_by_size(size)
    km_price = 0.0 if in_tver else distance_km * tariff
    total = base + km_price

    # Округление как в примерах (до сотен? у вас в примерах — по обычным правилам)
    total_rounded = round(total / 100) * 100 if total >= 1000 else round(total / 50) * 50
    # На всякий случай сделаем как раньше — в примерах фигурировали суммы .0; оставим total_rounded
    total_show = float(total_rounded)

    # Вывод результата
    st.subheader("Результат")
    st.write(f"**Стоимость доставки:** {total_show:.0f} руб.")
    st.write(f"**Дата:** {delivery_date.strftime('%d.%m.%Y')} ({['Понедельник','Вторник','Среда','Четверг','Пятница','Суббота','Воскресенье'][delivery_date.weekday()]})")

    if not in_tver:
        st.write(f"**Километраж:** {distance_km:.2f} км")
        st.write(f"**Тариф:** {tariff} руб./км")
        st.write(f"**Рейс:** {route_name_used}")
    else:
        st.write("**В пределах адм. границ Твери — доплата за километраж не начисляется.**")

    st.write(f"**Координаты:** lat={lat:.6f}, lon={lon:.6f}")
    st.write(f"**Ближайшая точка выхода:** ({exit_lonlat[0]:.6f}, {exit_lonlat[1]:.6f})")
    st.write(f"**Расстояние до выхода (по прямой):** {haversine_km(lat, lon, exit_lonlat[1], exit_lonlat[0]):.2f} км")
    st.write(f"**Извлечённый населённый пункт:** {short_name or '—'}")

    # После успешного расчёта — запомним адрес/дату и запушим cache.json (если что-то новое добавили)
    st.session_state.last_address = address.strip()
    st.session_state.last_date = delivery_date
    save_cache(cache)
    git_msg = git_sync_cache()
    st.caption(git_msg)

# Пояснения внизу
with st.expander("О логике определения «по рейсу»"):
    st.markdown(
        """
- Проверяем день недели и строим геометрию рейсов для этого дня (по дорогам, ORS).
- Вычисляем «отклонение по дороге» от адреса до ближайшей точки маршрута (набор ближайших вершин, считаем ORS-расстояние).
- Если отклонение ≤ настраиваемого порога (по умолчанию 10 км), появляется опция «Доставка по рейсу вместе с оптовыми заказами».
- При выборе опции и подтверждении — тариф 15 руб./км, иначе 32 руб./км.
- При изменении **адреса** или **даты** флаг «по рейсу» автоматически **сбрасывается**.
- Расчёт километража всегда ведётся **от ближайшей точки выхода из Твери**.
        """
    )
