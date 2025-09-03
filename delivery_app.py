# -*- coding: utf-8 -*-
"""
delivery_app.py — Streamlit-калькулятор доставки (розница)
Работает на Render (только веб), без PyQt и .env.

Ключевые фичи:
- Русифицированный календарь (заголовок дней недели и понедельник — первый день, через CSS-оверлей).
- Автоопределение "по рейсу" по дорожной близости к точкам маршрутов (routes.json),
  где маршруты один раз загружаются из "Точки выхода и рейсы.txt" -> routes.json.
- Корректный сброс "15 руб./км" при изменении адреса/даты.
- Расчёт километража от ближайшей точки выхода из Твери по дорогам (ORS), кэширование.
- В пределах адм. границ Твери — километраж не начисляется.
- Новая точка выхода №7: (56.844247, 35.783293).
- Автопуш кэша/маршрутов в GitHub при наличии GIT_* переменных окружения (как раньше).

Ожидания окружения на Render:
- ORS_API_KEY — ключ OpenRouteService (обязателен для дорог).
- (опц.) GIT_REPO, GIT_USER, GIT_TOKEN — для коммит/пуш cache.json и routes.json.
- (опц.) ADMIN_PASS — пароль для админ-режима (по умолчанию 'admin123').
- (опц.) AUTO_GIT_PUSH — '1' (по умолчанию), чтобы пушить после обновления cache/routes.

Файлы в репозитории:
- delivery_app.py (этот файл)
- favicon.png (ваш favicon)
- logo.png (ваш логотип; показываем по центру)
- distance_table.json (опционально; если нет — используем встроенный словарь)
- Точки выхода и рейсы.txt (исходник для одноразовой сборки routes.json)
- routes.json (сгенерированный JSON с маршрутами; будет создан, если отсутствует)

"""

import os
import json
import time
import math
import hashlib
import subprocess
from datetime import date, datetime
from typing import Dict, Any, List, Tuple, Optional

import requests
import streamlit as st

# -----------------------------
# Конфигурация/окружение
# -----------------------------
APP_TITLE_PAGE = "Калькулятор доставки (розница)"
APP_TITLE_MAIN = "Калькулятор стоимости доставки по Твери и области для розничных клиентов"

ADMIN_PASS = os.getenv("ADMIN_PASS", "admin123")
ORS_API_KEY = os.getenv("ORS_API_KEY", "").strip()
AUTO_GIT_PUSH = os.getenv("AUTO_GIT_PUSH", "1").strip() == "1"

# Пути к файлам
CACHE_PATH = "cache.json"
ROUTES_TXT = "Точки выхода и рейсы.txt"   # исходник от пользователя
ROUTES_JSON = "routes.json"               # рабочий JSON с маршрутами
DIST_TABLE_PATH = "distance_table.json"   # опционально; для «табличных» расстояний

# День недели: 0=ПН,...,6=ВС
RU_WEEKDAYS = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
RU_WEEKDAYS_ABBR = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]

# Тарифы
TARIFF_PER_KM_USUAL = 32.0
TARIFF_PER_KM_ROUTE = 15.0

# Базовые цены по размеру (можно при желании расширить)
BASE_PRICES = {
    "маленький": 350.0,
    "средний": 600.0,
    "большой": 900.0,
}

# Точки выхода из Твери (lon, lat). Координаты в формате (lon, lat)!
EXIT_POINTS = [
    (36.055364, 56.795587),  # 1
    (35.871802, 56.808677),  # 2
    (35.804913, 56.831684),  # 3
    (36.020937, 56.850973),  # 4
    (35.797443, 56.882207),  # 5
    (35.932805, 56.902966),  # 6
    (35.783293, 56.844247),  # 7 — НОВАЯ (lon, lat) !! (исправлено)
]

# Небольшая таблица известных расстояний (туда+обратно) по реальным дорогам
# Если есть distance_table.json — подменим этим содержимым
DISTANCE_TABLE_DEFAULT = {
    "Изоплит": 66.456,
    "посёлок Заволжский": 5.930,
    "Радченко": 47.366,
    "Бурашево": 24.328,
    "Мермерины": 24.406,
    "Завидово": 99.622,
    "Калашниково": 151.274,
    "Медное": 49.166,
    "Вараксино": 95.840,
    "Колталово": 51.296,
    "Конаково": 134.000,
}

