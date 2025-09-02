# -*- coding: utf-8 -*-
import math
import os
import json
import asyncio
import subprocess
from datetime import date, datetime

import requests
import aiohttp
import streamlit as st

# ====== i18n (только подписи) ======
try:
    from streamlit_i18n import init, _
    init("ru")
except Exception:
    def _(x): return x

# ====== Параметры страницы / бренд ======
st.set_page_config(page_title="Калькулятор доставки (розница)",
                   page_icon="favicon.png",
                   layout="centered")

# Центрируем логотип
c1, c2, c3 = st.columns([1, 2, 1])
with c2:
    try:
        st.image("logo.png", use_container_width=False, width=520)
    except Exception:
        pass

st.title(_("Калькулятор стоимости доставки по Твери и области для розничных клиентов"))
st.caption(_("Введите адрес доставки, выберите размер груза и дату доставки."))

# ====== Константы и справочники ======

# Размеры груза (цена в городе/база)
cargo_prices = {
    "маленький": 500,
    "средний": 800,
    "большой": 1200
}

# Выходы из Твери (lon, lat)
_exit_raw = [
    (36.055364, 56.795587),  # 1
    (35.871802, 56.808677),  # 2
    (35.804913, 56.831684),  # 3
    (36.020937, 56.850973),  # 4
    (35.797443, 56.882207),  # 5
    (35.932805, 56.902966),  # 6
]
# Новая Точка 7 была передана как (56.831684, 35.804913) — это (lat, lon).
# Нормализуем к (lon, lat) и добавим только если её ещё нет в списке:
p7_lat, p7_lon = 56.831684, 35.804913
p7 = (p7_lon, p7_lat)
if p7 not in _exit_raw and (p7_lat, p7_lon) not in _exit_raw:
    _exit_raw.append(p7)

exit_points = tuple(_exit_raw)

# Таблица ориентировочных расстояний и координат ключевых НП (lon, lat)
distance_table = {
    'Клин': {'distance': 140, 'exit_point': (36.055364, 56.795587), 'coords': (36.728611, 56.339167)},
    'Редкино': {'distance': 60, 'exit_point': (36.055364, 56.795587), 'coords': (36.013333, 56.723333)},
    'Мокшино': {'distance': 76, 'exit_point': (36.055364, 56.795587), 'coords': (36.106667, 56.616667)},
    'Новозавидовский': {'distance': 88, 'exit_point': (36.055364, 56.795587), 'coords': (36.050000, 56.533333)},
    'Конаково': {'distance': 134, 'exit_point': (36.055364, 56.795587), 'coords': (36.775000, 56.708333)},
    'Волоколамск': {'distance': 218, 'exit_point': (35.871802, 56.808677), 'coords': (35.957222, 56.035278)},
    'Лотошино': {'distance': 148, 'exit_point': (35.871802, 56.808677), 'coords': (35.506111, 56.047222)},
    'Руза': {'distance': 320, 'exit_point': (35.871802, 56.808677), 'coords': (36.227778, 55.702778)},
    'Шаховская': {'distance': 204, 'exit_point': (35.871802, 56.808677), 'coords': (35.879722, 56.043611)},
    'Великие Луки': {'distance': 740, 'exit_point': (35.804913, 56.831684), 'coords': (30.609167, 56.340278)},
    'Жарковский': {'distance': 640, 'exit_point': (35.804913, 56.831684), 'coords': (32.950833, 55.816667)},
    'Западная Двина': {'distance': 530, 'exit_point': (35.804913, 56.831684), 'coords': (32.055000, 56.250278)},
    'Зубцов': {'distance': 238, 'exit_point': (35.804913, 56.831684), 'coords': (34.583333, 56.183333)},
    'Нелидово': {'distance': 444, 'exit_point': (35.804913, 56.831684), 'coords': (32.775278, 56.225278)},
    'Оленино': {'distance': 350, 'exit_point': (35.804913, 56.831684), 'coords': (33.483333, 56.183333)},
    'Ржев': {'distance': 230, 'exit_point': (35.804913, 56.831684), 'coords': (34.327778, 56.261111)},
    'Старица': {'distance': 132, 'exit_point': (35.804913, 56.831684), 'coords': (34.935000, 56.505278)},
    'Торопец': {'distance': 620, 'exit_point': (35.804913, 56.831684), 'coords': (31.633333, 56.500000)},
    'Дубна': {'distance': 230, 'exit_point': (36.020937, 56.850973), 'coords': (37.166667, 56.733333)},
    'Кимры': {'distance': 186, 'exit_point': (36.020937, 56.850973), 'coords': (37.358333, 56.866667)},
    'Бологое': {'distance': 356, 'exit_point': (35.797443, 56.882207), 'coords': (34.083333, 57.883333)},
    'Вышний Волочек': {'distance': 242, 'exit_point': (35.797443, 56.882207), 'coords': (34.566667, 57.583333)},
    'Лихославль': {'distance': 88, 'exit_point': (35.797443, 56.882207), 'coords': (36.083333, 57.116667)},
    'Спирово': {'distance': 206, 'exit_point': (35.797443, 56.882207), 'coords': (36.416667, 57.416667)},
    'Торжок': {'distance': 122, 'exit_point': (35.797443, 56.882207), 'coords': (34.966667, 57.033333)},
    'Удомля': {'distance': 346, 'exit_point': (35.797443, 56.882207), 'coords': (35.016667, 57.866667)},
    'Сонково': {'distance': 306, 'exit_point': (35.932805, 56.902966), 'coords': (37.150000, 57.783333)},
    'Сандово': {'distance': 474, 'exit_point': (35.932805, 56.902966), 'coords': (36.983333, 58.450000)},
    'Лесное': {'distance': 382, 'exit_point': (35.932805, 56.902966), 'coords': (37.150000, 58.166667)},
    'Максатиха': {'distance': 232, 'exit_point': (35.932805, 56.902966), 'coords': (36.566667, 57.916667)},
    'Рамешки': {'distance': 118, 'exit_point': (35.932805, 56.902966), 'coords': (36.916667, 57.350000)},
    'Весьегонск': {'distance': 486, 'exit_point': (35.932805, 56.902966), 'coords': (37.266667, 58.733333)},
    'Калязин': {'distance': 386, 'exit_point': (35.932805, 56.902966), 'coords': (38.150000, 57.233333)},
    'Кесова Гора': {'distance': 414, 'exit_point': (35.932805, 56.902966), 'coords': (37.616667, 57.883333)},
    'Красный Холм': {'distance': 330, 'exit_point': (35.932805, 56.902966), 'coords': (37.116667, 58.066667)},
    'Бежецк': {'distance': 244, 'exit_point': (35.932805, 56.902966), 'coords': (36.683333, 57.783333)},
    'Кашин': {'distance': 286, 'exit_point': (35.932805, 56.902966), 'coords': (37.616667, 57.300000)},
    'Кувшиново': {'distance': 216, 'exit_point': (35.797443, 56.882207), 'coords': (34.750000, 57.366667)},
    'Осташков': {'distance': 370, 'exit_point': (35.797443, 56.882207), 'coords': (33.116667, 57.150000)},
    'Селижарово': {'distance': 430, 'exit_point': (35.797443, 56.882207), 'coords': (33.466667, 56.850000)},
    'Пено': {'distance': 400, 'exit_point': (35.797443, 56.882207), 'coords': (32.716667, 56.916667)}
}

