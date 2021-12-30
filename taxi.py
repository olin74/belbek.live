# coder: Olin (telegram: @whitejoe)
# use for free
# donate bitcoin: 1MFy9M3g6nxFeg8X1GDYabMtYaiuRcYJPT

import math
import redis
import time
import datetime
import os
import json

# Загружаем секретные ссылки и токены из системы
REDIS_URL = os.environ['REDIS_URL']

# Устанавливаем константы
SYMBOL = "₽"  # Символ валюты текущей денежной системы
PLANET_RADIUS = 6371  # Радиус текущей планеты в км, погрешность 0.5%
ABOUT_LIMIT = 300  # Лимит символов в объявлении


class SpaceTaxi:
    def __init__(self):
        redis_url = REDIS_URL
        # redis_url = 'redis://:@localhost:6379'  # Для теста на локальном сервере

        # База данных водителей
        self.drivers = {'about': redis.from_url(redis_url, db=1),
                        'radius': redis.from_url(redis_url, db=2),
                        'price': redis.from_url(redis_url, db=3),
                        'wait': redis.from_url(redis_url, db=4),
                        'status': redis.from_url(redis_url, db=5),
                        'geo_long': redis.from_url(redis_url, db=6),
                        'geo_lat': redis.from_url(redis_url, db=7),
                        'impressions': redis.from_url(redis_url, db=8),
                        'last_impression': redis.from_url(redis_url, db=9),
                        'views': redis.from_url(redis_url, db=10),
                        'name': redis.from_url(redis_url, db=11),
                        'username': redis.from_url(redis_url, db=12)}

        # Подгрузка координат населённых пунктов
        with open("geo_dolina.json") as json_file:
            self.points = json.load(json_file)

    # Вычисление расстояния между координатами
    @staticmethod
    def get_distance(lat1, long1, lat2, long2):
        # Функция вычисления гаверсинуса
        def hav(x):
            return (math.sin(x / 2)) ** 2

        # Координаты из градусов в радианы
        long1_rad = math.pi * long1 / 180
        lat1_rad = math.pi * lat1 / 180
        long2_rad = math.pi * long2 / 180
        lat2_rad = math.pi * lat2 / 180
        # Много геоматематики, пояснять не буду.
        res = 2 * PLANET_RADIUS * math.asin(math.sqrt(hav(long2_rad - long1_rad) + math.cos(long1_rad) *
                                                      math.cos(long1_rad) * hav(lat2_rad - lat1_rad)))
        return res

    # Функция увеличения счетчика просмотров у водителя
    def inc_impression(self, user_driver):
        current_time = int(time.time())
        # Проверка на смену дат и обнуление
        dt_timestamp = int(datetime.datetime.combine(datetime.date.today(), datetime.time(0, 0, 0)).timestamp())
        if user_driver not in self.drivers['last_impression'] or int(
                self.drivers['last_impression'][user_driver]) < dt_timestamp:
            self.drivers['impressions'][user_driver] = 0
        # Увеличиваем счетчик дня
        self.drivers['impressions'][user_driver] = int(self.drivers['impressions'][user_driver]) + 1
        # Увеличиваем счетчик общий
        self.drivers['views'][user_driver] = int(self.drivers['views'][user_driver]) + 1
        # Запоминаем время последнего показа водительского объявления пользователю
        self.drivers['last_impression'][user_driver] = current_time

    # Формирование списка водителей во время поиска
    def go_search(self, location, is_delivery=False):
        result_message = ''

        # Перебираем всех водителей
        geo = {}
        for user_driver_ne in self.drivers['status'].keys():
            user_driver = int(user_driver_ne)
            # Нам нужны только активныуе ("в поиске")
            if int(self.drivers['status'][user_driver]) == 1:
                # Вычисляем расстояние до водителя
                dist = self.get_distance(location['latitude'], location['longitude'],
                                         float(self.drivers['geo_lat'][user_driver]),
                                         float(self.drivers['geo_long'][user_driver])
                                         )
                # Если водитель рядом, то добавляем в результирующий список
                if dist < int(self.drivers['radius'][user_driver]):
                    geo[user_driver] = dist

        # Сортируем и составляем выдачу текстом
        sorted_list = sorted(geo, key=geo.get)
        for user_driver in sorted_list:
            dist = geo[user_driver]
            result_message = result_message + f"🚖 {self.drivers['about'][user_driver].decode('utf-8')}\n" \
                                              f"🚕 {dist:.2f} км\n" \
                                              f"💰 {int(self.drivers['price'][user_driver])} {SYMBOL}/км\n" \
                                              f"💬 @{self.drivers['username'][user_driver].decode('utf-8')}\n\n"
            # Если этого водителя нету в недавнем поиске, то накручиваем ему счетчик просмотра
            self.inc_impression(user_driver)

        s_count = len(sorted_list)
        m_text = "🤷‍ Ничего не найдено! Рядом нет водителей, придется попробовать позже."
        if s_count > 0:
            m_text = f"Найдено водителей рядом с Вами: {s_count}\n\n{result_message}" \
                     f"💬 Можете связаться с любым водителем и договориться с ним о совместной поездке." \
                     " Приятной дороги, не забудьте пристегнуть ремни безопасности!"
            if is_delivery:
                m_text = f"Найдено водителей рядом с местом: {s_count}\n\n{result_message}" \
                         f"💬 Можете связаться с любым водителем и договориться с ним о доставке."

        return m_text
