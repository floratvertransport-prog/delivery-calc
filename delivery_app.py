```python
import math
import requests
import streamlit as st
import os
import asyncio
import aiohttp
import json
import subprocess

# Установка заголовка вкладки
st.set_page_config(page_title="Флора калькулятор (розница)")

# Центрирование логотипа
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.image("logo.png", width=533)

# Функция Haversine
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    return distance

# Точки выхода
exit_points = [
    (36.055364, 56.795587),
    (35.871802, 56.808677),
    (35.804913, 56.831684),
    (36.020937, 56.850973),
    (35.797443, 56.882207),
    (35.932805, 56.902966)
]

# Таблица расстояний
distance_table = {
    'Клин': {'distance': 140, 'exit_point': (36.055364, 56.795587)},
    'Редкино': {'distance': 60, 'exit_point': (36.055364, 56.795587)},
    'Мокшино': {'distance': 76, 'exit_point': (36.055364, 56.795587)},
    'Новозавидовский': {'distance': 88, 'exit_point': (36.055364, 56.795587)},
    'Конаково': {'distance': 134, 'exit_point': (36.055364, 56.795587)},
    'Волоколамск': {'distance': 218, 'exit_point': (35.871802, 56.808677)},
    'Лотошино': {'distance': 148, 'exit_point': (35.871802, 56.808677)},
    'Руза': {'distance': 320, 'exit_point': (35.871802, 56.808677)},
    'Шаховская': {'distance': 204, 'exit_point': (35.871802, 56.808677)},
    'Великие Луки': {'distance': 740, 'exit_point': (35.804913, 56.831684)},
    'Жарковский': {'distance': 640, 'exit_point': (35.804913, 56.831684)},
    'Западная Двина': {'distance': 530, 'exit_point': (35.804913, 56.831684)},
    'Зубцов': {'distance': 238, 'exit_point': (35.804913, 56.831684)},
    'Нелидово': {'distance': 444, 'exit_point': (35.804913, 56.831684)},
    'Оленино': {'distance': 350, 'exit_point': (35.804913, 56.831684)},
    'Ржев': {'distance': 230, 'exit_point': (35.804913, 56.831684)},
    'Старица': {'distance': 132, 'exit_point': (35.804913, 56.831684)},
    'Торопец': {'distance': 620, 'exit_point': (35.804913, 56.831684)},
    'Дубна': {'distance': 230, 'exit_point': (36.020937, 56.850973)},
    'Кимры': {'distance': 186, 'exit_point': (36.020937, 56.850973)},
    'Бологое': {'distance': 356, 'exit_point': (35.797443, 56.882207)},
    'Вышний Волочек': {'distance': 242, 'exit_point': (35.797443, 56.882207)},
    'Лихославль': {'distance': 88, 'exit_point': (35.797443, 56.882207)},
    'Спирово': {'distance': 206, 'exit_point': (35.797443, 56.882207)},
    'Торжок': {'distance': 122, 'exit_point': (35.797443, 56.882207)},
    'Удомля': {'distance': 346, 'exit_point': (35.797443, 56.882207)},
    'Сонково': {'distance': 306, 'exit_point': (35.932805, 56.902966)},
    'Сандово': {'distance': 474, 'exit_point': (35.932805, 56.902966)},
    'Лесное': {'distance': 382, 'exit_point': (35.932805, 56.902966)},
    'Максатиха': {'distance': 232, 'exit_point': (35.932805, 56.902966)},
    'Рамешки': {'distance': 118, 'exit_point': (35.932805, 56.902966)},
    'Весьегонск': {'distance': 486, 'exit_point': (35.932805, 56.902966)},
    'Калязин': {'distance': 386, 'exit_point': (35.932805, 56.902966)},
    'Кесова Гора': {'distance': 414, 'exit_point': (35.932805, 56.902966)},
    'Красный Холм': {'distance': 330, 'exit_point': (35.932805, 56.902966)},
    'Бежецк': {'distance': 244, 'exit_point': (35.932805, 56.902966)},
    'Кашин': {'distance': 286, 'exit_point': (35.932805, 56.902966)}
}

# Тарифы
rate_per_km = 32
cargo_prices = {
    'маленький': 350,
    'средний': 500,
    'большой': 800
}

# Функции для кэша
def load_cache():
    cache_file = 'cache.json'
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            st.warning(f"Ошибка при загрузке кэша: {e}")
            return {}
    return {}

def save_cache(cache):
    cache_file = 'cache.json'
    try:
        st.session_state.cache_before_save = cache
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                saved_cache = json.load(f)
                st.session_state.cache_after_save = saved_cache
        # Настройка Git
        try:
            if not os.path.exists('.git'):
                subprocess.run(['git', 'init'], check=True, capture_output=True, text=True)
            git_repo = os.environ.get('GIT_REPO', 'https://github.com/floratvertransport-prog/delivery-calc.git')
            git_token = os.environ.get('GIT_TOKEN')
            if git_token:
                git_repo = git_repo.replace('https://', f'https://{git_token}@')
            # Проверяем и добавляем origin
            remote_output = subprocess.run(['git', 'remote', '-v'], capture_output=True, text=True)
            st.session_state.git_remote_status = f"Git remote: {remote_output.stdout}"
            if 'origin' not in remote_output.stdout:
                subprocess.run(['git', 'remote', 'add', 'origin', git_repo], check=True, capture_output=True, text=True)
            # Настраиваем Git
            subprocess.run(['git', 'config', '--global', 'user.name', os.environ.get('GIT_USER', 'floratvertransport-prog')], check=True, capture_output=True, text=True)
            subprocess.run(['git', 'config', '--global', 'user.email', 'floratvertransport-prog@example.com'], check=True, capture_output=True, text=True)
            # Исправляем detached HEAD
            branch_output = subprocess.run(['git', 'branch'], capture_output=True, text=True)
            st.session_state.git_branch_status = f"Git branch: {branch_output.stdout}"
            if 'detached' in branch_output.stdout:
                subprocess.run(['git', 'checkout', '-B', 'main'], check=True, capture_output=True, text=True)
                subprocess.run(['git', 'branch', '--set-upstream-to=origin/main', 'main'], check=True, capture_output=True, text=True)
            # Синхронизируем ветку
            try:
                fetch_result = subprocess.run(['git', 'fetch', 'origin'], check=True, capture_output=True, text=True)
                st.session_state.git_fetch_status = f"Git fetch: {fetch_result.stdout or 'Success'}"
                pull_result = subprocess.run(['git', 'pull', 'origin', 'main', '--allow-unrelated-histories'], check=True, capture_output=True, text=True)
                st.session_state.git_pull_status = f"Git pull: {pull_result.stdout or 'Success'}"
            except subprocess.CalledProcessError as e:
                st.session_state.git_sync_status = f"Ошибка git pull: {e}\nSTDERR: {e.stderr}"
                return
            # Проверяем изменения
            status_result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
            st.session_state.git_status = f"Git status: {status_result.stdout}"
            if cache_file in status_result.stdout:
                subprocess.run(['git', 'add', cache_file], check=True, capture_output=True, text=True)
                subprocess.run(['git', 'commit', '-m', 'Update cache.json'], check=True, capture_output=True, text=True)
                try:
                    push_result = subprocess.run(['git', 'push', 'origin', 'main'], check=True, capture_output=True, text=True)
                    st.session_state.git_sync_status = f"Кэш успешно синхронизирован с GitHub: {push_result.stdout or 'Success'}"
                except subprocess.CalledProcessError as e:
                    st.session_state.git_sync_status = f"Ошибка git push: {e}\nSTDERR: {e.stderr}"
            else:
                st.session_state.git_sync_status = "Нет изменений в cache.json для коммита"
        except subprocess.CalledProcessError as e:
            st.session_state.git_sync_status = f"Ошибка синхронизации с GitHub: {e}\nSTDERR: {e.stderr}"
    except Exception as e:
        st.session_state.save_cache_error = f"Ошибка при сохранении кэша: {e}"

# Проверка GIT_TOKEN
def check_git_token():
    git_token = os.environ.get('GIT_TOKEN')
    if not git_token:
        return "Ошибка: GIT_TOKEN не настроен в переменных окружения"
    try:
        response = requests.get('https://api.github.com/user', auth=('floratvertransport-prog', git_token))
        if response.status_code == 200:
            return f"GIT_TOKEN валиден: {response.json().get('login')}"
        else:
            return f"Ошибка проверки GIT_TOKEN: HTTP {response.status_code}, {response.json().get('message', 'Неизвестная ошибка')}"
    except Exception as e:
        return f"Ошибка проверки GIT_TOKEN: {str(e)}"

# Геокодирование через Яндекс
def geocode_address(address, api_key):
    url = f"https://geocode-maps.yandex.ru/1.x/?apikey={api_key}&geocode={address}&format=json"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        try:
            pos = data['response']['GeoObjectCollection']['featureMember'][0]['GeoObject']['Point']['pos']
            lon, lat = map(float, pos.split(' '))
            return lat, lon
        except (IndexError, KeyError):
            raise ValueError("Адрес не найден. Уточните адрес (например, добавьте 'Тверь' или 'Тверская область').")
    else:
        raise ValueError(f"Ошибка API: {response.status_code}")

# Получение IP сервера
async def get_server_ip():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.ipify.org?format=json', timeout=5) as response:
                if response.status == 200:
                    ip_data = await response.json()
                    return ip_data.get('ip', 'Не удалось получить IP')
                else:
                    return f"Ошибка получения IP: HTTP {response.status}"
    except aiohttp.ClientError as e:
        return f"Ошибка соединения при получении IP: {str(e)}"
    except Exception as e:
        return f"Неизвестная ошибка при получении IP: {str(e)}"

# Запрос к ORS
async def get_road_distance_ors(start_lon, start_lat, end_lon, end_lat, api_key):
    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
        "Accept": "application/geo+json"
    }
    body = {
        "coordinates": [[start_lon, start_lat], [end_lon, end_lat]],
        "units": "km",
        "radiuses": [1000, 1000]
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=body, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    distance = data["routes"][0]["summary"]["distance"]
                    return distance
                else:
                    error_data = await response.json()
                    error_code = error_data.get("error", {}).get("code", 0)
                    error_msg = error_data.get("error", {}).get("message", "Неизвестная ошибка")
                    if error_code == 2010:
                        raise ValueError(f"ORS не нашёл маршрут для координат: {error_msg}. Используется Haversine.")
                    raise ValueError(f"Ошибка ORS API: HTTP {response.status}. Код: {error_code}. Сообщение: {error_msg}")
    except aiohttp.ClientError as e:
        raise ValueError(f"Ошибка соединения с ORS API: {str(e)}")

# Поиск ближайшей точки выхода
def find_nearest_exit_point(dest_lat, dest_lon):
    min_dist = float('inf')
    nearest_exit = None
    for exit_point in exit_points:
        dist = haversine(dest_lat, dest_lon, exit_point[1], exit_point[0])
        if dist < min_dist:
            min_dist = dist
            nearest_exit = exit_point
    return nearest_exit, min_dist

# Извлечение населённого пункта
def extract_locality(address):
    if 'тверь' in address.lower():
        return 'Тверь'
    for locality in distance_table.keys():
        if locality.lower() in address.lower():
            return locality
    cache = load_cache()
    for locality in cache.keys():
        if locality.lower() in address.lower():
            return locality
    parts = address.split(',')
    for part in parts:
        part = part.strip()
        if part and 'область' not in part.lower() and 'ул.' not in part.lower() and 'г.' not in part.lower():
            return part
    return None

# Округление стоимости
def round_cost(cost):
    remainder = cost % 100
    if remainder <= 20:
        return (cost // 100) * 100
    else:
        return ((cost // 100) + 1) * 100

# Расчёт стоимости
async def calculate_delivery_cost(cargo_size, dest_lat, dest_lon, address, routing_api_key):
    if cargo_size not in cargo_prices:
        raise ValueError("Неверный размер груза. Доступны: маленький, средний, большой")
    base_cost = cargo_prices[cargo_size]
    nearest_exit, dist_to_exit = find_nearest_exit_point(dest_lat, dest_lon)
    locality = extract_locality(address)
    st.session_state.locality = locality
    if locality and locality.lower() == 'тверь':
        total_distance = 0
        total_cost = base_cost
        return total_cost, dist_to_exit, nearest_exit, locality, total_distance, "город"
    if locality and locality in distance_table:
        total_distance = distance_table[locality]['distance']
        extra_cost = total_distance * rate_per_km
        total_cost = base_cost + extra_cost
        rounded_cost = round_cost(total_cost) if total_distance > 0 else base_cost
        return rounded_cost, dist_to_exit, nearest_exit, locality, total_distance, "таблица"
    cache = load_cache()
    if locality and locality in cache:
        total_distance = cache[locality]['distance']
        extra_cost = total_distance * rate_per_km
        total_cost = base_cost + extra_cost
        rounded_cost = round_cost(total_cost) if total_distance > 0 else base_cost
        return rounded_cost, dist_to_exit, nearest_exit, locality, total_distance, "кэш"
    if routing_api_key and locality:
        try:
            road_distance = await get_road_distance_ors(nearest_exit[0], nearest_exit[1], dest_lon, dest_lat, routing_api_key)
            total_distance = road_distance * 2
            extra_cost = total_distance * rate_per_km
            total_cost = base_cost + extra_cost
            rounded_cost = round_cost(total_cost) if total_distance > 0 else base_cost
            cache[locality] = {'distance': total_distance, 'exit_point': nearest_exit}
            save_cache(cache)
            return rounded_cost, dist_to_exit, nearest_exit, locality, total_distance, "ors"
        except ValueError as e:
            st.warning(f"Ошибка ORS API: {e}. Используется Haversine с коэффициентом 1.3.")
            road_distance = dist_to_exit * 1.3
            total_distance = road_distance * 2
            extra_cost = total_distance * rate_per_km
            total_cost = base_cost + extra_cost
            rounded_cost = round_cost(total_cost) if total_distance > 0 else base_cost
            if locality:
                cache[locality] = {'distance': total_distance, 'exit_point': nearest_exit}
                save_cache(cache)
            return rounded_cost, dist_to_exit, nearest_exit, locality, total_distance, "haversine"
    road_distance = dist_to_exit * 1.3
    total_distance = road_distance * 2
    extra_cost = total_distance * rate_per_km
    total_cost = base_cost + extra_cost
    rounded_cost = round_cost(total_cost) if total_distance > 0 else base_cost
    if locality:
        cache[locality] = {'distance': total_distance, 'exit_point': nearest_exit}
        save_cache(cache)
    return rounded_cost, dist_to_exit, nearest_exit, locality, total_distance, "haversine"

# Streamlit UI
st.title("Калькулятор стоимости доставки по Твери и области для розничных клиентов")
st.write("Введите адрес доставки и выберите размер груза.")
api_key = os.environ.get("API_KEY")
routing_api_key = os.environ.get("ORS_API_KEY")
if not api_key:
    st.error("Ошибка: API-ключ для геокодирования не настроен. Обратитесь к администратору.")
else:
    cargo_size = st.selectbox("Размер груза", ["маленький", "средний", "большой"])
    address = st.text_input("Адрес доставки (например, 'Тверь, ул. Советская, 10' или 'Тверская область, Вараксино')", value="Тверская область, ")
    admin_password = st.text_input("Админ пароль для отладки (оставьте пустым для обычного режима)", type="password")
    if admin_password == "admin123":
        st.write("Точки выхода из Твери:")
        for i, point in enumerate(exit_points, 1):
            st.write(f"Точка {i}: {point}")
        server_ip = asyncio.run(get_server_ip())
        st.write(f"IP сервера Render: {server_ip}")
        st.write(f"Версия Streamlit: {st.__version__}")
        st.write(f"Версия aiohttp: {aiohttp.__version__}")
        st.write(f"Проверка GIT_TOKEN: {check_git_token()}")
        cache = load_cache()
        st.write(f"Текущий кэш: {cache}")
        if 'cache_before_save' in st.session_state:
            st.write(f"Кэш перед сохранением: {st.session_state.cache_before_save}")
        if 'cache_after_save' in st.session_state:
            st.write(f"Кэш после сохранения: {st.session_state.cache_after_save}")
        if 'save_cache_error' in st.session_state:
            st.write(f"Ошибка сохранения кэша: {st.session_state.save_cache_error}")
        if 'git_sync_status' in st.session_state:
            st.write(f"Статус синхронизации с GitHub: {st.session_state.git_sync_status}")
        if 'git_fetch_status' in st.session_state:
            st.write(f"Статус git fetch: {st.session_state.git_fetch_status}")
        if 'git_pull_status' in st.session_state:
            st.write(f"Статус git pull: {st.session_state.git_pull_status}")
        if 'git_remote_status' in st.session_state:
            st.write(st.session_state.git_remote_status)
        if 'git_branch_status' in st.session_state:
            st.write(st.session_state.git_branch_status)
        if 'git_status' in st.session_state:
            st.write(st.session_state.git_status)
        if not routing_api_key:
            st.warning("ORS_API_KEY не настроен. Для неизвестных адресов используется Haversine с коэффициентом 1.3.")
        else:
            st.success("ORS_API_KEY настроен. Расстояние будет рассчитано по реальным дорогам.")
        if cache:
            st.write("Кэш расстояний:")
            for locality, data in cache.items():
                st.write(f"{locality}: {data['distance']} км (точка выхода: {data['exit_point']})")
    if st.button("Рассчитать"):
        if address:
            try:
                dest_lat, dest_lon = geocode_address(address, api_key)
                result = asyncio.run(calculate_delivery_cost(cargo_size, dest_lat, dest_lon, address, routing_api_key))
                cost, dist_to_exit, nearest_exit, locality, total_distance, source = result
                st.success(f"Стоимость доставки: {cost} руб.")
                if admin_password == "admin123":
                    st.write(f"Координаты адреса: lat={dest_lat}, lon={dest_lon}")
                    st.write(f"Ближайшая точка выхода: {nearest_exit}")
                    st.write(f"Расстояние до ближайшей точки выхода (по прямой): {dist_to_exit:.2f} км")
                    st.write(f"Извлечённый населённый пункт: {locality}")
                    st.write(f"Источник расстояния: {source}")
                    if source == "город":
                        st.write(f"Населённый пункт: {locality} (доставка в пределах Твери)")
                        st.write(f"Километраж: {total_distance} км (без доплаты)")
                        st.write(f"Базовая стоимость: {cost} руб. (без округления)")
                    elif source == "таблица":
                        st.write(f"Населённый пункт из таблицы: {locality}")
                        st.write(f"Километраж из таблицы (туда и обратно): {total_distance} км")
                        st.write(f"Доплата: {total_distance} × 32 = {total_distance * 32} руб.")
                    elif source == "кэш":
                        st.write(f"Населённый пункт из кэша: {locality}")
                        st.write(f"Километраж из кэша (туда и обратно): {total_distance} км")
                        st.write(f"Доплата: {total_distance} × 32 = {total_distance * 32} руб.")
                    elif source == "ors":
                        st.write(f"Населённый пункт: {locality}")
                        st.write(f"Километраж по реальным дорогам (туда и обратно): {total_distance:.2f} км")
                        st.write(f"Доплата: {total_distance:.2f} × 32 = {total_distance * 32:.2f} руб.")
                    elif source == "haversine":
                        st.write(f"Населённый пункт: {locality}")
                        st.write(f"Километраж по Haversine с коэффициентом 1.3 (туда и обратно): {total_distance:.2f} км")
                        st.write(f"Доплата: {total_distance:.2f} × 32 = {total_distance * 32:.2f} руб.")
            except ValueError as e:
                st.error(f"Ошибка: {e}")
            except Exception as e:
                st.error(f"Ошибка при расчёте: {e}")
```