# Маршрутные коды и их «коридоры» (используем эти коды в UI и логике)
ROUTE_DEFS = {
    # Вторник
    "КВ_КЛ": {
        "weekdays": [1],
        "stops": ["Редкино", "Новозавидовский", "Мокшино", "Конаково", "Клин"]
    },
    "ЛШ_ШХ_ВК_РЗ": {
        "weekdays": [1],
        "stops": ["Руза", "Волоколамск", "Шаховская", "Лотошино"]
    },

    # Понедельник (длинная «Ржевская/Лукинская» нитка)
    "РЖ_СЦ_ЗБ_ЗД_ЖК_ТЦ_ВЛ_НЛ_ОЛ_ВЛ": {
        "weekdays": [0],
        "stops": ["Старица", "Ржев", "Зубцов", "Оленино", "Нелидово", "Западная Двина",
                  "Торопец", "Жарковский", "Великие Луки"]
    },
    "КШ_КЗ_КГ": {
        "weekdays": [0],
        "stops": ["Кашин", "Калязин", "Кесова Гора"]
    },

    # Среда
    "КМ_ДБ": {
        "weekdays": [2],
        "stops": ["Дубна", "Кимры"]
    },
    "СРЗ": {
        "weekdays": [2],
        "stops": ["Старица", "Ржев", "Зубцов"]
    },
    "СЛЖ_ОСТ_КУВ": {
        "weekdays": [2],
        "stops": ["Кувшиново", "Осташков", "Селижарово", "Пено"]
    },

    # Четверг
    "РЖ_СЦ_ЗБ_ЗД_ЖК_ТЦ_ВЛ_НЛ_ОЛ": {
        "weekdays": [3],
        "stops": ["Старица", "Ржев", "Зубцов", "Оленино", "Нелидово", "Западная Двина",
                  "Торопец", "Жарковский"]  # до Оленино/Нелидово — усечённая версия
    },
    "БОЛОГОЕ": {
        "weekdays": [3],
        "stops": ["Бологое"]
    },

    # Пятница
    "ТО_СП_ВВ_БГ_УД": {
        "weekdays": [4],
        "stops": ["Лихославль", "Торжок", "Спирово", "Вышний Волочек", "Бологое", "Удомля"]
    },
    "РШ_МХ_ЛС_СД": {
        "weekdays": [4],
        "stops": ["Лесное", "Максатиха", "Рамешки", "Сандово"]
    },
    "БК_СН_КХ_ВГ": {
        "weekdays": [4],
        "stops": ["Весьегонск", "Красный Холм", "Сонково", "Бежецк"]
    },
}

# ====== Утилиты ======

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1r = math.radians(lat1); lat2r = math.radians(lat2)
    dlat = lat2r - lat1r
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(lat1r)*math.cos(lat2r)*math.sin(dlon/2)**2
    return 2*R*math.asin(math.sqrt(a))

