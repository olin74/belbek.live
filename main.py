# coder: Olin (telegram: @whitejoe)
# use for free
# donate bitcoin: 1MFy9M3g6nxFeg8X1GDYabMtYaiuRcYJPT

import json
import math
import redis
import telebot
from telebot import types
import time
import re
import os

# Устанавливаем константы
ADMIN_LIST = [665812965]  # Список админов для спец команд (тут только Олин)
ABOUT_LIMIT = 100  # Лимит символов в описании
DESCRIPTION_LIMIT = 600  # Лимит символов в подробностях
PRICE_LIMIT = 25  # Лимит символов в цене
LIST_STEP = 10  # Результатов поиска за 1 раз
TIME_OUT_USER = 30 * 30 * 24 * 30  # Время отсутствия активности пользователя перед удалением его меток
CONTENT_TYPES = ["text", "audio", "document", "photo", "sticker", "video", "video_note", "voice", "location", "contact",
                 "new_chat_members", "left_chat_member", "new_chat_title", "new_chat_photo", "delete_chat_photo",
                 "group_chat_created", "supergroup_chat_created", "channel_chat_created", "migrate_to_chat_id",
                 "migrate_from_chat_id", "pinned_message"]


# Вычисление расстояния между координатами
def get_distance(long1, lat1, long2, lat2):
    # Функция вычисления гаверсинуса
    def hav(x):
        return (math.sin(x / 2)) ** 2

    # Радиус текущей планеты в км, погрешность 0.5%
    planet_radius = 6371  # Земля 6371, Марс 3380
    # Координаты из градусов в радианы
    long1_rad = math.pi * long1 / 180
    lat1_rad = math.pi * lat1 / 180
    long2_rad = math.pi * long2 / 180
    lat2_rad = math.pi * lat2 / 180
    # Много геоматематики, пояснять не буду.
    res = 2 * planet_radius * math.asin(math.sqrt(hav(long2_rad - long1_rad) + math.cos(long1_rad) *
                                                  math.cos(long1_rad) * hav(lat2_rad - lat1_rad)))
    return res