**Изменения**:
1. Добавлена функция `check_git_token`:
   ```python
   def check_git_token():
       git_token = os.environ.get('GIT_TOKEN')
       if not git_token:
           return "Ошибка: GIT_TOKEN не настроен в переменных окружения"
       try:
           response = requests.get('https://api.github.com/user', auth=('floratvertransport-prog', git_token))
           if response.status_code == 200:
               return f"GIT_TOKEN валиден: {response.json().get('login')}"
           else:
               return f"Ошибка проверки GIT_TOKEN: HTTP {response.status_code}, {response.json().get('message', 'Неизвестная ошибка')}"
       except Exception as e:
           return f"Ошибка проверки GIT_TOKEN: {str(e)}"
   ```
   - Выводится в админ-режиме: `Проверка GIT_TOKEN: ...`.
2. Улучшена настройка Git:
   - Используется `git checkout -B main` вместо `git checkout main` для создания/переключения на ветку `main`.
   - Добавлен `git fetch` перед `git pull` с отдельной отладкой:
     ```python
     fetch_result = subprocess.run(['git', 'fetch', 'origin'], check=True, capture_output=True, text=True)
     st.session_state.git_fetch_status = f"Git fetch: {fetch_result.stdout or 'Success'}"
     ```
3. Все Git-команды используют `capture_output=True, text=True` для детальных логов.