# -----------------------------
# Утилиты
# -----------------------------

def normalize_place_name(name: str) -> str:
    return (name or "").strip().lower()

def haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def ensure_json(path: str, default: Any) -> Any:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_json(path: str, data: Any) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def debug_info() -> str:
    import platform
    return (
        f"IP сервера Render: (нет прямого доступа)\n"
        f"Версия Streamlit: {st.__version__}\n"
        f"Проверка GIT_TOKEN: {'настроен' if os.getenv('GIT_TOKEN') else 'не задан'}\n"
    )

# -----------------------------
# GitHub sync
# -----------------------------

def git_run(cmd: List[str]) -> Tuple[bool, str]:
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        return True, out.strip()
    except subprocess.CalledProcessError as e:
        return False, f"Command {cmd} failed: {e.output}"

def git_sync(files_to_commit: List[str], message: str) -> str:
    """Коммитит и пушит изменения (если заданы GIT_REPO/GIT_TOKEN/GIT_USER)."""
    repo = os.getenv("GIT_REPO")
    token = os.getenv("GIT_TOKEN")
    user = os.getenv("GIT_USER")
    if not (repo and token and user):
        return "GIT_* переменные не заданы — пропуск push."

    # Настроить origin при необходимости
    ok, out = git_run(["git", "rev-parse", "--is-inside-work-tree"])
    if not ok:
        return f"Git error: {out}"

    # Добавляем remote origin, если его нет/некорректен
    _, remotes = git_run(["git", "remote", "-v"])
    if "origin" not in remotes:
        auth_repo = repo.replace("https://", f"https://{token}@")
        git_run(["git", "remote", "add", "origin", auth_repo])

    # Ветка main, если возможна
    git_run(["git", "fetch", "origin"])
    ok, branches = git_run(["git", "branch", "-a"])
    if ok and "remotes/origin/main" in branches:
        git_run(["git", "checkout", "-B", "main", "origin/main"])
    else:
        # остаёмся на текущей ветке
        pass

    # add/commit/pull/push
    git_run(["git", "add"] + files_to_commit)
    ok, out = git_run(["git", "commit", "-m", message])
    if not ok and "nothing to commit" in out.lower():
        # Нечего коммитить — но попробуем всё равно пушнуть
        pass

    git_run(["git", "pull", "--rebase", "origin", "main"])
    ok, out = git_run(["git", "push", "origin", "HEAD:main"])
    return f"Git push: {'Success' if ok else 'Failed'}\n{out}"

# -----------------------------
# Геокодер (Nominatim)
# -----------------------------

def geocode(address: str) -> Tuple[Optional[float], Optional[float], Optional[str], Dict[str, Any]]:
    """
    Возвращает (lat, lon, display_name, address_details)
    """
    try:
        url = (
            "https://nominatim.openstreetmap.org/search"
            f"?q={requests.utils.quote(address)}"
            "&format=json&limit=1&addressdetails=1"
        )
        headers = {"User-Agent": "flora-delivery-calc/1.0"}
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        js = r.json()
        if not js:
            return None, None, None, {}
        item = js[0]
        lat = float(item["lat"])
        lon = float(item["lon"])
        display = item.get("display_name", address)
        addr = item.get("address", {})
        return lat, lon, display, addr
    except Exception:
        return None, None, None, {}

def extract_settlement(addr_details: Dict[str, Any], display_name: str) -> str:
    """
    Пробуем извлечь населенный пункт из addressdetails, иначе — берём первую часть display_name.
    """
    for key in ("village", "town", "city", "hamlet", "suburb", "neighbourhood"):
        if addr_details.get(key):
            return str(addr_details[key])
    # fallback: до первой запятой
    if display_name:
        return display_name.split(",")[0].strip()
    return ""