def lonlat_to_xy_km(lon, lat, lon0=36.0, lat0=56.86):
    # Плоская аппроксимация около Твери
    x = (lon - lon0) * 111.320 * math.cos(math.radians(lat0))
    y = (lat - lat0) * 110.574
    return x, y

def point_segment_distance_km(px, py, ax, ay, bx, by):
    # Расстояние от точки P до отрезка AB в km (в уже-проекционных координатах)
    abx, aby = bx - ax, by - ay
    apx, apy = px - ax, py - ay
    ab2 = abx*abx + aby*aby
    if ab2 == 0:
        dx, dy = px - ax, py - ay
        return math.hypot(dx, dy)
    t = max(0.0, min(1.0, (apx*abx + apy*aby) / ab2))
    cx, cy = ax + t*abx, ay + t*aby
    return math.hypot(px - cx, py - cy)

# ====== Кэш ======

CACHE_FILE = "cache.json"

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache: dict):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.warning(f"Ошибка записи {CACHE_FILE}: {e}")
        return

    # === GitHub sync (устойчивая) ===
    try:
        if not os.path.exists(".git"):
            subprocess.run(["git", "init"], check=True, capture_output=True, text=True)

        git_repo = os.environ.get("GIT_REPO", "").strip()
        git_user = os.environ.get("GIT_USER", "render-bot")
        git_token = os.environ.get("GIT_TOKEN", "").strip()

        if git_repo and git_token and git_repo.startswith("https://"):
            auth_repo = git_repo.replace("https://", f"https://{git_token}@")
        else:
            auth_repo = None

        # user config
        subprocess.run(["git", "config", "--global", "user.name", git_user], check=True,
                       capture_output=True, text=True)
        subprocess.run(["git", "config", "--global", "user.email", f"{git_user}@example.com"], check=True,
                       capture_output=True, text=True)

        # remote origin
        remotes = subprocess.run(["git", "remote", "-v"], capture_output=True, text=True)
        if "origin" not in remotes.stdout and auth_repo:
            subprocess.run(["git", "remote", "add", "origin", auth_repo],
                           check=True, capture_output=True, text=True)

        # ensure main branch exists
        subprocess.run(["git", "checkout", "-B", "main"], check=True, capture_output=True, text=True)

        # add/commit
        subprocess.run(["git", "add", CACHE_FILE], check=True, capture_output=True, text=True)
        subprocess.run(["git", "commit", "-m", "Update cache.json"], check=False, capture_output=True, text=True)

        # pull --rebase (если есть origin)
        if auth_repo:
            subprocess.run(["git", "fetch", "origin"], check=False, capture_output=True, text=True)
            subprocess.run(["git", "pull", "--rebase", "origin", "main"], check=False, capture_output=True, text=True)
            # push
            subprocess.run(["git", "push", "origin", "HEAD:main"], check=False, capture_output=True, text=True)
            st.session_state.git_sync_status = "Кэш синхронизирован с GitHub (main)."
        else:
            st.session_state.git_sync_status = "GIT_REPO/GIT_TOKEN не заданы — пропустили push."
    except subprocess.CalledProcessError as e:
        st.session_state.git_sync_status = f"Git ошибка: {e}\nSTDERR: {getattr(e, 'stderr', '') or ''}"
    except Exception as e:
        st.session_state.git_sync_status = f"Git sync исключение: {e}"

# ====== Геокодер Яндекс ======

def geocode_address(address: str, api_key: str):
    """
    Возвращает: (lat, lon, components_dict, display_text)
    components_dict: {'locality': 'Тверь', 'province': 'Тверская область', ...}
    """
    url = (
        "https://geocode-maps.yandex.ru/1.x/"
        f"?apikey={api_key}&geocode={address}&format=json&lang=ru_RU&rspn=1"
    )
    r = requests.get(url, timeout=10)
    if r.status_code != 200:
        raise ValueError(f"Ошибка геокодера Яндекс: HTTP {r.status_code}")

    data = r.json()
    try:
        member = data["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]
    except (KeyError, IndexError):
        raise ValueError(_("Адрес не найден. Уточните адрес (например, добавьте 'Тверь' или 'Тверская область')."))

    pos = member["Point"]["pos"]
    lon_str, lat_str = pos.split()
    lat, lon = float(lat_str), float(lon_str)

    display_name = member.get("name", "")
    meta = member.get("metaDataProperty", {}).get("GeocoderMetaData", {})
    address_data = meta.get("Address", {})
    comps = address_data.get("Components", [])
    comps_dict = {}
    for comp in comps:
        kind = comp.get("kind")
        name = comp.get("name")
        if kind and name:
            comps_dict[kind] = name

    return lat, lon, comps_dict, display_name

def is_within_tver(components: dict) -> bool:
    """
    Признаём адрес внутри административных границ г. Тверь, если среди компонентов есть locality=Тверь
    или sublocality/area, у которых parent — Тверь (Яндекс обычно включает 'Тверь' куда-нибудь в Components).
    """
    for key in ("