---

#### Шаг 2: Обновление `GIT_TOKEN` в Render
1. Войдите в https://dashboard.render.com/, выберите проект `delivery-calc-yf19`.
2. Перейдите в **Environment** → **Environment Variables**.
3. Обновите `GIT_TOKEN`:
   ```
   GIT_TOKEN = ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx (вставьте RenderSyncToken2025)
   ```
   - Убедитесь, что остальные переменные корректны:
     ```
     API_KEY = ••••••••••••• (для Яндекс Геокодирования)
     ORS_API_KEY = ••••••••••••• (для OpenRouteService)
     PYTHON_VERSION = 3.12.7
     GIT_USER = floratvertransport-prog
     GIT_REPO = https://github.com/floratvertransport-prog/delivery-calc.git
     ```
4. Нажмите **Save Changes**.

---

#### Шаг 3: Обновление кода в репозитории
1. Войдите в https://github.com/floratvertransport-prog/delivery-calc.
2. Найдите `delivery_app.py`, нажмите ✏️ **Edit this file**.
3. Замените код на новый из xaiArtifact (artifact_id: `6d305a7c-ad24-44fc-b6d9-fc278d968463`, version_id: `a9f5e3d2-4b7c-4f1e-9a8b-7e2f9c8a5e2d`).
4. В "Commit message" напишите: `Add GIT_TOKEN check and fix detached HEAD`.
5. Выберите **Commit directly to the main branch**.
6. Нажмите **Commit changes**.