class Live:
    def __init__(self):

        # Подгружаем из системы ссылки на базы данных
        redis_url = os.environ['REDIS_URL_LIVE']
        redis_url_labels = os.environ['REDIS_URL_LABELS']
        # redis_url_events = os.environ['REDIS_URL_EVENTS']
        # redis_url = 'redis://:@localhost:6379'  # Для теста на локальном сервере

        # База данных пользователей
        self.users = {'wait': redis.from_url(redis_url, db=1),
                      'status': redis.from_url(redis_url, db=2),
                      'geo_long': redis.from_url(redis_url, db=3),
                      'geo_lat': redis.from_url(redis_url, db=4),
                      'category': redis.from_url(redis_url, db=5),
                      'subcategory': redis.from_url(redis_url, db=6),
                      'name': redis.from_url(redis_url, db=7),
                      'username': redis.from_url(redis_url, db=8),
                      'search': redis.from_url(redis_url, db=9),
                      # 'labels': redis.from_url(redis_url, db=10),
                      'last_login': redis.from_url(redis_url, db=11)
                      }

        # База данных меток
        self.labels = {'about': redis.from_url(redis_url_labels, db=1),
                       'description': redis.from_url(redis_url_labels, db=2),
                       'photos': redis.from_url(redis_url_labels, db=3),
                       'price': redis.from_url(redis_url_labels, db=4),
                       'subcategory': redis.from_url(redis_url_labels, db=5),
                       'tags': redis.from_url(redis_url_labels, db=6),
                       'status_label': redis.from_url(redis_url_labels, db=7),
                       'geo_long': redis.from_url(redis_url_labels, db=8),
                       'geo_lat': redis.from_url(redis_url_labels, db=9),
                       'views': redis.from_url(redis_url_labels, db=10),
                       'author': redis.from_url(redis_url_labels, db=11),
                       'zoom': redis.from_url(redis_url_labels, db=12)
                       }

        # База данных событий
        # self.events =

        # Инициализируем индексацию меток
        self.common = redis.from_url(redis_url, db=0)
        if "index" not in self.common:
            index = 0
            for k in self.labels['status_label'].keys():
                index = k
            self.common['index'] = index

        # Подгрузка категорий
        with open("categories.json") as json_file:
            self.categories = json.load(json_file)

        # Кнопки меню
        self.menu_items = [f'Еще {LIST_STEP}', 'Новый поиск', 'Выбрать категорию', 'Выбрать подкатегорию',
                           'Менеджер меток']
        self.menu_labels = ['Выход', "Что такое метка?", "Мои метки", "✳️ Создать метку ✳️"]
        self.menu_edit_label = ['Изменить описание', 'Изменить подробности', 'Изменить фотографии', 'Изменить цену',
                                'Изменить категорию', 'Изменить опции', 'Снять с публикации', 'Опубликовать',
                                'Продвижение']
        # Чистка базы
        for field in self.labels:
            for key in self.labels[field].keys():
                if key not in self.labels['status_label'].keys():
                    self.labels[field].delete(key)
        for label_id in self.labels['status_label'].keys():
            user_id = int(self.labels['author'][label_id])
            if int(self.users['last_login'][user_id]) < int(time.time()) - TIME_OUT_USER:
                self.labels['status_label'][label_id] = 0

    # Стартовое сообщение
    def go_start(self, bot, message, is_start=True):
        user_id = message.chat.id
        menu_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
        # Если поиск
        first_row = []
        if user_id in self.users['search']:
            first_row.append(types.KeyboardButton(text=self.menu_items[0]))
        first_row.append(types.KeyboardButton(text=self.menu_items[1], request_location=True))
        menu_keyboard.row(*first_row)

        second_row = [types.KeyboardButton(text=self.menu_items[2])]
        if user_id in self.users['category']:
            second_row.append(types.KeyboardButton(text=self.menu_items[3]))

        second_row.append(types.KeyboardButton(text=self.menu_items[4]))
        menu_keyboard.row(*second_row)
        # Сброс статуса и ожидания ввода текста
        self.users['status'][user_id] = -1
        self.users['wait'][user_id] = 0
        self.users['last_login'][user_id] = int(time.time())
        # Подсчет статистики
        active = 0
        for label_id in self.labels['status_label'].keys():
            if int(self.labels['status_label'][label_id]) == 1:
                active += 1
        menu_message = ""
        if is_start:
            menu_message = f"Объявлений опубликовано: {active}\n" \
                           f"🔎 Для поиска мест, укажите категорию, нажмите “Новый поиск” " \
                           f"(определение геолокации должно быть включено)" \
                           f" или отправьте свои координаты текстом.\n" \
                           f"Канал поддержки https://t.me/BelbekLive\n"
        mess_cat = "Все"
        if user_id in self.users['category']:
            mess_cat = self.users['category'][user_id].decode('utf-8')
        menu_message = menu_message + f"\nКатегория поиска: {mess_cat}"
        if user_id in self.users['category']:
            mess_cat = "Все"
            if user_id in self.users['subcategory']:
                mess_cat = self.users['subcategory'][user_id].decode('utf-8')
            menu_message = menu_message + f"\nПодкатегория поиска: {mess_cat}"
        bot.send_message(message.chat.id, menu_message, reply_markup=menu_keyboard, disable_web_page_preview=True)

    # Запрос объявления
    def go_about(self, bot, message, label_id):
        keyboard = types.ReplyKeyboardRemove()
        user_id = message.chat.id
        # Устанавливаем ожидание текстового ответа для поля "объявление"
        self.users['wait'][user_id] = 1
        self.users['status'][user_id] = label_id
        bot.send_message(message.chat.id, f"Введите название и краткое описание места (не больше {ABOUT_LIMIT}"
                                          f" символов), например: “Спот. Культурное протранство. Туристический центр.”",
                         reply_markup=keyboard)
        return

    # Запрос подробностей
    def go_description(self, bot, message, label_id):
        keyboard = types.ReplyKeyboardRemove()
        user_id = message.chat.id
        # Устанавливаем ожидание текстового ответа для поля "подробности"
        self.users['wait'][user_id] = 2
        self.users['status'][user_id] = label_id
        bot.send_message(message.chat.id, f"📝 Введите подробное описание места "
                                          f"(не больше {DESCRIPTION_LIMIT} символов)",
                         reply_markup=keyboard)
        return

    # Запрос цены
    def go_price(self, bot, message, label_id):
        keyboard = types.ReplyKeyboardRemove()
        user_id = message.chat.id
        # Устанавливаем ожидание текстового ответа для поля "цена"
        self.users['wait'][user_id] = 4
        self.users['status'][user_id] = label_id
        bot.send_message(message.chat.id,
                         f"💰 Введите цену (не больше {PRICE_LIMIT} символов), например: “от 300 рублей/сутки”",
                         reply_markup=keyboard)
        return

    # Послать краткую метку
    def send_label(self, bot, message, label_id, dist=None):
        keyboard = types.InlineKeyboardMarkup()
        status_indicator = "✳️"
        if int(self.labels['status_label'][label_id]) == 0:
            status_indicator = "✴️"
        label_text = f"{status_indicator} {self.labels['about'][label_id].decode('utf-8')}"
        if label_id in self.labels['price']:
            label_text = label_text + f"\n💰 {self.labels['price'][label_id].decode('utf-8')}"
        a_id = int(self.labels['author'][label_id])
        username = self.users['username'][a_id].decode('utf-8')
        if dist is not None:
            dist_km = dist / 1000
            label_text = label_text + f"\n🚙 {dist_km:.2f} км"
        label_text = label_text + f"\n💬 @{username}"
        key_text = "Подробнее"
        user_id = message.chat.id
        if a_id == user_id and int(self.users['status'][user_id]) >= 0:
            key_text = "Изменить"
        keyboard.add(types.InlineKeyboardButton(text=key_text, callback_data=f"show_{label_id}"))
        bot.send_message(message.chat.id, label_text, reply_markup=keyboard)
        return

    def my_list(self, user_id):
        result = []
        for label_id in self.labels['status_label'].keys():
            if int(user_id) == int(self.labels['author'][label_id]):
                result.append(int(label_id))
        return result

    # Выявить перекресные категории
    def uni_cat(self, orig_label_id, user_id):
        c_list = json.loads(self.labels['subcategory'][orig_label_id].decode('utf-8'))
        l_list = self.my_list(user_id)
        cross_cat = []
        for label_id in l_list:
            if int(self.labels['status_label'][label_id]) == 1 and label_id != orig_label_id:
                cat_list = json.loads(self.labels['subcategory'][label_id].decode('utf-8'))
                for cat in cat_list:
                    if cat in c_list:
                        cross_cat.append(cat)
        return cross_cat

    # Послать полную метку
    def send_full_label(self, bot, message, label_id, is_edit=False):
        if label_id not in self.labels['about']:
            self.go_about(bot, message, label_id)
            return
        if label_id not in self.labels['subcategory']:
            self.go_cat(bot, message, label_id)
            return
        c_list = json.loads(self.labels['subcategory'][label_id].decode('utf-8'))
        if len(c_list) == 0:
            self.go_cat(bot, message, label_id)
            return
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        user_id = message.chat.id
        status_indicator = "✳️"
        if int(self.labels['status_label'][label_id]) == 0:
            status_indicator = "✴️"
        label_text = f"№{label_id} {status_indicator} {self.labels['about'][label_id].decode('utf-8')}"
        if label_id in self.labels['description']:
            label_text = label_text + f"\n📝 {self.labels['description'][label_id].decode('utf-8')}"
        if label_id in self.labels['price']:
            label_text = label_text + f"\n💰 {self.labels['price'][label_id].decode('utf-8')}"
        label_text = label_text + f"\n📒 {','.join(c_list)}"
        label_text = label_text + f"\n👀 {int(self.labels['views'][label_id])} просмотра"
        a_id = int(self.labels['author'][label_id])
        username = self.users['username'][a_id].decode('utf-8')
        label_text = label_text + f"\n💬 @{username}"
        cross = self.uni_cat(label_id, user_id)
        if len(cross) > 0 and int(self.labels['status_label'][label_id]) == 1:
            self.labels['status_label'][label_id] = 0
        button_list = []
        if int(self.users['status'][user_id]) < 0 or int(self.labels['author'][label_id]) != user_id:
            button_list.append(types.InlineKeyboardButton(text="Показать на карте", callback_data=f"geo_{label_id}"))
        else:
            button_list.append(types.InlineKeyboardButton(text="Изменить описание", callback_data=f"abo_{label_id}"))
            button_list.append(types.InlineKeyboardButton(text="Изменить подробности", callback_data=f"des_{label_id}"))
            button_list.append(types.InlineKeyboardButton(text="Изменить цену", callback_data=f"pri_{label_id}"))
            button_list.append(types.InlineKeyboardButton(text="Изменить категории", callback_data=f"cat_{label_id}"))
            if int(self.labels['status_label'][label_id]) == 0:
                if len(cross) == 0:
                    label_text = label_text + f"\nОбъявления снятые с публикации удаляются спустя сутки"
                    button_list.append(types.InlineKeyboardButton(text="Опубликовать", callback_data=f"pub_{label_id}"))
                else:
                    label_text = label_text + f"\n\nВы не можете создать две метки в одной подкатегории." \
                                              f" Ваши объявления уже есть здесь: {','.join(cross)}"
            if int(self.labels['status_label'][label_id]) == 1:
                button_list.append(types.InlineKeyboardButton(text="Удалить", callback_data=f"del_{label_id}"))
        keyboard.add(*button_list)
        if is_edit:
            bot.edit_message_text(chat_id=message.chat.id, message_id=message.message_id,
                                  text=label_text, reply_markup=keyboard)
        else:
            bot.send_message(message.chat.id, label_text, reply_markup=keyboard)

    # Мои метки
    def my_labels(self, bot, message):
        user_id = message.chat.id
        user_labels = self.my_list(user_id)
        self.users['status'][user_id] = 0
        for user_label_id in user_labels:
            self.send_label(bot, message, int(user_label_id))
        self.go_menu_labels(bot, message)

    # Меню менеджера меток
    def go_menu_labels(self, bot, message):
        user_id = message.chat.id
        menu_label_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)

        label_id = int(self.users['status'][user_id])
        # Сохраним username пользователя, если есть
        if message.chat.username is not None:
            self.users['username'][user_id] = message.chat.username
        # Сохраним имя пользователя, если есть
        name = ""
        if message.chat.first_name is not None:
            name = name + message.chat.first_name
        if message.chat.last_name is not None:
            name = name + " " + message.chat.last_name
        self.users['name'][user_id] = name

        if label_id > 0:
            self.send_full_label(bot, message, int(label_id))
            if int(self.users['wait'][user_id]) > 0:
                return

        menu_label_keyboard.row(types.KeyboardButton(text=self.menu_labels[0]),
                                types.KeyboardButton(text=self.menu_labels[1]),
                                types.KeyboardButton(text=self.menu_labels[2]))
        # Если задан username то покажем кнопку
        menu_label_text = f"‼️ Задайте имя пользователя в аккаунте Telegram, что бы создавать метки ‼️"
        if message.chat.username is not None:
            menu_label_keyboard.row(types.KeyboardButton(text=self.menu_labels[3], request_location=True))
            menu_label_text = f"Управляйте своими метками или создайте новую."

        bot.send_message(message.chat.id, menu_label_text, reply_markup=menu_label_keyboard)

    # Формирование списка поиска
    def get_search_list(self, message, location):
        user_id = message.chat.id
        # Перебираем все метки
        geo = {}
        for label_id in self.labels['status_label'].keys():

            # Нам нужны только опубликованые
            if int(self.labels['status_label'][label_id]) == 1:
                # Вычисляем расстояние до метки
                user_subcategories = []
                if user_id in self.users['category']:
                    user_category = self.users['category'][user_id].decode('utf-8')
                    user_subcategories = self.categories[user_category]
                    if user_id in self.users['subcategory']:
                        user_subcategory = self.users['subcategory'][user_id].decode('utf-8')
                        user_subcategories = [user_subcategory]
                if len(user_subcategories) > 0:
                    label_subcategories = json.loads(self.labels['subcategory'][label_id].decode('utf-8'))
                    cont = False
                    for sub in label_subcategories:
                        if sub in user_subcategories:
                            cont = True
                            break
                    if not cont:
                        continue

                dist = get_distance(location['longitude'], location['latitude'],
                                    float(self.labels['geo_long'][label_id]),
                                    float(self.labels['geo_lat'][label_id]))
                # Если водитель рядом, то добавляем в результирующий список
                geo[int(label_id)] = dist
        sorted_list = sorted(geo, key=geo.get)
        result = []
        for key in sorted_list:
            result.append(key)
            result.append(int(geo[key]*1000))
        return result

    # Вывод поисковых результатов
    def go_search(self, bot, message):
        user_id = message.chat.id
        s_list = json.loads(self.users['search'][user_id].decode('utf-8'))
        s_len = len(s_list)
        if s_len == 0:
            m_text = "🤷‍ Ничего не найдено! Этот раздел еще не начал наполняться."
        else:
            m_text = f"Найдено меток: {s_len // 2}"
        bot.send_message(message.chat.id, m_text)
        for i in range(LIST_STEP):
            if len(s_list) == 0:
                break
            label_id = int(s_list[0])
            self.labels['views'][label_id] = int(self.labels['views'][label_id]) + 1
            dist = int(s_list[1])
            self.send_label(bot, message, label_id, dist)
            del s_list[0]
            del s_list[0]
        if len(s_list) == 0:
            self.users['search'].delete(user_id)
        else:
            self.users['search'][user_id] = json.dumps(s_list)

    # Получены координаты тем или иным образом
    def go_location(self, bot, message, location):
        user_id = message.chat.id
        # Определение того что делать, искать или создать метку
        if int(self.users['status'][user_id]) == 0:  # Создать метку
            if user_id in self.users['username']:
                # Создаём метку
                index = int(self.common['index']) + 1
                self.common['index'] = index
                self.labels['status_label'].setex(index, 86400, 0)
                self.labels['views'][index] = 0
                self.labels['geo_long'][index] = location['longitude']
                self.labels['geo_lat'][index] = location['latitude']
                self.labels['author'][index] = user_id
                self.users['status'][user_id] = index
                self.go_menu_labels(bot, message)

        elif int(self.users['status'][user_id]) < 0:  # Поиск
            self.users['search'][user_id] = json.dumps(self.get_search_list(message, location))
            self.go_search(bot, message)
            self.go_start(bot, message, False)

    def select_cat(self, bot, message):
        keyboard = types.InlineKeyboardMarkup()

        for cat in self.categories.keys():
            keyboard.row(types.InlineKeyboardButton(text=cat, callback_data=f"ucat_{cat}"))

        bot.send_message(message.chat.id, "Выберите категорию:", reply_markup=keyboard)

    def select_sub(self, bot, message):
        keyboard = types.InlineKeyboardMarkup()
        user_id = message.chat.id
        cat = self.users['category'][user_id].decode('utf-8')
        for sub in self.categories[cat]:
            keyboard.row(types.InlineKeyboardButton(text=sub, callback_data=f"usub_{sub}"))
        bot.send_message(message.chat.id, "Выберите подкатегорию:", reply_markup=keyboard)

    def go_cat(self, bot, message, first=True):
        keyboard = types.InlineKeyboardMarkup()
        user_id = message.chat.id
        self.users['wait'][user_id] = 5

        orig_label_id = int(self.users['status'][user_id])

        l_list = self.my_list(user_id)
        st_list = []
        for label_id in l_list:
            if int(self.labels['status_label'][label_id]) == 1 and label_id != orig_label_id:
                cat_list = json.loads(self.labels['subcategory'][label_id].decode('utf-8'))
                for cat in cat_list:
                    st_list.append(cat)

        label_id = int(self.users['status'][user_id])
        if label_id not in self.labels['subcategory']:
            self.labels['subcategory'][label_id] = '[]'
        label_cats = json.loads(self.labels['subcategory'][label_id].decode('utf-8'))
        for cat, sub_list in self.categories.items():
            for sub in sub_list:
                pre = ""
                call_st = f"lcat_{sub}"
                if sub in label_cats:
                    pre = "✅ "
                elif sub in st_list:
                    pre = "🚫 "
                    call_st = "none"
                keyboard.row(types.InlineKeyboardButton(text=f"{pre}{cat}: {sub}", callback_data=call_st))
        keyboard.row(types.InlineKeyboardButton(text=f"Готово", callback_data=f"done"))
        m_text = "Следует отметить одну или несколько подкатегорий:"
        if first:
            bot.send_message(message.chat.id, m_text,
                             reply_markup=keyboard)
        else:
            bot.edit_message_text(chat_id=message.chat.id, message_id=message.message_id,
                                  text=m_text, reply_markup=keyboard)

    def deploy(self):
        bot = telebot.TeleBot(os.environ['TELEGRAM_TOKEN_LIVE'])

        # Стартовое сообщение
        @bot.message_handler(commands=['start'])
        def start_message(message):
            bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)

            self.go_start(bot, message)

        # Тест вычисления расстояния специальной командой
        @bot.message_handler(commands=['geo'])
        def geo_message(message):
            try:
                long1 = float(message.text.split(' ')[1])
                lat1 = float(message.text.split(' ')[2])
                long2 = float(message.text.split(' ')[3])
                lat2 = float(message.text.split(' ')[4])
                dist = get_distance(long1, lat1, long2, lat2)
                bot.send_message(message.chat.id, f"Расстояние {dist} км")
            except Exception as e:
                bot.send_message(message.chat.id, f"%USERNAME% какбе ошибсо {e}")

        # Вывод админу списка Айди пользователя с именем
        @bot.message_handler(commands=['list'])
        def list_message(message):
            if message.chat.id in ADMIN_LIST:
                me = "Список пользователей (ID - имя - последний вход):\n"
                for user_id in self.users['name'].keys():
                    me = me + f"{user_id.decode('utf-8')} - {self.users['name'][user_id].decode('utf-8')}" \
                              f" - {time.ctime(int(self.users['last_login'][user_id]))}\n"
                bot.send_message(message.chat.id, me)

        # Обработка всех текстовых команд
        @bot.message_handler(content_types=['text'])
        def message_text(message):
            user_id = message.chat.id

            # Обработка текстовых сообщений от пользователя, заполняю описание
            if int(self.users['wait'][user_id]) == 1 and int(self.users['status'][user_id]) > 0:
                if len(message.text) <= ABOUT_LIMIT:
                    label_id = int(self.users['status'][user_id])
                    self.labels['about'][label_id] = message.text
                    self.users['wait'][user_id] = 0
                    self.go_menu_labels(bot, message)
                    return
                else:
                    bot.send_message(message.chat.id, f"‼️ Описание слишком длинное, ограничение {ABOUT_LIMIT} символов")
                    return

            # Обработка текстовых сообщений от пользователя, заполняю подробности
            if int(self.users['wait'][user_id]) == 2 and int(self.users['status'][user_id]) > 0:
                if len(message.text) <= DESCRIPTION_LIMIT:
                    label_id = int(self.users['status'][user_id])
                    self.labels['description'][label_id] = message.text
                    self.users['wait'][user_id] = 0
                    self.go_menu_labels(bot, message)
                    return
                else:
                    bot.send_message(message.chat.id,
                                     f"‼️ Подробное описание слишком длинное, ограничение {DESCRIPTION_LIMIT} символов")
                return

            # Обработка текстовых сообщений от пользователя, заполняю цену
            if int(self.users['wait'][user_id]) == 4 and int(self.users['status'][user_id]) > 0:
                if len(message.text) <= PRICE_LIMIT:
                    label_id = int(self.users['status'][user_id])
                    self.labels['price'][label_id] = message.text
                    self.users['wait'][user_id] = 0
                    self.go_menu_labels(bot, message)
                    return
                else:
                    bot.send_message(message.chat.id,
                                     f"‼️ Описание цены слишком длинное, ограничение {PRICE_LIMIT} символов")
                    return

            # Обработка кнопки "Менеджер меток"
            if message.text == self.menu_items[4] and int(self.users['status'][user_id]) < 0:
                self.users['status'][user_id] = 0
                if user_id in self.users['search']:
                    self.users['search'].delete(user_id)
                self.go_menu_labels(bot, message)
                return

            # Обработка кнопки "Выход"
            if message.text == self.menu_labels[0]:
                self.users['status'][user_id] = -1
                self.users['wait'][user_id] = 0
                if user_id in self.users['category']:
                    self.users['category'].delete(user_id)
                if user_id in self.users['subcategory']:
                    self.users['subcategory'].delete(user_id)
                self.go_start(bot, message)
                return

            # Обработка кнопки "Что такое метка?"
            if message.text == self.menu_labels[1]:
                wtf_label = "Метка - это точка на карте, в которой происходит производство или реализация" \
                            " ваших товаров и услуг." \
                            " Например, это может быть точка продажи хлеба, сдаваемая в аренду недвижимость," \
                            " студия массажа, или, в случае, если у" \
                            " вас доставка по долине, место производства. Эта точка будет" \
                            " использоваться для навигации к вам, если это потребуется, или просто давать информацию" \
                            " о том, из какой части долины будет производиться доставка." \
                            " Разместить метку можно нажав на" \
                            " кнопку 'Создать метку', тогда метка будет создана на том же месте, где вы находитесь" \
                            " (геолокация на телефоне должна быть включена). Если вы хотите создать метку в другом" \
                            " месте, то вместо нажатия кнопки отправьте текстом координаты (через запятую)." \
                            " После создания точки на карте, укажите" \
                            " назавние и дайте краткое описание метки. Затем выберите подкатегорию (или несколько)," \
                            " в которых ваша метка будет отображаться при поиске пользователями сервиса." \
                            " В каждой подкатегории у вас может быть не более одной метки. После создания метки вы" \
                            " можете заполнить необзательные поля, такие как 'подробное описание' или 'цена'. Далее" \
                            " вам следует опубликовать метку нажав на соответствующую кнопку. Для удаления метки" \
                            " снимие её с публикации и она удалится из списка ваших меток через сутки."
                bot.send_message(message.chat.id, wtf_label)
                return

            # Обработка кнопки "Мои метки"
            if message.text == self.menu_labels[2]:
                self.my_labels(bot, message)
                return

            # Обработка кнопки "Выбрать категорию"
            if message.text == self.menu_items[2] and int(self.users['status'][user_id]) < 0:
                self.select_cat(bot, message)
                return

            # Обработка кнопки "Выбрать подкатегорию"
            if message.text == self.menu_items[3] and int(self.users['status'][user_id]) < 0:
                if user_id in self.users['category']:
                    self.select_sub(bot, message)
                    return

            # Обработка кнопки "Еще"
            if message.text == self.menu_items[0] and int(self.users['status'][user_id]) < 0:
                self.go_search(bot, message)
                self.go_start(bot, message, False)
                return

            # Обработка отправления координат текстом
            if re.fullmatch("^(-?\d+(\.\d+)?),\s*(-?\d+(\.\d+)?)$", message.text):
                location = {'longitude': float(message.text.split(',')[0]),
                            'latitude': float(message.text.split(',')[1])}
                self.go_location(bot, message, location)
                return
            # Удаление сообщений не подошедших под ожидаемые нажатия кнопок
            bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)

        # Реакция на отправление геопозиции
        @bot.message_handler(content_types=['location'])
        def message_geo(message):
            location = {'longitude': message.location.longitude, 'latitude': message.location.latitude}
            self.go_location(bot, message, location)

        # Удаление сообщений  всех типов не подошедших под ожидаемые
        @bot.message_handler(content_types=CONTENT_TYPES)
        def message_any(message):
            bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)

        @bot.callback_query_handler(func=lambda call: True)
        def callback_worker(call):
            user_id = call.message.chat.id

            # Выбираем категорию поиска
            if call.data[:4] == "ucat":
                category = call.data.split('_')[1]
                self.users['category'][user_id] = category
                if user_id in self.users['subcategory']:
                    self.users['subcategory'].delete(user_id)

                self.go_start(bot, call.message)

            # Выбираем подкатегорию поиска
            if call.data[:4] == "usub":
                subcategory = call.data.split('_')[1]
                self.users['subcategory'][user_id] = subcategory
                self.go_start(bot, call.message)

            # Показываем подробнее
            if call.data[:4] == "show":
                label_id = int(call.data.split('_')[1])
                if int(self.users['status'][user_id]) == 0:
                    self.users['status'][user_id] = label_id
                self.send_full_label(bot, call.message, int(label_id))

            # Посылаем геопозицию
            if call.data[:3] == "geo":
                label_id = int(call.data.split('_')[1])
                long = float(self.labels['geo_long'][label_id])
                lat = float(self.labels['geo_lat'][label_id])
                bot.send_location(chat_id=call.message.chat.id, longitude=long, latitude=lat)

            # Меняем описание краткое
            if call.data[:3] == "abo":
                label_id = int(call.data.split('_')[1])
                self.users['status'][user_id] = label_id
                self.go_about(bot, call.message, label_id)

            # Меняем подробное описание
            if call.data[:3] == "des":
                label_id = int(call.data.split('_')[1])
                self.users['status'][user_id] = label_id
                self.go_description(bot, call.message, label_id)

            # Меняем цену
            if call.data[:3] == "pri":
                label_id = int(call.data.split('_')[1])
                self.users['status'][user_id] = label_id
                self.go_price(bot, call.message, label_id)

            # Начинаем выбор из всех подкатегорий
            if call.data[:3] == "cat":
                label_id = int(call.data.split('_')[1])
                self.users['status'][user_id] = label_id
                self.go_cat(bot, call.message)

            # Отмечена подкатегория
            if call.data[:4] == "lcat":
                cat = call.data.split('_')[1]
                label_id = int(self.users['status'][user_id])
                categories = []
                if label_id in self.labels['subcategory']:
                    categories = json.loads(self.labels['subcategory'][label_id].decode('utf-8'))

                if cat in categories:
                    categories.remove(cat)
                else:
                    categories.append(cat)

                self.labels['subcategory'][label_id] = json.dumps(categories)

                self.go_cat(bot, call.message, False)

            # Категории выбраны
            if call.data[:4] == "done":
                self.users['wait'][user_id] = 0
                bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
                self.go_menu_labels(bot, message=call.message)

            # Снять с публикации
            if call.data[:3] == "del":
                label_id = int(call.data.split('_')[1])
                self.labels['status_label'].setex(label_id, 86400, 0)
                self.send_full_label(bot, call.message, label_id, True)

            # Опубликовать
            if call.data[:3] == "pub":
                label_id = int(call.data.split('_')[1])
                self.labels['status_label'].set(label_id, 1)
                self.send_full_label(bot, call.message, label_id, True)

            bot.answer_callback_query(call.id)

        bot.polling()


if __name__ == "__main__":
    live = Live()
    live.deploy()