def is_within_tver(addr_details: Dict[str, Any]) -> bool:
    """
    Административные границы города Тверь.
    Считаем внутри, если city/town == 'Тверь', либо municipality/ county указывают на городской округ Тверь.
    """
    targets = {"тверь", "город тверь", "tver", "tver’"}
    for key in ("city", "town"):
        v = str(addr_details.get(key, "")).strip().lower()
        if v in targets:
            return True
    # Иногда Nominatim даёт municipality/county/state_district
    for key in ("municipality", "county", "state_district"):
        v = str(addr_details.get(key, "")).lower()
        if "твер" in v and ("город" in v or "городской округ" in v):
            return True
    return False

# -----------------------------
# ORS — расстояние по дорогам
# -----------------------------

def ors_distance_km(lon1: float, lat1: float, lon2: float, lat2: float, timeout=25) -> Optional[float]:
    if not ORS_API_KEY:
        return None
    try:
        url = "https://api.openrouteservice.org/v2/directions/driving-car"
        headers = {"Authorization": ORS_API_KEY, "Content-Type": "application/json"}
        body = {"coordinates": [[lon1, lat1], [lon2, lat2]]}
        r = requests.post(url, headers=headers, json=body, timeout=timeout)
        r.raise_for_status()
        js = r.json()
        dist_m = js["features"][0]["properties"]["segments"][0]["distance"]
        return dist_m / 1000.0
    except Exception:
        return None

# -----------------------------
# Кэш расстояний (settlement -> {distance, exit_point})
# -----------------------------

def load_cache() -> Dict[str, Any]:
    return ensure_json(CACHE_PATH, {})

def save_cache(cache: Dict[str, Any]):
    save_json(CACHE_PATH, cache)
    if AUTO_GIT_PUSH:
        git_sync([CACHE_PATH], "Update cache.json (auto)")

# -----------------------------
# Загрузка distance_table.json (опционально)
# -----------------------------

def load_distance_table() -> Dict[str, float]:
    if os.path.exists(DIST_TABLE_PATH):
        try:
            with open(DIST_TABLE_PATH, "r", encoding="utf-8") as f:
                return {k: float(v) for k, v in json.load(f).items()}
        except Exception:
            pass
    return DISTANCE_TABLE_DEFAULT.copy()

# -----------------------------
# Маршруты: парсер TXT -> routes.json
# -----------------------------

def parse_routes_txt_to_json(txt: str) -> Dict[str, Any]:
    """
    Ожидаемый формат (как в предоставленном файле):
    Пример заголовка:
      1) Рейс КВ_КЛ (Конаково, Клин) по вторникам - точка выхода 56.795587, 36.055364
    Далее идут строки:
      {тип/название} {lat}, {lon}
    Пока не встретится следующий заголовок "... Рейс ..."

    На выходе структура:
    {
      "routes": [
        {
          "name": "КВ_КЛ",
          "days": [1],  # 0=ПН,...,6=ВС
          "exit_point": [lon, lat],   # ВНИМАНИЕ: (lon, lat)
          "points": [[lon, lat], ...] # точки маршрута (в порядке следования)
        },
        ...
      ]
    }
    """
    lines = [l.strip() for l in txt.splitlines()]
    routes: List[Dict[str, Any]] = []

    def ru_days_to_idx(s: str) -> List[int]:
        s = s.lower()
        result = set()
        day_map = {
            "понедельник": 0, "понедельникам": 0, "по понедельникам": 0,
            "вторник": 1, "вторникам": 1, "по вторникам": 1,
            "среда": 2, "средам": 2, "по средам": 2,
            "четверг": 3, "четвергам": 3, "по четвергам": 3,
            "пятница": 4, "пятницам": 4, "по пятницам": 4,
            "суббота": 5, "субботам": 5, "по субботам": 5,
            "воскресенье": 6, "воскресеньям": 6, "по воскресеньям": 6
        }
        # выделяем слова и ищем соответствия
        tokens = [t.strip(",.() ") for t in s.split()]
        for t in tokens:
            if t in day_map:
                result.add(day_map[t])
        # часто встречается форма "по понедельникам и четвергам"
        if "и" in tokens:
            # уже покрыто
            pass
        return sorted(result)

    current: Optional[Dict[str, Any]] = None

    import re
    header_re = re.compile(
        r"^\d+\)\s*Рейс\s+([A-Za-zА-Яа-я0-9_]+).*?по\s+([А-Яа-я ,и]+)\s*-\s*точка выхода\s*([0-9.]+)\s*,\s*([0-9.]+)$"
    )

    coord_re = re.compile(r".*?([0-9]{2}\.[0-9]+)\s*,\s*([0-9]{2}\.[0-9]+)$")

    for raw in lines:
        if not raw:
            continue
        m = header_re.match(raw)
        if m:
            # сохраняем предыдущий
            if current and current.get("points"):
                routes.append(current)
            name = m.group(1).strip()
            days_text = m.group(2).strip()
            lat = float(m.group(3))
            lon = float(m.group(4))
            current = {
                "name": name,
                "days": ru_days_to_idx(days_text),
                "exit_point": [lon, lat],  # (lon, lat)
                "points": []
            }
            continue
        # строки с точками
        m2 = coord_re.match(raw)
        if m2 and current is not None:
            lat = float(m2.group(1))
            lon = float(m2.group(2))
            current["points"].append([lon, lat])  # (lon, lat)
        else:
            # игнорируем произвольные строки
            pass
    # финальный
    if current and current.get("points"):
        routes.append(current)

    return {"routes": routes}