---

#### Шаг 4: Проверка файлов
1. **Проверьте `requirements.txt`**:
   - Убедитесь, что в корне репозитория:
     ```
     requests
     streamlit>=1.37.0
     aiohttp==3.9.5
     streamlit-javascript
     ```
   - Если нужно, обновите: **Edit this file** → Закоммитьте: `Update requirements.txt`.
2. **Проверьте `logo.png`**:
   - Убедитесь, что `logo.png` (533x300 пикселей) есть.
   - Если нет, загрузите: **Add file** → **Upload files** → Закоммитьте: `Add logo.png`.
3. **Проверьте `cache.json`**:
   - Убедитесь, что `cache.json` существует и содержит `{}` или данные.
   - Если нет, создайте: **Add file** → **Create new file** → Вставьте `{}`, закоммитьте: `Create cache.json`.

---

#### Шаг 5: Перезапуск деплоя
1. В https://dashboard.render.com/, выберите проект `delivery-calc-yf19`.
2. В **Manual Deploy** нажмите **Deploy latest commit**.
3. Дождитесь логов:
   ```
   ==> Using Python version 3.12.7
   ==> Running 'streamlit run delivery_app.py --server.port 8080'
   ==> Your service is live 🎉
   ```

---

#### Шаг 6: Тестирование
1. Откройте https://delivery-calc-yf19.onrender.com.
2. **Тест 1: Вараксино**:
   - Введите: "Тверская область, Вараксино", груз: маленький.
   - Ожидаемый результат:
     - Стоимость: ~2300 руб. (ORS: ~30 км × 2 × 32 + 350 = 2270, остаток 70 > 20 → 2300).
     - Админ-режим (пароль `admin123`):
       - Проверка GIT_TOKEN: `GIT_TOKEN валиден: floratvertransport-prog` (или ошибка, например, `Ошибка проверки GIT_TOKEN: HTTP 401, Bad credentials`).
       - Источник: `ors` (первый запрос) или `кэш` (повторный).
       - Кэш перед сохранением: `{"Вараксино": {"distance": 60, "exit_point": [36.055364, 56.795587]}, ...}`
       - Кэш после сохранения: То же.
       - Статус синхронизации: `Кэш успешно синхронизирован с GitHub: Success` (или ошибка).
       - Git remote: `origin https://github.com/floratvertransport-prog/delivery-calc.git (fetch/push)`
       - Git branch: `* main`
       - Git status: Пусто или `M cache.json`.
       - Git fetch: `Git fetch: Success` (или ошибка).
       - Git pull: `Git pull: Success` (или ошибка).
