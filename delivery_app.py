import math
import requests
import streamlit as st
import os
import json
from datetime import date, datetime
from urllib.parse import urlencode

# =====================
# Настройки приложения
# =====================
PAGE_TITLE = "Флора калькулятор (розница) — улучшенная версия"
PAGE_ICON = "favicon.png"

# Тарифы на км
RATE_PER_KM_DEFAULT = 32  # обычная доставка
RATE_PER_KM_ROUTE = 15    # совместно с оптовым рейсом

# Коэффициент для прямой (Haversine), если ORS недоступен
HAVERSINE_CORR = 1.30

# Минимальная стоимость доплаты за выезд (опционально, 0 = отключено)
MIN_EXTRA_CHARGE = 0

# Ключи в переменных окружения
YANDEX_GEOCODER_KEY_ENV = "API_KEY"     # HTTP Геокодер Яндекс
ORS_API_KEY_ENV = "ORS_API_KEY"         # OpenRouteService

# Репозиторий для кэша (опционально)
GIT_REPO_ENV = "GIT_REPO"
GIT_TOKEN_ENV = "GIT_TOKEN"
GIT_USER_ENV = "GIT_USER"

# =====================
# Инициализация страницы
# =====================
st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON)

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    try:
        st.image("logo.png", width=533)
    except Exception:
        st.write(":truck: Флора калькулятор")

# =====================
# Справочники и данные
# =====================
CARGO_PRICES = {
    "маленький": 500,
    "средний": 800,
    "большой": 1200,
}

# Точки выхода из Твери (lon, lat)
EXIT_POINTS = [
    (36.055364, 56.795587),
    (35.871802, 56.808677),
    (35.804913, 56.831684),
    (36.020937, 56.850973),
    (35.797443, 56.882207),
    (35.932805, 56.902966),
]

# Алиасы населённых пунктов -> нормализованное имя
ALIASES = {
    "тверь": "Тверь",
    "завидово": "Завидово",
    "ново-завидово": "Новозавидовский",
    "новозавидово": "Новозавидовский",
}

# Справочник расстояний (км, как ПОЛНЫЙ пробег туда-обратно от границы города/точки выхода)
DISTANCE_TABLE = {
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
    'Пено': {'distance': 400, 'exit_point': (35.797443, 56.882207), 'coords': (32.716667, 56.916667)},
    # Добавим явный синоним для Завидово (если используем в расписании)
    'Завидово': {'distance': 88, 'exit_point': (36.055364, 56.795587), 'coords': (36.533333, 56.533333)},
}

# Рейсы по дням недели (0=Пн ... 6=Вс)
REYSY = {
    0: [
        ["Великие Луки", "Жарковский", "Торопец", "Западная Двина", "Нелидово", "Оленино", "Зубцов", "Ржев", "Старица"],
        ["Кашин", "Калязин", "Кесова Гора"],
    ],
    1: [
        ["Конаково", "Редкино", "Мокшино", "Новозавидовский", "Клин", "Завидово"],
        ["Руза", "Волоколамск", "Шаховская", "Лотошино"],
    ],
    2: [
        ["Дубна", "Кимры"],
        ["Старица", "Ржев", "Зубцов"],
        ["Кувшиново", "Осташков", "Селижарово", "Пено"],
    ],
    3: [
        ["Великие Луки", "Жарковский", "Торопец", "Западная Двина", "Нелидово", "Оленино"],
        ["Бологое"],
    ],
    4: [
        ["Удомля", "Вышний Волочек", "Спирово", "Торжок", "Лихославль"],
        ["Лесное", "Максатиха", "Рамешки"],
        ["Сандово", "Весьегонск", "Красный Холм", "Сонково", "Бежецк"],
    ],
}

# =====================
# Утилиты
# =====================

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    from math import radians, sin, cos, atan2, sqrt
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

CACHE_FILE = 'cache.json'

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache: dict):
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.warning(f"Ошибка сохранения кэша: {e}")


def normalize_locality(address: str) -> str | None:
    if not address:
        return None
    s = address.lower()
    for key, norm in ALIASES.items():
        if key in s:
            return norm
    # прямое попадание по таблице
    for name in DISTANCE_TABLE.keys():
        if name.lower() in s:
            return name
    # попытка взять 'чистую' часть адреса
    parts = [p.strip() for p in address.split(',') if p.strip()]
    for part in parts:
        if all(x not in part.lower() for x in ['область', 'ул.', 'г.']):
            return part
    return None


def find_nearest_exit_point(dest_lat: float, dest_lon: float):
    best = None
    best_dist = float('inf')
    for (lon, lat) in EXIT_POINTS:
        d = haversine(dest_lat, dest_lon, lat, lon)
        if d < best_dist:
            best_dist = d
            best = (lon, lat)
    return best, best_dist


