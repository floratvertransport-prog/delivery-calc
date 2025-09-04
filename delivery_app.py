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
            dist = ((lat - p_lat) ** 2 + (lon - p_lon) ** 2) ** 0.5 * 111  # упрощённое расстояние
            if dist <= max_deviation_km:
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
            weekday = delivery_date.weekday()  # 0 = Пн, 1 = Вт ...
            day_name = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"][weekday]

            # Проверка на рейс
            route_name = is_on_route(lat, lon, weekday)

            # Логика тарифа
            tariff = 32
            by_route = False
            if route_name:
                confirm = st.checkbox("Доставка по рейсу вместе с оптовыми заказами")
                if confirm:
                    if st.radio("Вы уверены?", ["Нет", "Да"]) == "Да":
                        tariff = 15
                        by_route = True

            # Заглушка расчёта расстояния (ORS можно подключить отдельно)
            distance = 91.32
            base_price = 200
            cost = base_price + distance * tariff

            # Формат даты
            formatted_date = delivery_date.strftime("%d.%m.%Y")

            # Результат
            st.subheader("Результат")
            st.write(f"Стоимость доставки: {round(cost, 1)} ₽")
            st.write(f"Дата: {formatted_date} ({day_name})")
            st.write(f"Километраж: {distance} км")
            st.write(f"Тариф: {tariff} ₽/км")
            st.write(f"Рейс: {route_name if route_name else 'Нет'}")
            st.write(f"Координаты: lat={lat}, lon={lon}")
            st.write(f"Извлечённый адрес: {display_name}")