3. **Проверьте `cache.json` на GitHub**:
   - После теста: https://github.com/floratvertransport-prog/delivery-calc/blob/main/cache.json.
   - Ожидаемый результат:
     ```json
     {
       "Изоплит": {"distance": 66.456, "exit_point": [36.055364, 56.795587]},
       "Мермерины": {"distance": 24.406, "exit_point": [35.797443, 56.882207]},
       "Вараксино": {"distance": 60, "exit_point": [36.055364, 56.795587]}
     }
     ```
4. **Тест 2: Тверь**:
   - Введите: "Тверь, ул. Советская, 10", груз: маленький.
   - Ожидаемый результат: 350 руб., источник: `город`.

---

#### Шаг 7: Если проблемы сохраняются
1. **Если `GIT_TOKEN` невалиден**:
   - В админ-режиме вы увидите: `Ошибка проверки GIT_TOKEN: HTTP 401, Bad credentials`.
   - Создайте новый токен:
     - GitHub → **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)** → **Generate new token (classic)**.
     - Имя: `RenderSyncToken2025v2`.
     - Scope: `repo`.
     - Срок: 90 дней.
     - Обновите `GIT_TOKEN` в Render (см. Шаг 2).
     - Перезапустите деплой.
2. **Если ошибка `origin`**:
   - Если в админ-режиме: `Статус синхронизации с GitHub: Ошибка git push: ... fatal: 'origin' does not appear to be a git repository`:
     - Проверьте `GIT_REPO` в Render:
       ```
       GIT_REPO = https://github.com/floratvertransport-prog/delivery-calc.git
       ```
     - Убедитесь, что репозиторий существует: https://github.com/floratvertransport-prog/delivery-calc.
     - Если репозиторий другой, обновите `GIT_REPO` в Render.
