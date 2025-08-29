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
            st.session_state.git_remote_status = f"Git remote: {remote_output.stdout.replace(git_token, '******') if git_token else remote_output.stdout or 'No remotes set'}"
            if 'origin' not in remote_output.stdout:
                subprocess.run(['git', 'remote', 'add', 'origin', git_repo], check=True, capture_output=True, text=True)
                st.session_state.git_remote_status = f"Git remote: added origin {git_repo.replace(git_token, '******') if git_token else git_repo}"
            # Настраиваем Git
            subprocess.run(['git', 'config', '--global', 'user.name', os.environ.get('GIT_USER', 'floratvertransport-prog')], check=True, capture_output=True, text=True)
            subprocess.run(['git', 'config', '--global', 'user.email', 'floratvertransport-prog@example.com'], check=True, capture_output=True, text=True)
            # Проверяем текущую ветку и исправляем detached HEAD
            branch_output = subprocess.run(['git', 'branch'], capture_output=True, text=True)
            st.session_state.git_branch_status = f"Git branch: {branch_output.stdout}"
            if 'detached' in branch_output.stdout:
                subprocess.run(['git', 'fetch', 'origin'], check=True, capture_output=True, text=True)
                subprocess.run(['git', 'checkout', '-B', 'main', 'origin/main'], check=True, capture_output=True, text=True)
                st.session_state.git_branch_status = f"Git branch: switched to main"
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
        return rounded_cost, distFinger1: System: Простите, но я не могу ответить на этот вопрос, так как он требует больше информации, чем у меня есть. Могу ли я помочь вам с чем-то ещё?
