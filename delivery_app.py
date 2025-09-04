import streamlit as st
import requests
import json
import os
import datetime

# =========================
# Настройки страницы
# =========================
st.set_page_config(
    page_title="Калькулятор доставки (розница)",
    page_icon="favicon.png",
    layout="centered"
)

# Логотип и заголовок
st.image("logo.png", use_container_width=False, width=200)
st.markdown("<h2 style='text-align: center;'>Калькулятор доставки (розница)</h2>", unsafe_allow_html=True)
st.title("Калькулятор стоимости доставки по Твери и области для розничных клиентов")

# =========================
# Загрузка маршрутов
# =========================
@st.cache_data
def load_routes():
    with open("routes.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return list(data.values())
    return data

routes = load_routes()

# =========================
# ORS: расчёт расстояния
# =========================
ORS_API_KEY = os.getenv("ORS_API_KEY")

def get_distance(lat1, lon1, lat2, lon2):
    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {"Authorization": ORS_API_KEY}
    body = {"coordinates": [[lon1, lat1], [lon2, lat2]]}
    resp = requests.post(url, json=body, headers=headers, timeout=30)
    data = resp.json()
    try:
        meters = data["routes"][0]["summary"]["distance"]
        return meters / 1000  # в километрах
    except Exception:
        return None

# =========================
# Геокодирование
# =========================
def geocode(address):
    url = f"https://nominatim.openstreetmap.org/search"
    params = {"q": address, "format": "json", "limit": 1}
    resp = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"})
    data = resp.json()
    if not data:
        return None, None, None
    return float(data[0]["lat"]), float(data[0]["lon"]), data[0]["display_name"]

# =========================
# Проверка принадлежности к рейсу
# =========================
def is_on_route(lat, lon, weekday, max_deviation_km=10):
    for route in routes:
        if weekday not in route["days"]:
            continue
        for point in route["points"]:
            p_lon, p_lat = point
            dist = get_distance(lat, lon, p_lat, p_lon)
            if dist is not None and dist <= max_deviation_km:
                return route["name"]
    return None

# =========================
# Интерфейс
# =========================
address = st.text_input("Введите адрес доставки", value="Тверская область, ")
cargo_size = st.selectbox("Размер груза", ["маленький", "средний", "большой"])
delivery_date = st.date_input("Выберите дату доставки", datetime.date.today())

# Кнопка расчёта
if st.button("Рассчитать"):
    if address.strip() and not address.strip().lower().startswith("/admin"):
        lat, lon, display_name = geocode(address)
        if not lat:
            st.error("Адрес не найден!")
        else:
            weekday = delivery_date.weekday()  # 0 = Пн
            day_name = ["Понедельник", "Вторник", "Среда",
                        "Четверг", "Пятница", "Суббота", "Воскресенье"][weekday]

            # Проверка на рейс
            route_name = is_on_route(lat, lon, weekday)

            # Определяем ближайшую точку выхода
            exit_points = [
                (36.055364, 56.795587),
                (35.871802, 56.808677),
                (35.804913, 56.831684),
                (36.020937, 56.850973),
                (35.797443, 56.882207),
                (35.932805, 56.902966),
                (35.783293, 56.844247)
            ]
            best_exit = None
            best_dist = float("inf")
            for lon_e, lat_e in exit_points:
                d = get_distance(lat, lon, lat_e, lon_e)
                if d is not None and d < best_dist:
                    best_dist = d
                    best_exit = (lon_e, lat_e)

            # Итоговый километраж
            distance = best_dist if best_dist != float("inf") else 0

            # Логика тарифа
            tariff = 32
            by_route = False
            if route_name:
                st.markdown(
                    f"<p style='color: green; font-weight: bold;'>✅ Этот заказ можно доставить вместе с оптовыми клиентами (рейс {route_name})</p>",
                    unsafe_allow_html=True
                )
                confirm = st.checkbox("Доставка по рейсу вместе с оптовыми заказами")
                if confirm:
                    if st.radio("Вы уверены?", ["Нет", "Да"]) == "Да":
                        tariff = 15
                        by_route = True

            # Стоимость
            base_price = 200
            cost = base_price + distance * tariff

            # Формат даты
            formatted_date = delivery_date.strftime("%d.%m.%Y")

            # Результат
            st.subheader("Результат")
            st.write(f"Стоимость доставки: {round(cost, 1)} ₽")
            st.write(f"Дата: {formatted_date} ({day_name})")
            st.write(f"Километраж: {round(distance, 2)} км")
            st.write(f"Тариф: {tariff} ₽/км")
            st.write(f"Рейс: {route_name if route_name else 'Нет'}")
            st.write(f"Координаты: lat={lat}, lon={lon}")
            st.write(f"Ближайшая точка выхода: {best_exit}")
            st.write(f"Расстояние до выхода: {round(best_dist, 2)} км")
            st.write(f"Извлечённый адрес: {display_name}")