3. **Временное отключение Git**:
   - Если синхронизация не работает, отключите Git:
     ```python
     def save_cache(cache):
         cache_file = 'cache.json'
         try:
             st.session_state.cache_before_save = cache
             with open(cache_file, 'w', encoding='utf-8') as f:
                 json.dump(cache, f, ensure_ascii=False, indent=2)
             if os.path.exists(cache_file):
                 with open(cache_file, 'r', encoding='utf-8') as f:
                     saved_cache = json.load(f)
                     st.session_state.cache_after_save = saved_cache
             st.session_state.git_sync_status = "Git-синхронизация отключена, кэш сохранён локально"
         except Exception as e:
             st.session_state.save_cache_error = f"Ошибка при сохранении кэша: {e}"
     ```
     - Обновите `delivery_app.py` на GitHub.
     - Закоммитьте: `Disable Git sync temporarily`.
     - Перезапустите деплой.
     - Кэш будет работать локально, но теряться между деплоями.
4. **Ручное обновление `cache.json`**:
   - Если синхронизация не заработает, обновите `cache.json` на GitHub:
     ```json
     {
       "Изоплит": {"distance": 66.456, "exit_point": [36.055364, 56.795587]},
       "Мермерины": {"distance": 24.406, "exit_point": [35.797443, 56.882207]},
       "Вараксино": {"distance": 60, "exit_point": [36.055364, 56.795587]}
     }
     ```
     - **Edit this file** → Вставьте JSON → Закоммитьте: `Manually update cache.json`.
     - Перезапустите деплой.