def geocode_yandex(address: str, api_key: str):
    base = "https://geocode-maps.yandex.ru/1.x/"
    params = {
        "apikey": api_key,
        "geocode": address,
        "format": "json",
        "lang": "ru_RU",
        "results": 1,
    }
    try:
        resp = requests.get(base, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        member = data['response']['GeoObjectCollection']['featureMember']
        if not member:
            raise ValueError("Адрес не найден. Уточните адрес (например, добавьте 'Тверь' или 'Тверская область').")
        pos = member[0]['GeoObject']['Point']['pos']
        lon, lat = map(float, pos.split())
        return lat, lon
    except requests.RequestException as e:
        raise ValueError(f"Ошибка геокодера Яндекс: {e}") from e
    except Exception as e:
        raise ValueError(f"Ошибка обработки ответа геокодера: {e}") from e


def ors_distance_km(start_lon: float, start_lat: float, end_lon: float, end_lat: float, api_key: str) -> float:
    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {"Authorization": api_key, "Content-Type": "application/json", "Accept": "application/geo+json"}
    body = {
        "coordinates": [[start_lon, start_lat], [end_lon, end_lat]],
        "units": "km",
        "radiuses": [1000, 1000],
    }
    try:
        resp = requests.post(url, json=body, headers=headers, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            return float(data["routes"][0]["summary"]["distance"])
        else:
            data = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else {}
            code = data.get("error", {}).get("code", resp.status_code)
            msg = data.get("error", {}).get("message", resp.text)
            if code == 2010:
                raise RuntimeError(f"ORS не нашёл маршрут: {msg}")
            raise RuntimeError(f"Ошибка ORS API: HTTP {resp.status_code}. {msg}")
    except requests.RequestException as e:
        raise RuntimeError(f"Ошибка соединения с ORS: {e}") from e


def check_route_match(locality: str | None, delivery_date: date | None) -> bool:
    if not locality or not delivery_date:
        return False
    day = delivery_date.weekday()
    routes = REYSY.get(day, [])
    return any(locality in r for r in routes)


def round_cost(cost: int | float) -> int:
    cost = int(round(cost))
    rem = cost % 100
    if rem <= 20:
        return (cost // 100) * 100
    return ((cost // 100) + 1) * 100


def calc_cost(cargo_size: str, dest_lat: float, dest_lon: float, address: str, ors_key: str | None, delivery_date: date | None, use_route_rate: bool):
    if cargo_size not in CARGO_PRICES:
        raise ValueError("Неверный размер груза. Доступны: маленький, средний, большой")

    base_cost = CARGO_PRICES[cargo_size]
    nearest_exit, dist_to_exit = find_nearest_exit_point(dest_lat, dest_lon)
    locality = normalize_locality(address)

    rate = RATE_PER_KM_ROUTE if use_route_rate else RATE_PER_KM_DEFAULT

    # Внутри Твери — только базовая стоимость
    if locality == 'Тверь':
        return {
            "cost": base_cost,
            "source": "город",
            "locality": locality,
            "total_distance": 0.0,
            "rate": rate,
            "nearest_exit": nearest_exit,
            "dist_to_exit": dist_to_exit,
        }

    cache = load_cache()

    # Таблица
    if locality and locality in DISTANCE_TABLE:
        total_distance = float(DISTANCE_TABLE[locality]['distance'])
        extra = max(total_distance * rate, MIN_EXTRA_CHARGE)
        total = base_cost + extra
        return {
            "cost": round_cost(total) if total_distance > 0 else base_cost,
            "source": "таблица",
            "locality": locality,
            "total_distance": total_distance,
            "rate": rate,
            "nearest_exit": nearest_exit,
            "dist_to_exit": dist_to_exit,
        }

    # Кэш
    if locality and locality in cache:
        total_distance = float(cache[locality]['distance'])
        extra = max(total_distance * rate, MIN_EXTRA_CHARGE)
        total = base_cost + extra
        return {
            "cost": round_cost(total) if total_distance > 0 else base_cost,
            "source": "кэш",
            "locality": locality,
            "total_distance": total_distance,
            "rate": rate,
            "nearest_exit": tuple(cache[locality].get('exit_point', nearest_exit)),
            "dist_to_exit": dist_to_exit,
        }

    # ORS либо Haversine
    if locality and ors_key:
        try:
            road_one_way = ors_distance_km(nearest_exit[0], nearest_exit[1], dest_lon, dest_lat, ors_key)
            total_distance = road_one_way * 2
            extra = max(total_distance * rate, MIN_EXTRA_CHARGE)
            total = base_cost + extra
            # Сохранить в кэш
            cache[locality] = {
                'distance': round(total_distance, 2),
                'exit_point': list(nearest_exit),
                'ts': datetime.utcnow().isoformat(),
            }
            save_cache(cache)
            return {
                "cost": round_cost(total) if total_distance > 0 else base_cost,
                "source": "ors",
                "locality": locality,
                "total_distance": total_distance,
                "rate": rate,
                "nearest_exit": nearest_exit,
                "dist_to_exit": dist_to_exit,
            }
        except Exception as e:
            st.warning(f"Ошибка ORS: {e}. Используется Haversine × {HAVERSINE_CORR}.")

    # Haversine fallback
    road_one_way = dist_to_exit * HAVERSINE_CORR
    total_distance = road_one_way * 2
    extra = max(total_distance * rate, MIN_EXTRA_CHARGE)
    total = base_cost + extra
    if locality:
        cache[locality] = {
            'distance': round(total_distance, 2),
            'exit_point': list(nearest_exit),
            'ts': datetime.utcnow().isoformat(),
        }
        save_cache(cache)
    return {
        "cost": round_cost(total) if total_distance > 0 else base_cost,
        "source": "haversine",
        "locality": locality,
        "total_distance": total_distance,
        "rate": rate,
        "nearest_exit": nearest_exit,
        "dist_to_exit": dist_to_exit,
    }

# =====================
# UI
# =====================
st.title("Калькулятор стоимости доставки по Твери и области для розничных клиентов — v2")
st.write("Введите адрес доставки, выберите размер груза и дату доставки.")

api_key = os.environ.get(YANDEX_GEOCODER_KEY_ENV)
ors_key = os.environ.get(ORS_API_KEY_ENV)

if not api_key:
    st.error("Ошибка: API-ключ для геокодирования не настроен (переменная окружения API_KEY). Обратитесь к администратору.")

with st.form(key="delivery_form"):
    cargo_size = st.selectbox("Размер груза", list(CARGO_PRICES.keys()))
    address = st.text_input(
        "Адрес доставки (например, 'Тверь, ул. Советская, 10' или 'Тверская область, Вараксино')",
        value="Тверская область, ",
    )
    delivery_date = st.date_input("Дата доставки", value=date(2025, 9, 2), format="DD.MM.YYYY")

    # Отладочный блок (свёрнут по умолчанию)
    admin_password = st.text_input("Админ пароль для отладки (оставьте пустым для обычного режима)", type="password")

    # Логика рейса
    locality_guess = normalize_locality(address)
    on_route_today = check_route_match(locality_guess, delivery_date)
    if on_route_today:
        if 'use_route' not in st.session_state:
            st.session_state.use_route = False
        st.session_state.use_route = st.checkbox("Использовать доставку по рейсу (совместно с оптом)", value=st.session_state.use_route)
        if st.session_state.use_route and not st.session_state.get('route_confirmed', False):
            confirm = st.radio(
                "Подтвердите: заказ подходит для рейсовой доставки (объём/время допускают совмещение)",
                ("Нет", "Да"),
            )
            if confirm == "Да":
                st.session_state.route_confirmed = True
            else:
                st.session_state.use_route = False

    submit_button = st.form_submit_button("Рассчитать")

if submit_button:
    try:
        if not address:
            st.error("Введите адрес доставки")
        else:
            dest_lat, dest_lon = geocode_yandex(address, api_key)
            use_route_rate = st.session_state.get('use_route', False) and st.session_state.get('route_confirmed', False)
            result = calc_cost(cargo_size, dest_lat, dest_lon, address, ors_key, delivery_date, use_route_rate)

            st.success(f"Стоимость доставки: {int(result['cost'])} руб.")

            # Подробности
            with st.expander("Подробности расчёта"):
                st.write(f"Извлечённый населённый пункт: {result['locality'] or 'не определён'}")
                st.write(f"Источник расстояния: {result['source']}")
                if result['source'] == "город":
                    st.write("Доставка в пределах Твери: доплата за км не взимается.")
                else:
                    st.write(f"Километраж (Т/О): {result['total_distance']:.2f} км")
                    st.write(f"Тариф: {result['rate']} руб/км")
                st.write(f"Ближайшая точка выхода: {result['nearest_exit']}")
                st.write(f"Расстояние по прямой до точки выхода: {result['dist_to_exit']:.2f} км")
                st.write(f"Дата доставки: {delivery_date.strftime('%d.%m.%Y')} ({delivery_date.strftime('%A')})")
                st.write(f"Использован рейс: {use_route_rate}")

            # Отладка
            if admin_password == "admin123":
                with st.expander(":wrench: Отладка / среда"):
                    st.write(f"Версия Streamlit: {st.__version__}")
                    st.write(f"ORS ключ настроен: {bool(ors_key)}")
                    st.write("Кэш расстояний:")
                    st.json(load_cache())
    except ValueError as e:
        st.error(f"Ошибка: {e}")
    except Exception as e:
        st.error(f"Ошибка при расчёте: {e}")