def load_or_build_routes() -> Dict[str, Any]:
    if os.path.exists(ROUTES_JSON):
        try:
            with open(ROUTES_JSON, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # Пытаемся собрать routes.json из TXT
    if os.path.exists(ROUTES_TXT):
        try:
            # Пробуем разные кодировки
            content = None
            for enc in ("utf-8", "utf-8-sig", "cp1251", "utf-16", "utf-16le", "utf-16be"):
                try:
                    with open(ROUTES_TXT, "r", encoding=enc) as f:
                        content = f.read()
                    break
                except Exception:
                    continue
            if not content:
                return {"routes": []}
            data = parse_routes_txt_to_json(content)
            save_json(ROUTES_JSON, data)
            if AUTO_GIT_PUSH:
                git_sync([ROUTES_JSON], "Build routes.json from TXT (auto)")
            return data
        except Exception:
            return {"routes": []}
    # Если ничего нет — пусто
    return {"routes": []}

# -----------------------------
# Поиск «по рейсу» для выбранной даты/адреса
# -----------------------------

def nearest_exit_point(lon: float, lat: float) -> Tuple[Tuple[float, float], float]:
    """
    Возвращает (exit_point (lon,lat), d_straight_km)
    """
    best = None
    best_d = 1e9
    for ep in EXIT_POINTS:
        d = haversine_km(lat, lon, ep[1], ep[0])
        if d < best_d:
            best_d = d
            best = ep
    return best, best_d

def find_route_match_for_day(
    routes: Dict[str, Any],
    weekday_idx: int,
    addr_lon: float,
    addr_lat: float,
    threshold_km: float = 10.0,
    candidates_per_route: int = 1
) -> Tuple[Optional[str], Optional[Tuple[float, float]], Optional[float]]:
    """
    Перебираем маршруты заданного дня, выбираем ближайшую точку маршрута (по прямой),
    затем считаем расстояние по дорогам от адреса до этой точки маршрута (ORS).
    Если расстояние <= threshold_km — считаем, что адрес лежит «по пути» данного рейса.

    Возвращает: (route_name, nearest_route_point(lon,lat), road_km_to_route_point) либо (None, None, None).
    """
    best_name = None
    best_pt = None
    best_km = None

    routes_list = routes.get("routes", [])
    for r in routes_list:
        if weekday_idx not in r.get("days", []):
            continue
        pts = r.get("points") or []
        if not pts:
            continue
        # Находим N ближайших точек (по прямой)
        pts_with_d = []
        for p in pts:
            lon2, lat2 = p
            d = haversine_km(addr_lat, addr_lon, lat2, lon2)
            pts_with_d.append((d, p))
        pts_with_d.sort(key=lambda x: x[0])
        for _, p in pts_with_d[:max(1, candidates_per_route)]:
            lon2, lat2 = p
            road = ors_distance_km(addr_lon, addr_lat, lon2, lat2)
            if road is None:
                # Fallback: умножаем прямую на коэффициент 1.3
                road = haversine_km(addr_lat, addr_lon, lat2, lon2) * 1.3
            if road <= threshold_km:
                # Нашли подходящий рейс
                best_name = r.get("name")
                best_pt = (lon2, lat2)
                best_km = road
                return best_name, best_pt, best_km
    return None, None, None

# -----------------------------
# Расчёт стоимости
# -----------------------------

def calc_cost_for_address(
    address: str,
    cargo_size: str,
    delivery_date: date,
    routes_data: Dict[str, Any],
    threshold_km: float,
    distance_table: Dict[str, float],
    cache: Dict[str, Any],
    use_route_tariff: bool
) -> Dict[str, Any]:
    """
    Главный расчёт. Возвращает словарь с деталями.
    """
    lat, lon, display, addr_details = geocode(address)

    if lat is None or lon is None:
        raise RuntimeError("Не удалось геокодировать адрес. Уточните ввод.")

    # Определяем населённый пункт
    place = extract_settlement(addr_details, display)
    place_norm = normalize_place_name(place)

    # В пределах Твери — без километража
    if is_within_tver(addr_details):
        total = BASE_PRICES[cargo_size]
        return {
            "ok": True,
            "place": place,
            "lat": lat,
            "lon": lon,
            "within_tver": True,
            "exit_point": None,
            "exit_point_km": None,
            "km_roundtrip": 0.0,
            "km_source": "город",
            "base": BASE_PRICES[cargo_size],
            "surcharge": 0.0,
            "tariff_per_km": 0.0,
            "total": total,
            "route_name": None,
            "route_possible": False,
        }

    # Находим ближайшую точку выхода (по прямой)
    exit_pt, d_exit_direct = nearest_exit_point(lon, lat)

    # Ищем расстояние адрес <-> выход по дорогам с кэшем
    # Кэшируем по ключу населённого пункта (как в предыдущей версии)
    km_source = "ors"
    km_roundtrip = None

    if place in cache:
        entry = cache[place]
        km_roundtrip = float(entry.get("distance", 0.0))
        # В кэше хранили distance (туда-обратно) и exit_point
        exit_saved = entry.get("exit_point")
        if isinstance(exit_saved, (list, tuple)) and len(exit_saved) == 2:
            exit_pt = (float(exit_saved[0]), float(exit_saved[1]))
        km_source = "кэш"

    if km_roundtrip is None:
        # Попробуем таблицу (если есть)
        if place in distance_table:
            km_roundtrip = float(distance_table[place])
            km_source = "таблица"

    if km_roundtrip is None:
        # Вычисляем по дорогам (туда и обратно)
        one_way = ors_distance_km(exit_pt[0], exit_pt[1], lon, lat)
        if one_way is None:
            # fallback по прямой * коэффициент
            one_way = haversine_km(exit_pt[1], exit_pt[0], lat, lon) * 1.3
            km_source = "расчёт (прямая*1.3)"
        km_roundtrip = round(one_way * 2.0, 3)
        # Сохраняем в кэш
        cache[place] = {"distance": km_roundtrip, "exit_point": [exit_pt[0], exit_pt[1]]}
        save_cache(cache)

    # Определяем «по рейсу возможно?» для выбранной даты
    weekday_idx = delivery_date.weekday()  # 0=ПН
    route_name, route_pt, road_km_to_route = find_route_match_for_day(
        routes_data, weekday_idx, lon, lat, threshold_km=threshold_km, candidates_per_route=1
    )
    route_possible = route_name is not None

    # Тариф
    tariff = TARIFF_PER_KM_ROUTE if (use_route_tariff and route_possible) else TARIFF_PER_KM_USUAL

    base = BASE_PRICES[cargo_size]
    surcharge = round(km_roundtrip * tariff, 2)
    total = round(base + surcharge, 2)

    return {
        "ok": True,
        "place": place,
        "lat": lat,
        "lon": lon,
        "within_tver": False,
        "exit_point": exit_pt,
        "exit_point_km": d_exit_direct,
        "km_roundtrip": km_roundtrip,
        "km_source": km_source,
        "base": base,
        "surcharge": surcharge,
        "tariff_per_km": tariff,
        "total": total,
        "route_name": route_name,
        "route_possible": route_possible,
        "road_km_to_route": road_km_to_route,
    }

# -----------------------------
# Streamlit UI
# -----------------------------

st.set_page_config(page_title=APP_TITLE_PAGE, page_icon="favicon.png", layout="centered")

# Центровка лого и русификация заголовка дней календаря
st.markdown("""
<style>
/* центрируем логотип */
.block-container { padding-top: 1rem; }
.logo-wrapper { display: flex; justify-content: center; align-items: center; margin: 0.5rem 0 0.5rem 0; }

/* Русификация заголовка дней в календаре Streamlit (Mo Tu We Th Fr Sa Su -> ПН ВТ СР ЧТ ПТ СБ ВС) */
[data-testid="stDateInput"] .st-emotion-cache-1r6slb0 {
    direction: ltr;
}
[data-testid="stDateInput"] .st-emotion-cache-1v0mbdj, 
[data-testid="stDateInput"] .stDateInput {
    /* контейнер календаря */
}
[data-testid="stDateInput"] .stDateInput [data-baseweb="datepicker"] div[aria-label="day of week"] {
    font-weight: 700;
}
[data-testid="stDateInput"] .stDateInput [data-baseweb="datepicker"] div[aria-label="day of week"]:nth-child(1)::after { content: "ПН"; }
[data-testid="stDateInput"] .stDateInput [data-baseweb="datepicker"] div[aria-label="day of week"]:nth-child(2)::after { content: "ВТ"; }
[data-testid="stDateInput"] .stDateInput [data-baseweb="datepicker"] div[aria-label="day of week"]:nth-child(3)::after { content: "СР"; }
[data-testid="stDateInput"] .stDateInput [data-baseweb="datepicker"] div[aria-label="day of week"]:nth-child(4)::after { content: "ЧТ"; }
[data-testid="stDateInput"] .stDateInput [data-baseweb="datepicker"] div[aria-label="day of week"]:nth-child(5)::after { content: "ПТ"; }
[data-testid="stDateInput"] .stDateInput [data-baseweb="datepicker"] div[aria-label="day of week"]:nth-child(6)::after { content: "СБ"; }
[data-testid="stDateInput"] .stDateInput [data-baseweb="datepicker"] div[aria-label="day of week"]:nth-child(7)::after { content: "ВС"; }
/* скрываем англ. подписи дней */
[data-testid="stDateInput"] .stDateInput [data-baseweb="datepicker"] div[aria-label="day of week"] > * { color: transparent; }

/* чуть сужаем инпут */
[data-testid="stDateInput"] input { text-align: left; }

/* Выравнивание разделов */
hr { margin: 0.5rem 0 0.5rem 0; }
</style>
""", unsafe_allow_html=True)

# Логотип по центру
with st.container():
    st.markdown('<div class="logo-wrapper">', unsafe_allow_html=True)
    st.image("logo.png", use_container_width=False, width=160)
    st.markdown('</div>', unsafe_allow_html=True)

st.title(APP_TITLE_MAIN)

# Полезная отладочная шапка (сворачиваемая)
with st.expander("Точки выхода из Твери / Отладка окружения", expanded=False):
    for i, (lon, lat) in enumerate(EXIT_POINTS, start=1):
        st.write(f"Точка {i}: ({lon}, {lat})")
    st.caption(debug_info())

# Инициализация session_state для флагов "по рейсу"
def key_for_inputs(addr: str, d: date) -> str:
    return hashlib.sha1(f"{addr}|{d.isoformat()}".encode("utf-8")).hexdigest()

if "route_confirmed_key" not in st.session_state:
    st.session_state["route_confirmed_key"] = ""
if "route_user_wants" not in st.session_state:
    st.session_state["route_user_wants"] = False

# -----------------------------
# Форма ввода
# -----------------------------
with st.form("calc"):
    # Адрес по умолчанию всегда начинается с "Тверская область, "
    default_address = "Тверская область, "
    addr = st.text_input("Введите адрес доставки", value=default_address, max_chars=200)

    size = st.selectbox("Размер груза", options=list(BASE_PRICES.keys()), index=0)

    # Дата
    d: date = st.date_input("Выберите дату доставки", value=date.today(), format="DD.MM.YYYY")

    # Псевдо-локализация даты (читаемый текст): "02.09.2025 (Вторник)"
    ru_date_text = f"{d.strftime('%d.%m.%Y')} ({RU_WEEKDAYS[d.weekday()]})"
    st.caption(ru_date_text)

    # Админ режим
    st.markdown("**Админ режим**")
    admin_pwd = st.text_input("Админ пароль", type="password", help="Введите для доступа к настройкам")
    admin_mode = (admin_pwd.strip() == ADMIN_PASS)

    # Настройки/экшены админа
    if admin_mode:
        st.success("Админ режим активирован")
        st.markdown("**Настройки рейсов/кэш/гит**")
        threshold_km = st.number_input(
            "Макс. отклонение адреса от графика рейса (по дороге), км",
            min_value=1.0, max_value=50.0, step=0.5, value=10.0, format="%.2f"
        )
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            build_routes = st.form_submit_button("Собрать routes.json из TXT")
        with col_b:
            push_now = st.form_submit_button("Пуш в GitHub (cache/routes)")
        with col_c:
            clear_choice = st.form_submit_button("Сбросить выбор «по рейсу»")
        if clear_choice:
            st.session_state["route_confirmed_key"] = ""
            st.session_state["route_user_wants"] = False
    else:
        threshold_km = 10.0
        build_routes = False
        push_now = False

    # Кнопка расчёта
    calc = st.form_submit_button("Рассчитать")

# Обработчики админ-кнопок вне формы (чтобы не мешать основному расчёту)
routes_data = load_or_build_routes()
if build_routes:
    if os.path.exists(ROUTES_TXT):
        try:
            # читаем TXT и пересобираем
            content = None
            for enc in ("utf-8", "utf-8-sig", "cp1251", "utf-16", "utf-16le", "utf-16be"):
                try:
                    with open(ROUTES_TXT, "r", encoding=enc) as f:
                        content = f.read()
                    break
                except Exception:
                    continue
            if not content:
                st.error("Не удалось прочитать файл 'Точки выхода и рейсы.txt'. Проверьте кодировку/наличие.")
            else:
                new_routes = parse_routes_txt_to_json(content)
                save_json(ROUTES_JSON, new_routes)
                routes_data = new_routes
                st.success(f"routes.json пересобран. Маршрутов: {len(routes_data.get('routes', []))}")
                if AUTO_GIT_PUSH:
                    st.info(git_sync([ROUTES_JSON], "Rebuild routes.json (manual)"))
        except Exception as e:
            st.error(f"Ошибка сборки routes.json: {e}")
    else:
        st.error("Файл 'Точки выхода и рейсы.txt' отсутствует в репозитории.")

if push_now:
    files = []
    if os.path.exists(CACHE_PATH):
        files.append(CACHE_PATH)
    if os.path.exists(ROUTES_JSON):
        files.append(ROUTES_JSON)
    if files:
        st.info(git_sync(files, "Manual push cache/routes"))
    else:
        st.warning("Нет файлов для пуша.")

# Основной расчёт
if calc:
    # Сброс «залипания» флага 15 руб. при смене адреса/даты:
    cur_key = key_for_inputs(addr, d)
    if st.session_state.get("route_confirmed_key", "") != cur_key:
        st.session_state["route_user_wants"] = False
        st.session_state["route_confirmed_key"] = cur_key

    with st.spinner("Считаем..."):
        distance_table = load_distance_table()
        cache = load_cache()

        try:
            # Сначала считаем «без маршрута», чтобы понять возможен ли маршрут:
            prelim = calc_cost_for_address(
                addr, size, d, routes_data, threshold_km, distance_table, cache,
                use_route_tariff=False  # на первом проходе всегда 32, просто чтобы вычислить route_possible
            )
            route_possible = prelim["route_possible"]
            route_name = prelim["route_name"]

            # Если по графику есть попадание в рейс — показываем опцию с подтверждением
            use_route_tariff = False
            if route_possible:
                st.info(
                    f"Обнаружено совпадение с рейсом **{route_name}** ({RU_WEEKDAYS[d.weekday()]}) — "
                    "вы можете доставить вместе с оптовыми заказами по тарифу 15 руб./км."
                )
                # Кнопка подтверждения (двухшаговая)
                c1, c2 = st.columns(2)
                with c1:
                    yes = st.button("Да, применить тариф 15 руб./км")
                with c2:
                    no = st.button("Нет, считать по обычному тарифу")

                if yes:
                    st.session_state["route_user_wants"] = True
                if no:
                    st.session_state["route_user_wants"] = False

                use_route_tariff = bool(st.session_state["route_user_wants"])

            # Повторный расчёт с учётом выбранного тарифа
            result = calc_cost_for_address(
                addr, size, d, routes_data, threshold_km, distance_table, cache,
                use_route_tariff=use_route_tariff
            )

            # Автопуш кэша (если включён)
            if AUTO_GIT_PUSH:
                if os.path.exists(CACHE_PATH):
                    git_sync([CACHE_PATH], "Update cache.json (auto after calc)")

        except RuntimeError as e:
            st.error(str(e))
            result = None
        except requests.exceptions.JSONDecodeError:
            st.error("Ошибка ответа геокодера. Попробуйте уточнить адрес.")
            result = None
        except Exception as e:
            st.error(f"Не удалось выполнить расчёт: {e}")
            result = None

    # Вывод результата
    st.subheader("Результат")
    if result and result.get("ok"):
        st.markdown(f"**Стоимость доставки:** {result['total']:.2f} руб.\n")
        st.write(f"**Дата:** {d.strftime('%d.%m.%Y')} ({RU_WEEKDAYS[d.weekday()]})")

        if result["within_tver"]:
            st.info("**В пределах адм. границ Твери — доплата за километраж не начисляется.**")
        else:
            st.write(f"**Километраж (туда-обратно):** {result['km_roundtrip']:.2f} км")
            st.write(f"**Тариф:** {int(result['tariff_per_km'])} руб./км")
            st.write(f"**Рейс:** {'Да (' + result['route_name'] + ')' if (result['route_name'] and st.session_state.get('route_user_wants')) else ('Есть совпадение' if result['route_possible'] else 'Нет')}")
            st.write(f"**Координаты:** lat={result['lat']:.6f}, lon={result['lon']:.6f}")

            if result.get("exit_point"):
                ep = result["exit_point"]
                st.write(f"**Ближайшая точка выхода:** ({ep[0]:.6f}, {ep[1]:.6f})")
                st.write(f"**Расстояние до выхода (по прямой):** {result['exit_point_km']:.2f} км")

            st.write(f"**Источник расстояния:** {result['km_source']}")

        st.write(f"**Извлечённый населённый пункт:** {result['place'] or '—'}")

    else:
        st.warning("Рассчёт не выполнен.")

# Пояснение логики (сворачиваемое)
with st.expander("О логике определения «по рейсу»", expanded=False):
    st.markdown("""
- Берём выбранный день недели и подгружаем **routes.json**.
- Для каждого рейса этого дня ищем ближайшую к адресу точку маршрута (из списка точек с шагом ~10–15 км).
- Считаем расстояние **по дорогам (ORS)** от адреса до этой ближайшей точки.
- Если расстояние ≤ настраиваемого **порога** (по умолчанию 10 км), считаем что адрес находится «по пути» рейса.
- Тогда показываем опцию «Доставка по рейсу вместе с оптовыми заказами» с подтверждением.
- При подтверждении тариф меняется на **15 руб./км**, иначе остаётся **32 руб./км**.
- Флаг 15 руб./км сбрасывается при изменении адреса или даты.
- Километраж для тарифа — всегда от **ближайшей точки выхода** из Твери до адреса и обратно, **по дорогам (ORS)**,
  с кэшированием. В пределах адм. границ Твери — километраж 0.
""")