---

### Замечания
- **Тверь**: Стоимость 350 руб. работает, источник `город`, всё корректно.
- **Кэш**: Локально работает, но не синхронизируется из-за проблем с `origin` и, возможно, `GIT_TOKEN`.
- **Git**:
  - Ошибка `origin` связана с неверным токеном или отсутствием настройки `origin`.
  - `detached HEAD` исправлен через `git checkout -B main`.
- **Проверка токена**: Новая функция `check_git_token` покажет валидность токена в админ-режиме.

---

### Поделитесь
Чтобы я мог дальше помочь, предоставьте:
1. Логи Render после деплоя (особенно ошибки Git, если есть).
2. Вывод из админ-режима для теста "Тверская область, Вараксино":
   - `Проверка GIT_TOKEN: ...`
   - `Статус синхронизации с GitHub: ...`
   - `Git fetch: ...`
   - `Git pull: ...`
   - `Git remote: ...`
   - `Git branch: ...`
   - `Git status: ...`
   - `Текущий кэш: ...`
   - `Кэш перед сохранением: ...`
   - `Кэш после сохранения: ...`
3. Содержимое `cache.json` на GitHub после теста: https://github.com/floratvertransport-prog/delivery-calc/blob/main/cache.json.
4. Скриншот админ-режима, если возможно.

Если что-то неясно или не получается, напишите, разберёмся! 😊
