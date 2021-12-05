# coder: Olin (telegram: @whitejoe)
# use for free
# donate bitcoin: 1MFy9M3g6nxFeg8X1GDYabMtYaiuRcYJPT

import psycopg2
import json
import math
import redis
import telebot
from telebot import types
import time
import re
import os
import Levenshtein

# Устанавливаем константы
# ADMIN_LIST = [665812965]  # Список админов для спец команд (тут только whitejoe)
CLEAR_OLD_MESSAGES = False  # Чистим сообщения в чате, но создаём нагрузку
ABOUT_LIMIT = 1000  # Лимит символов в описании
SYMBOL = "₽"  # Валюта текущей системы
PLANET_RADIUS = 6371  # Радиус текущей планеты
TIME_OUT_USER = 30 * 30 * 24 * 30  # Время отсутствия активности пользователя перед удалением его меток
CONTENT_TYPES = ["text", "audio", "document", "photo", "sticker", "video", "video_note", "voice", "location", "contact",
                 "new_chat_members", "left_chat_member", "new_chat_title", "new_chat_photo", "delete_chat_photo",
                 "group_chat_created", "supergroup_chat_created", "channel_chat_created", "migrate_to_chat_id",
                 "migrate_from_chat_id", "pinned_message"]


# Вычисление расстояния между координатами
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


class Space:
    def __init__(self):

        # Подгружаем из системы ссылки на базы данных
        redis_url = os.environ['REDIS_URL_SPACE']
        # redis_url = "redis://:@localhost:6379"
        # redis_url_snapshot = os.environ['REDIS_URL_SNAPSHOT']

        # База данных пользователей
        self.users = redis.from_url(redis_url, db=1)
        '''
        username
        menu
        parent_menu
        item
        last_login
        message_id
        clean_id
        geo_long
        geo_lat
        category
        subcategory
        search_string
        cat_sel
        '''
        self.new_label = redis.from_url(redis_url, db=2)
        '''
        geo_long
        geo_lat
        about
        subcategory_list
        '''
        self.my_labels = redis.from_url(redis_url, db=3)
        self.search = redis.from_url(redis_url, db=4)

        # Подключемся к базе данных
        self.connection = psycopg2.connect(os.environ['POSTGRES_URL'])
        self.cursor = self.connection.cursor()
        '''
        0 id
        1 about
        2 photos
        3 subcategory 
        4 tags
        5 status_label
        6 geo_lat
        7 geo_long
        8 views
        9 author
        10 zoom
        11 time_added
        12 username
        '''

        # Подгрузка категорий
        with open("categories.json") as json_file:
            self.categories = json.load(json_file)

        # Подгрузка координат населённых пунктов

        with open("geo_dolina.json") as json_file:
            self.points = json.load(json_file)

        # Снепшот
        # пока отключен (без базы)
        # today = str(int(time.time()) - int(time.time()) % (3600 * 24))[:-3]
        # redis.from_url(redis_url_snapshot).set('snapshot-' + today, self.snap_data())

        # Чистка базы
        # какой базы?

    def snap_data(self):
        s_data = []
        query = "SELECT * from labels"
        self.cursor.execute(query)
        while 1:
            row = self.cursor.fetchone()
            if row is None:
                break
            label = {
                    'about': row[1],
                    'subcategory': json.dumps(row[3]),
                    #  'tags': self.labels['tags'][label_id].decode('utf-8'),
                    'geo_lat': row[6],
                    'geo_long': row[7],
                    'views': row[8],
                    'author_tg_username': f"@{row[12]}"
                    }
            s_data.append(label)
        return json.dumps(s_data)

    def get_point(self, text):
        min_r_dist = -1
        result = None
        for key, geo in self.points.items():
            r_dist = Levenshtein.distance(text, key)
            if min_r_dist < 0 or r_dist < min_r_dist:
                min_r_dist = r_dist
                result = geo
        return result

    # Обработчик всех состояний меню
    def go_menu(self, bot, message, menu_id):
        user_id = message.chat.id
        cur_time = int(time.time())

        self.users.hset(user_id, b'last_login', cur_time)
        keyboard = types.InlineKeyboardMarkup()

        self.users.hset(user_id, b'menu', menu_id)

        if menu_id == 0:  # Главное меню
            self.users.hset(user_id, b'parent_menu', menu_id)
            self.users.hset(user_id, b'item', 0)
            self.search.delete(user_id)
            self.users.hset(user_id, b'search_string', '')

            # Кнопки меню
            start_menu_items = ['Как искать❓', '🏜 Мои места',
                                '📍 Указать моё местоположение',
                                '🌎 Выбрать сферу деятельности', '📚 Выбрать направление',
                                '🏕 Поиск мест 🏕']
            keyboard_line = [types.InlineKeyboardButton(text=start_menu_items[0], callback_data=f"go_4"),
                             types.InlineKeyboardButton(text=start_menu_items[1], callback_data=f"go_5")]
            keyboard.row(*keyboard_line)
            keyboard.row(types.InlineKeyboardButton(text=start_menu_items[2], callback_data=f"go_20"))
            keyboard_line = [types.InlineKeyboardButton(text=start_menu_items[3], callback_data=f"go_1")]

            if self.users.hexists(user_id, b'category'):
                keyboard_line.append(types.InlineKeyboardButton(text=start_menu_items[4], callback_data=f"go_2"))
            keyboard.row(*keyboard_line)
            keyboard.row(types.InlineKeyboardButton(text=start_menu_items[5], callback_data=f"go_6"))
            query = "SELECT count(*) from labels"
            self.cursor.execute(query)
            count_labels = self.cursor.fetchone()[0]

            message_text = f"Записей в базе {count_labels}, начните поиск нажав на кнопку.\n" \
                           f"Канал поддержки: https://t.me/belbekspace"
            if str(user_id).encode() not in self.my_labels.keys():
                message_text = message_text + "\nДля публикации собственных творав/услуг зайдите в меню 'Мои места'" \
                                              " и создайте новое место"

            cat_s = 'Все сферы'
            if self.users.hexists(user_id, b'category'):
                cat_s = self.users.hget(user_id, b'category').decode('utf-8')
            message_text = message_text + f"\n🌎 {cat_s}"
            if self.users.hexists(user_id, b'category'):
                sub_s = 'Все направления'
                if self.users.hexists(user_id, b'subcategory'):
                    sub_s = self.users.hget(user_id, b'subcategory').decode('utf-8')
                message_text = message_text + f"\n📚 {sub_s}"
            try:
                bot.edit_message_text(chat_id=user_id, message_id=int(self.users.hget(user_id, b'message_id')),
                                      text=message_text, reply_markup=keyboard)
            except Exception as error:
                print("Error: ", error)
                bot.send_message(user_id, message_text, reply_markup=keyboard)

        elif menu_id == 1:  # Выбор сферы
            for cat in self.categories.keys():
                keyboard.row(types.InlineKeyboardButton(text=cat, callback_data=f"ucat_{cat}"))
            keyboard.row(types.InlineKeyboardButton(text="🌎 Все сферы 🌎", callback_data=f"dcat"))
            message_text = "Выберите сферу деятельности:"
            try:
                bot.edit_message_text(chat_id=user_id, message_id=int(self.users.hget(user_id, b'message_id')),
                                      text=message_text, reply_markup=keyboard)
            except Exception as error:
                print("Error: ", error)
                bot.send_message(user_id, message_text, reply_markup=keyboard)

        elif menu_id == 2:  # Выбор направления
            cat = self.users.hget(user_id, b'category').decode('utf-8')
            for sub in self.categories[cat]:
                keyboard.row(types.InlineKeyboardButton(text=sub, callback_data=f"usub_{sub}"))
            keyboard.row(types.InlineKeyboardButton(text="📚 Все направления 📚", callback_data=f"dsub"))
            message_text = "Выберите направление:"
            try:
                bot.edit_message_text(chat_id=user_id, message_id=int(self.users.hget(user_id, b'message_id')),
                                      text=message_text, reply_markup=keyboard)
            except Exception as error:
                print("Error: ", error)
                bot.send_message(user_id, message_text, reply_markup=keyboard)

        elif menu_id == 3:  # Выбор направлений места

            selected_cats = []  # Список категорий выбранного места

            temp_label_id = -1
            if int(self.users.hget(user_id, b'parent_menu')) == 8:

                sub_list = self.new_label.hget(user_id, b'subcategory_list')
                if sub_list is not None:
                    selected_cats = json.loads(sub_list.decode('utf-8'))
            else:
                temp_label_id = int(self.my_labels.zrevrange(user_id, 0, -1)[int(self.users.hget(user_id, b'item'))])
                query = "SELECT subcategory from labels WHERE id=%s"
                self.cursor.execute(query, (temp_label_id,))
                row = self.cursor.fetchone()
                selected_cats = row[0]

            banned_cats = []  # Список категорий других мест пользователя
            if str(user_id).encode() in self.my_labels.keys():
                user_labels = self.my_labels.zrange(user_id, 0, -1)
                query = "SELECT subcategory from labels WHERE id=%s"
                for label_id in user_labels:
                    if int(label_id) != temp_label_id:
                        self.cursor.execute(query, (int(label_id),))
                        row = self.cursor.fetchone()
                        for cat in row[0]:
                            banned_cats.append(cat)
            keyboard_line = []
            message_text = f"Следует отметить одно или несколько направлений.\nВыбрано {len(selected_cats)}\n"
            if self.users.hexists(user_id, b'cat_sel'):
                sub_list = self.categories.get(self.users.hget(user_id, b'cat_sel').decode('utf-8'))
                for sub in sub_list:
                    pre = ""
                    call_st = f"lcat_{sub}"
                    if sub in selected_cats:
                        pre = "✅ "
                    elif sub in banned_cats:
                        pre = "🚫 "
                        call_st = "none"
                    keyboard.row(types.InlineKeyboardButton(text=f"{pre}{sub}", callback_data=call_st))
                keyboard_line.append(types.InlineKeyboardButton(text=f"↩️ Назад",
                                                                callback_data=f"rcat"))
            else:
                message_text = f"Выберите сферу дейтельности:"
                for cat in self.categories.keys():
                    keyboard.row(types.InlineKeyboardButton(text=f"{cat}", callback_data=f"scat_{cat}"))
            keyboard_line.append(types.InlineKeyboardButton(text=f"☑️ Готово",
                                                callback_data=f"go_{int(self.users.hget(user_id, b'parent_menu'))}"))
            keyboard.row(*keyboard_line)

            try:
                bot.edit_message_text(chat_id=user_id, message_id=int(self.users.hget(user_id, b'message_id')),
                                      text=message_text, reply_markup=keyboard)
            except Exception as error:
                print("Error: ", error)
                bot.send_message(user_id, message_text, reply_markup=keyboard)

        elif menu_id == 4:  # Помощь "как искать?"
            message_text = "Перед поиском имеет смысл выбрать сферу деятельности мест (🌎), которые вы хотите увидеть." \
                           " Для уточнения можете выбрать направление (📚). Что бы начать поиск мест нажмите на кнопку" \
                           " внизу. Результаты будут показаны на экране по одному в порядке увеличения расстояния от" \
                           " Вас. Что бы связаться с создателем места нажмите на его имя возле значка 💬." \
                           " Вы сможете найти машину от сервиса @BelbekTaxiBot к месту или заказать оттуда" \
                           " доставку нажатием кнопок под описанием места. Там же Вы найдёте кнопки для просмотра" \
                           " места на карте и его фото. Перелистывать результаты поиска можно кнопками в внизу меню." \
                           " Для завершения поиска нажмите ОК. Для обсуждения любых вопросов связанных работой с" \
                           " ботом, обратитесь в канал поддержки @belbekspace"

            keyboard.row(types.InlineKeyboardButton(text=f"Спасибо",
                                                callback_data=f"go_{int(self.users.hget(user_id, b'parent_menu'))}"))
            try:
                bot.edit_message_text(chat_id=user_id, message_id=int(self.users.hget(user_id, b'message_id')),
                                      text=message_text, reply_markup=keyboard)
            except Exception as error:
                print("Error: ", error)
                bot.send_message(user_id, message_text, reply_markup=keyboard)

        elif menu_id == 5:  # Меню редактирования
            self.users.hset(user_id, b'parent_menu', menu_id)
            self.users.hdel(user_id, b'cat_sel')

            item = int(self.users.hget(user_id, b'item'))
            self.new_label.delete(user_id)
            menu_edit_items = ['Как создавать места❓',
                               '❓', '🏜 Новое место',
                               '📝', '🗺', '📸', '📚', '❌',
                               '⏪', '🆗', '⏩', '🔄', '⏮']
            keyboard_line = []
            message_text = "Здесь будут доступны для редактирования все ваши места, но пока их у вас нет"
            if str(user_id).encode() in self.my_labels.keys():
                keyboard_line.append(types.InlineKeyboardButton(text=menu_edit_items[1], callback_data=f"go_16"))
                query = "SELECT * from labels WHERE id = %s"
                label_id = int(self.my_labels.zrevrange(user_id, 0, -1)[int(self.users.hget(user_id, b'item'))])

                self.cursor.execute(query, (label_id,))
                row = self.cursor.fetchone()
                message_text = f"🏕 {item + 1} из {self.my_labels.zcard(user_id)} Ваших мест:\n\n" \
                               f"📝 {row[1]}\n🆔 {row[0]}\n📚 {','.join(row[3])}\n👀 {row[8]}\n" \
                               f"💬 @{message.chat.username}"
            else:
                keyboard.row(types.InlineKeyboardButton(text=menu_edit_items[0], callback_data=f"go_16"))

            keyboard_line.append(types.InlineKeyboardButton(text=menu_edit_items[2], callback_data=f"go_8"))

            keyboard.row(*keyboard_line)
            if str(user_id).encode() in self.my_labels.keys():
                keyboard_line = [types.InlineKeyboardButton(text=menu_edit_items[3], callback_data=f"go_14"),
                                 types.InlineKeyboardButton(text=menu_edit_items[4], callback_data=f"go_20"),
                                 types.InlineKeyboardButton(text=menu_edit_items[5], callback_data=f"go_13"),
                                 types.InlineKeyboardButton(text=menu_edit_items[6], callback_data=f"go_3"),
                                 types.InlineKeyboardButton(text=menu_edit_items[7], callback_data=f"go_15")]
                keyboard.row(*keyboard_line)
            keyboard_line = []

            if item > 0:
                keyboard_line.append(types.InlineKeyboardButton(text=menu_edit_items[8],
                                                                callback_data=f"select_{item-1}"))
            else:
                keyboard_line.append(types.InlineKeyboardButton(text=menu_edit_items[12],
                                                                callback_data=f"none"))
            keyboard_line.append(types.InlineKeyboardButton(text=menu_edit_items[9], callback_data=f"go_0"))
            if str(user_id).encode() in self.my_labels.keys():

                if item < self.my_labels.zcard(user_id) - 1:
                    keyboard_line.append(types.InlineKeyboardButton(text=menu_edit_items[10],
                                                                    callback_data=f"select_{item+1}"))
                else:
                    keyboard_line.append(types.InlineKeyboardButton(text=menu_edit_items[11],
                                                                    callback_data=f"select_0"))
            keyboard.row(*keyboard_line)

            try:
                bot.edit_message_text(chat_id=user_id, message_id=int(self.users.hget(user_id, b'message_id')),
                                      text=message_text, reply_markup=keyboard)
            except Exception as error:
                print("Error: ", error)
                bot.send_message(user_id, message_text, reply_markup=keyboard)

        elif menu_id == 6:  # Меню просмотра результатов поиска
            self.users.hset(user_id, b'parent_menu', menu_id)
            menu_search_items = ['🚕➡️⛺️', '⬅️🚕⛺️',
                                 '🗺 Карта', 'Фото 📸',
                                 '⏪', '🆗', '⏩', '🔄', '⏮']
            new_search = False
            if str(user_id).encode() not in self.search.keys():
                self.do_search(message)

                self.users.hset(user_id, b'item', 0)
                new_search = True

            message_text = "🤷‍ Ничего не найдено! Этот раздел еще не начал наполняться."
            if str(user_id).encode() in self.search.keys():

                item = int(self.users.hget(user_id, b'item'))
                query = "SELECT * from labels WHERE id=%s"

                label_id = int(self.search.zrange(user_id, 0, -1)[item])
                self.cursor.execute(query, (label_id,))
                row = self.cursor.fetchone()
                message_text = f"🏕 {item + 1} из {self.search.zcard(user_id)} результатов поиска\n"
                if self.users.hexists(user_id, b'category'):
                    message_text = message_text + f"🌎 {self.users.hget(user_id, b'category').decode('utf-8')}\n"
                if self.users.hexists(user_id, b'subcategory'):
                    message_text = message_text + f"📚 {self.users.hget(user_id, b'subcategory').decode('utf-8')}\n"
                search_s = self.users.hget(user_id, b'search_string', 0).decode('utf-8')
                if len(search_s) > 0:
                    message_text = message_text + f"📖 '{search_s}' (поиск по словам еще не работает)\n"
                message_text = message_text + f"\n📝 {row[1]}\n🆔 {row[0]}\n📚 {','.join(row[3])}\n👀 {row[8]}\n" \
                                              f"🚙 {float(self.search.zscore(user_id, label_id))/1000:.1f} км\n" \
                                              f"💬 @{row[12]}"

                keyboard_line = [types.InlineKeyboardButton(text=menu_search_items[0], callback_data=f"go_13"),
                                 types.InlineKeyboardButton(text=menu_search_items[1], callback_data=f"go_13")]
                keyboard.row(*keyboard_line)
                keyboard_line = [types.InlineKeyboardButton(text=menu_search_items[2], callback_data=f"go_10"),
                                 types.InlineKeyboardButton(text=menu_search_items[3], callback_data=f"go_13")]
                keyboard.row(*keyboard_line)
                keyboard_line = []
                if item > 0:
                    keyboard_line.append(types.InlineKeyboardButton(text=menu_search_items[4],
                                                                    callback_data=f"select_{item - 1}"))
                else:
                    keyboard_line.append(types.InlineKeyboardButton(text=menu_search_items[8],
                                                                    callback_data=f"none"))
                keyboard_line.append(types.InlineKeyboardButton(text=menu_search_items[5], callback_data=f"go_0"))
                if item < self.search.zcard(user_id) - 1:
                    keyboard_line.append(types.InlineKeyboardButton(text=menu_search_items[6],
                                                                    callback_data=f"select_{item + 1}"))
                else:
                    keyboard_line.append(types.InlineKeyboardButton(text=menu_search_items[7],
                                                                    callback_data=f"select_0"))
                keyboard.row(*keyboard_line)
            else:
                keyboard.row(types.InlineKeyboardButton(text=menu_search_items[5], callback_data=f"go_0"))

            if new_search:

                bot.send_message(user_id, message_text, reply_markup=keyboard)
                try:
                    bot.delete_message(chat_id=message.chat.id, message_id=int(self.users.hget(user_id, b'message_id')))
                except Exception as error:
                    print("Error del message: ", error)
            else:
                try:
                    bot.edit_message_text(chat_id=user_id, message_id=int(self.users.hget(user_id, b'message_id')),
                                          text=message_text, reply_markup=keyboard)
                except Exception as error:
                    print("Error: ", error)
                    bot.send_message(user_id, message_text, reply_markup=keyboard)

        elif menu_id == 7:  # Задать начальную локацию

            geo_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            geo_keyboard.row(types.KeyboardButton(text="Отправить геопозицию", request_location=True))
            message_text = "Боту следует знать, где Вы находитесь, что бы выдавать результы поиска в порядке удаления" \
                           " от Вас, для этого отправьте свою геопозицию нажав на кнопку ниже или " \
                           " напишите текстом название села" \
                           " (также Вы можете прислать координаты через запятую)."

            bot.send_message(user_id, message_text, reply_markup=geo_keyboard)
            bot.delete_message(chat_id=message.chat.id, message_id=int(self.users.hget(user_id, b'message_id')))
            next_id = int(self.users.hget(user_id, b'message_id')) + 1
            self.users.hset(user_id, b'message_id', next_id)
            self.users.hset(user_id, b'parent_menu', 0)

        elif menu_id == 8:  # Меню создания нового места
            if message.chat.username is not None:
                #  self.users.hset(user_id, b'username', message.chat.username)
                self.users.hset(user_id, b'parent_menu', menu_id)
                self.users.hdel(user_id, b'cat_sel')
                if str(user_id).encode() not in self.new_label.keys():
                    self.new_label.hset(user_id, b'geo_lat', self.users.hget(user_id, b'geo_lat'))
                    self.new_label.hset(user_id, b'geo_long', self.users.hget(user_id, b'geo_long'))
                can_create = self.new_label.hexists(user_id, 'about') and self.new_label.hexists(user_id,
                                                                                                 'subcategory_list')
                menu_new_label_items = ['📝 Описание', '🗺 Карта', '📸 Фото', '📚 Направления',
                                        'Опубликовать', '❌']
                about_text = f"‼️ Необходимо заполнить описание (📝), лимит {ABOUT_LIMIT} символов"
                if self.new_label.hexists(user_id, 'about'):
                    about_text = self.new_label.hget(user_id, 'about').decode('utf-8')

                cat_text = "‼️ Необходимо выбрать одно или несколько направлений (📚) "
                if self.new_label.hexists(user_id, 'subcategory_list'):
                    cat_text = ','.join(json.loads(self.new_label.hget(user_id,
                                                                       'subcategory_list').decode('utf-8')))
                message_text = f"Описание 📝: {about_text}\n\nНаправления 📚: {cat_text}"
                keyboard_line = [types.InlineKeyboardButton(text=menu_new_label_items[0], callback_data=f"go_14"),
                                 types.InlineKeyboardButton(text=menu_new_label_items[1], callback_data=f"go_20")]
                keyboard.row(*keyboard_line)
                keyboard_line = [types.InlineKeyboardButton(text=menu_new_label_items[2], callback_data=f"go_13"),
                                 types.InlineKeyboardButton(text=menu_new_label_items[3], callback_data=f"go_3")]
                keyboard.row(*keyboard_line)
                keyboard_line = []
                if can_create:
                    keyboard_line.append(types.InlineKeyboardButton(text=menu_new_label_items[4],
                                                                    callback_data=f"go_9"))
                keyboard_line.append(types.InlineKeyboardButton(text=menu_new_label_items[5], callback_data=f"go_5"))
                keyboard.row(*keyboard_line)
                try:
                    bot.edit_message_text(chat_id=user_id, message_id=int(self.users.hget(user_id, b'message_id')),
                                          text=message_text, reply_markup=keyboard)
                except Exception as error:
                    print("Error: ", error)
                    bot.send_message(user_id, message_text, reply_markup=keyboard)
            else:
                message_text = f"‼️ Задайте имя пользователя в аккаунте Telegram," \
                               f" что бы бот мог направить Вам гостей и жителей долины ‼️ Для этого зайдите в" \
                               f" настройки, справа сверху нажмите 'Изменить' и заполните" \
                               f" поле 'Имя пользователя'."
                keyboard.row(
                    types.InlineKeyboardButton(text=f"☑️ Готово",
                                               callback_data=f"go_{int(self.users.hget(user_id, b'parent_menu'))}"))
                try:
                    bot.edit_message_text(chat_id=user_id, message_id=int(self.users.hget(user_id, b'message_id')),
                                          text=message_text, reply_markup=keyboard)
                except Exception as error:
                    print("Error: ", error)
                    bot.send_message(user_id, message_text, reply_markup=keyboard)

        elif menu_id == 9:  # Уведомление создание места
            self.users.hset(user_id, b'item', 0)
            message_text = " 🥳 Новое место появилось в Belbek.Space ! 🎊"

            query = "INSERT INTO labels (about, subcategory, geo_lat, geo_long, author, time_added, username) " \
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)"
            self.cursor.execute(query, (self.new_label.hget(user_id, b'about').decode('utf-8'),
                                        json.loads(self.new_label.hget(user_id,
                                                                       b'subcategory_list').decode('utf-8')),
                                        float(self.new_label.hget(user_id, b'geo_lat')),
                                        float(self.new_label.hget(user_id, b'geo_long')),
                                        user_id,
                                        cur_time,
                                        message.chat.username))

            self.connection.commit()

            query = "SELECT LASTVAL()"
            self.cursor.execute(query)
            row = self.cursor.fetchone()
            label_id = row[0]
            self.my_labels.zadd(user_id, {label_id: cur_time})

            keyboard.row(types.InlineKeyboardButton(text="Замечательно", callback_data=f"go_5"))
            try:
                bot.edit_message_text(chat_id=user_id, message_id=int(self.users.hget(user_id, b'message_id')),
                                      text=message_text, reply_markup=keyboard)
            except Exception as error:
                print("Error: ", error)
                bot.send_message(user_id, message_text, reply_markup=keyboard)

        elif menu_id == 10:  # Показать на карте

            label_id = int(self.search.zrange(user_id, 0, -1)[int(self.users.hget(user_id, b'item'))])
            query = "SELECT geo_lat, geo_long from labels WHERE id=%s"

            self.cursor.execute(query, (label_id,))
            row = self.cursor.fetchone()

            lat = row[0]
            long = row[1]

            keyboard.row(types.InlineKeyboardButton(text="OK",
                                                callback_data=f"dgo_{int(self.users.hget(user_id, b'parent_menu'))}"))
            bot.send_location(chat_id=message.chat.id, longitude=long, latitude=lat, reply_markup=keyboard)
            bot.delete_message(chat_id=message.chat.id, message_id=int(self.users.hget(user_id, b'message_id')))

        elif menu_id == 11:  # Показ такси
            pass

        elif menu_id == 12:  # Показ доставки через такси
            pass

        elif menu_id == 13:  # Уведомление "в разработке"
            message_text = "Эта часть бота в разработке. Простите, но придётся подождать"
            keyboard.row(types.InlineKeyboardButton(text=f"Конечно, я подожду, спасибо",
                                                callback_data=f"go_{int(self.users.hget(user_id, b'parent_menu'))}"))
            try:
                bot.edit_message_text(chat_id=user_id, message_id=int(self.users.hget(user_id, b'message_id')),
                                      text=message_text, reply_markup=keyboard)
            except Exception as error:
                print("Error: ", error)
                bot.send_message(user_id, message_text, reply_markup=keyboard)

        elif menu_id == 14:  # Изменение описания места
            message_text = f"Описание вашего места:\n\n📝 "

            if int(self.users.hget(user_id, b'parent_menu')) == 5:
                label_id = int(self.my_labels.zrevrange(user_id, 0, -1)[int(self.users.hget(user_id, b'item'))])
                query = "SELECT about from labels WHERE id = %s"
                self.cursor.execute(query, (label_id,))
                row = self.cursor.fetchone()
                message_text = message_text + row[0]

            elif int(self.users.hget(user_id, b'parent_menu')) == 8:

                if self.new_label.hexists(user_id, b'about'):
                    message_text = message_text + self.new_label.hget(user_id, b'about').decode('utf-8')
                else:
                    message_text = message_text + " 🤷🏽 пусто!  "

            message_text = message_text + "\n\n Отправьте текстом новое описание или нажмите 'Готово'"

            keyboard.row(types.InlineKeyboardButton(text=f"☑️ Готово",
                                                callback_data=f"go_{int(self.users.hget(user_id, b'parent_menu'))}"))
            try:
                bot.edit_message_text(chat_id=user_id, message_id=int(self.users.hget(user_id, b'message_id')),
                                      text=message_text, reply_markup=keyboard)
            except Exception as error:
                print("Error: ", error)
                bot.send_message(user_id, message_text, reply_markup=keyboard)

        elif menu_id == 15:  # Подтверждение удаления
            message_text = "Вы действительно хотите ❌ убрать ❌ это место из нашего космоса?"
            keyboard.row(types.InlineKeyboardButton(text="Нет, пусть остаётся 👍",
                                                callback_data=f"go_{int(self.users.hget(user_id, b'parent_menu'))}"))
            keyboard.row(types.InlineKeyboardButton(text="Да, убираю 👎", callback_data=f"del_label"))

            try:
                bot.edit_message_text(chat_id=user_id, message_id=int(self.users.hget(user_id, b'message_id')),
                                      text=message_text, reply_markup=keyboard)
            except Exception as error:
                print("Error: ", error)
                bot.send_message(user_id, message_text, reply_markup=keyboard)

        elif menu_id == 16:  # Помощь "как создать место?"

            message_text = f" Место 🏜️ - это точка на карте, в которой происходит производство или реализация" \
                           f" ваших товаров и услуг." \
                           f" Например, это может быть точка продажи хлеба, сдаваемая в аренду недвижимость," \
                           f" студия массажа, или, в случае, если у" \
                           f" вас доставка по долине, место производства. Эта точка будет" \
                           f" использоваться для навигации к вам, если это потребуется, или просто давать информацию" \
                           f" о том, из какой части долины будет производиться доставка." \
                           f" Для создания нового места нажмите на кнопку 'Новое место', в открывшемся меню Вам будет" \
                           f" предложено заполнить описание (лимит {ABOUT_LIMIT} символов). Также Вам следует" \
                           f" указать как минимум одно из направлений деятельности из предложенных ботом." \
                           f" Вы можете создать не больше одного места в каждом из направлений, но место можете иметь" \
                           f" несколько направлений. После этого у Вас появится возможность опубликовать место." \
                           f" При желании Вы можете загрузить фото и изменить геолокацию публикуемого места" \
                           f" (по-умолчанию выставляется Ваше текущее местоположение). После создания вы сможете" \
                           f" вносить любые изменения. Обсудить набор сфер и направлений деятельности, оставить" \
                           f" замечания по работе и обнаруженные ошибке Вы можете в канале поддержки @belbekspace "

            keyboard.row(
                types.InlineKeyboardButton(text=f"Спасибо, Джо, очень помог!",
                                           callback_data=f"go_{int(self.users.hget(user_id, b'parent_menu'))}"))
            try:
                bot.edit_message_text(chat_id=user_id, message_id=int(self.users.hget(user_id, b'message_id')),
                                      text=message_text, reply_markup=keyboard)
            except Exception as error:
                print("Error: ", error)
                bot.send_message(user_id, message_text, reply_markup=keyboard)
        elif menu_id == 17:  #
            pass
        elif menu_id == 18:  #
            pass
        elif menu_id == 19:  #
            pass
        elif menu_id == 20:  # Геолокация текущая

            if int(self.users.hget(user_id, b'parent_menu')) == 5:
                button_text = "Да, это здесь"
                label_id = int(self.my_labels.zrevrange(user_id, 0, -1)[int(self.users.hget(user_id, b'item'))])
                query = "SELECT geo_lat, geo_long from labels WHERE id=%s"
                self.cursor.execute(query, (label_id,))
                row = self.cursor.fetchone()
                lat = row[0]
                long = row[1]
            elif int(self.users.hget(user_id, b'parent_menu')) == 8:
                button_text = "Да, это здесь"
                lat = self.new_label.hget(user_id, b'geo_lat')
                long = self.new_label.hget(user_id, b'geo_long')
            else:
                lat = float(self.users.hget(user_id, b'geo_lat'))
                long = float(self.users.hget(user_id, b'geo_long'))
                button_text = "Да, я здесь"

            keyboard.row(types.InlineKeyboardButton(text=button_text, callback_data=f"dgo_23"))
            keyboard.row(types.InlineKeyboardButton(text="Изменить", callback_data=f"dgo_21"))
            bot.send_location(chat_id=message.chat.id, longitude=long, latitude=lat, reply_markup=keyboard)
            try:
                bot.delete_message(chat_id=message.chat.id, message_id=int(self.users.hget(user_id, b'message_id')))
            except Exception as error:
                print("Error del geo-request message: ", error)

        elif menu_id == 21:  # Предупреждение об локации
            message_text = "Не забудьте включить геолокацию, если хотите что бы бот сам определил Ваше местонахождение"
            keyboard.row(types.InlineKeyboardButton(text=f"Хорошо", callback_data=f"go_22"))
            try:
                bot.edit_message_text(chat_id=user_id, message_id=int(self.users.hget(user_id, b'message_id')),
                                      text=message_text, reply_markup=keyboard)
            except Exception as error:
                print("Error: ", error)
                bot.send_message(user_id, message_text, reply_markup=keyboard)

        elif menu_id == 22:  # Смена локации

            geo_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            geo_keyboard.row(types.KeyboardButton(text="Отправить геопозицию", request_location=True))
            message_text = "Отправьте геопозицию нажав кнопку ниже или напишите текстом название села" \
                           " (также Вы можете прислать координаты через запятую). " \
                           "/cancel для отмены"

            bot.send_message(user_id, message_text, reply_markup=geo_keyboard)
            bot.delete_message(chat_id=message.chat.id, message_id=int(self.users.hget(user_id, b'message_id')))
            next_id = int(self.users.hget(user_id, b'message_id')) + 1
            self.users.hset(user_id, b'message_id', next_id)

        elif menu_id == 23:  # Уведомление о смене локации
            message_text = "Геолокация подтвеждена"
            keyboard.row(types.InlineKeyboardButton(text=f"Ок",
                                                callback_data=f"go_{int(self.users.hget(user_id, b'parent_menu'))}"))
            try:
                bot.edit_message_text(chat_id=user_id, message_id=int(self.users.hget(user_id, b'message_id')),
                                      text=message_text, reply_markup=keyboard)
            except Exception as error:
                print("Error: ", error)
                bot.send_message(user_id, message_text, reply_markup=keyboard)

    # Формирование списка поиска
    def do_search(self, message):

        user_id = message.chat.id
        # Перебираем все метки

        # поиск по слову попозже будет
        query = "SELECT * from labels"  # пересечение категорий ввести и поиск по слову!
        self.cursor.execute(query)
        while 1:
            row = self.cursor.fetchone()
            if row is None:
                break

            label_id = row[0]
            # это говнокод фильтрующий пересечение категорий, запрос фильтрации через запрос в бд еще не освоил
            # короче, переделаю потом, а пока так
            label_cat_list = []
            label_sub_list = row[3]

            for label_sub in label_sub_list:
                for cat, sub_list in self.categories.items():
                    if label_sub in sub_list:
                        label_cat_list.append(cat)
            if not self.users.hexists(user_id, b'category') or \
                    self.users.hget(user_id, b'category').decode('utf-8') in label_cat_list:
                if not self.users.hexists(user_id, b'subcategory') or \
                        self.users.hget(user_id, b'subcategory').decode('utf-8') in label_sub_list:
                    dist = int(1000*get_distance(float(self.users.hget(user_id, b'geo_lat')),
                                                 float(self.users.hget(user_id, b'geo_long')),
                                                 row[6], row[7]))
                    self.search.zadd(user_id, {label_id: dist})

    # Получены координаты тем или иным образом
    def go_location(self, bot, message, location):
        user_id = message.chat.id
        if int(self.users.hget(user_id, b'menu')) in [7, 22]:
            if int(self.users.hget(user_id, b'parent_menu')) == 5:
                label_id = int(self.my_labels.zrevrange(user_id, 0, -1)[int(self.users.hget(user_id, b'item'))])

                query = "UPDATE labels SET geo_lat = %s, geo_long = %s WHERE id = %s"
                self.cursor.execute(query, (location['latitude'], location['longitude'], label_id))
                self.connection.commit()
            elif int(self.users.hget(user_id, b'parent_menu')) == 8:
                self.new_label.hset(user_id, b'geo_lat', location['latitude'])
                self.new_label.hset(user_id, b'geo_long', location['longitude'])
            else:
                self.users.hset(user_id, b'geo_lat', location['latitude'])
                self.users.hset(user_id, b'geo_long', location['longitude'])
            self.go_menu(bot, message, 20)

    def service(self):
        for b_user_id in self.my_labels.keys():
            self.my_labels.delete(b_user_id)

        query_sel = "SELECT id, time_added, author from labels"
        self.cursor.execute(query_sel)
        while 1:
            row_res = self.cursor.fetchone()
            if row_res is None:
                break
            self.my_labels.zadd(int(row_res[2]), {row_res[0]: row_res[1]})

    def deploy(self):
        self.service()
        bot = telebot.TeleBot(os.environ['TELEGRAM_TOKEN_SPACE'])

        # Стартовое сообщение
        @bot.message_handler(commands=['start'])
        def start_message(message):
            user_id = message.chat.id

            welcome_text = f"Приветствую Вас Жители и Гости Бельбексокой Долины!" \
                           f" Этот бот - агрегатор товаров и услуг этого замечательного уголка Крыма. Здесь Вы" \
                           f" можете найти всё для жизни и отдыха, а также разместить информацию о своей" \
                           f" деятельности. Каждое объявление - это место в Долине. Место продажи товаров, мастерская" \
                           f" или что-нибудь еще в зависимости от сферы деятельности."
            keyboard = types.InlineKeyboardMarkup()
            self.users.hset(user_id, b'menu', -1)

            keyboard.row(types.InlineKeyboardButton(text=f"Хорошо, приступим!", callback_data=f"go_7"))
            bot.send_message(user_id, welcome_text, reply_markup=keyboard)
            mess_id = 2
            if self.users.hexists(int(user_id), b'message_id'):
                mess_id = int(self.users.hget(int(user_id), b'message_id'))
            for i in range(3):
                if mess_id - i < message.message_id:
                    try:
                        bot.delete_message(chat_id=message.chat.id, message_id=mess_id - i)
                    except Exception as e:
                        print("Error: ", e)
            bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)

        # Отмена ввода
        @bot.message_handler(commands=['cancel'])
        def cancel_message(message):
            user_id = message.chat.id
            if int(self.users.hget(user_id, b'menu')) == 22:
                self.go_menu(bot, message, 20)
            bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)

        # Обработка всех текстовых команд
        @bot.message_handler(content_types=['text'])
        def message_text(message):
            user_id = message.chat.id

            # Введена строка для поиска
            if int(self.users.hget(user_id, b'menu')) == 0:
                self.users.hset(user_id, b'search_string', message.text)
                self.go_menu(bot, message, 6)

            # Введена описание
            if int(self.users.hget(user_id, b'menu')) == 14:
                about = message.text[:ABOUT_LIMIT]
                if int(self.users.hget(user_id, b'parent_menu')) == 5:

                    label_id = int(self.my_labels.zrevrange(user_id, 0, -1)[int(self.users.hget(user_id, b'item'))])
                    query = "UPDATE labels SET about = %s WHERE id = %s"
                    self.cursor.execute(query, (about, label_id))
                    self.connection.commit()
                elif int(self.users.hget(user_id, b'parent_menu')) == 8:
                    self.new_label.hset(user_id, b'about', about)

                self.go_menu(bot, message, 14)
                '''
                try:
                    bot.delete_message(chat_id=message.chat.id,
                                       message_id=int(self.users.hget(user_id, b'message_id')))
                except Exception as e:
                    print("Error: ", e)
                '''

            # Обработка отправления текстом координат или названия пункта
            if int(self.users.hget(user_id, b'menu')) in [7, 22]:
                if re.fullmatch("^(-?\d+(\.\d+)?),\s*(-?\d+(\.\d+)?)$", message.text):
                    location = {'latitude': float(message.text.split(',')[0]),
                                'longitude': float(message.text.split(',')[1])}
                else:
                    location = self.get_point(message.text)
                self.go_location(bot, message, location)

            # Удаление сообщений
            bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)

        # Реакция на отправление геопозиции
        @bot.message_handler(content_types=['location'])
        def message_geo(message):
            location = {'longitude': message.location.longitude, 'latitude': message.location.latitude}
            self.go_location(bot, message, location)
            bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)

        # Удаление сообщений всех типов
        @bot.message_handler(content_types=CONTENT_TYPES)
        def message_any(message):
            bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)

        @bot.callback_query_handler(func=lambda call: True)
        def callback_worker(call):
            user_id = call.message.chat.id

            # Фиксируем ID сообщения
            self.users.hset(user_id, b'message_id', call.message.message_id)  # Фиксируем ID сообщения

            # Чистим старые сообщения
            if not self.users.hexists(user_id, b'clean_id'):
                self.users.hset(user_id, b'clean_id', call.message.message_id - 1)

            message_id_clean = int(self.users.hget(user_id, b'clean_id'))
            while message_id_clean < call.message.message_id - 1:
                message_id_clean += 1
                if CLEAR_OLD_MESSAGES:
                    try:
                        bot.delete_message(chat_id=call.message.chat.id, message_id=message_id_clean)
                    except Exception as e:
                        print("Error: ", e)
            self.users.hset(user_id, b'clean_id', call.message.message_id - 1)  # Фиксируем ID сообщения

            # Передаём управление главной функции
            if call.data[:2] == "go":
                self.go_menu(bot, call.message, int(call.data.split('_')[1]))

            # Передаём управление главной функции с удалением предыдущего сообщения
            if call.data[:3] == "dgo":

                self.go_menu(bot, call.message, int(call.data.split('_')[1]))
                bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)

            # Выбираем сферу для поиска
            if call.data[:4] == "ucat":
                category = call.data.split('_')[1]
                self.users.hdel(user_id, b'subcategory')
                self.users.hset(user_id, b'category', category)
                self.go_menu(bot, call.message, int(self.users.hget(user_id, b'parent_menu')))

            # Выбираем все сферы для поиска
            if call.data == "dcat":
                self.users.hdel(user_id, b'category')
                self.users.hdel(user_id, b'subcategory')
                self.go_menu(bot, call.message, int(self.users.hget(user_id, b'parent_menu')))

            # Выбираем направление для поиска
            if call.data[:4] == "usub":
                subcategory = call.data.split('_')[1]
                self.users.hset(user_id, b'subcategory', subcategory)
                self.go_menu(bot, call.message, int(self.users.hget(user_id, b'parent_menu')))

            # Выбираем все направления для поиска
            if call.data == "dsub":
                self.users.hdel(user_id, b'subcategory')
                self.go_menu(bot, call.message, int(self.users.hget(user_id, b'parent_menu')))

            # Выбран item
            if call.data[:6] == "select":
                new_item = int(call.data.split('_')[1])
                self.users.hset(user_id, b'item', new_item)
                self.go_menu(bot, call.message, int(self.users.hget(user_id, b'parent_menu')))

            # Отмечена подкатегория
            if call.data[:4] == "lcat":
                cat = call.data.split('_')[1]

                categories = []  # Извлекаем список направлений у метки
                if int(self.users.hget(user_id, b'parent_menu')) == 5:

                    label_id = int(self.my_labels.zrevrange(user_id, 0, -1)[int(self.users.hget(user_id, b'item'))])
                    query = "SELECT subcategory FROM labels WHERE id = %s"
                    self.cursor.execute(query, (label_id,))
                    row = self.cursor.fetchone()
                    categories = row[0]
                elif int(self.users.hget(user_id, b'parent_menu')) == 8:
                    if self.new_label.hexists(user_id, b'subcategory_list'):
                        categories = json.loads(self.new_label.hget(user_id,
                                                                    b'subcategory_list').decode('utf-8'))

                if cat in categories:
                    categories.remove(cat)
                else:
                    categories.append(cat)

                # Сохраняем список направлений
                if int(self.users.hget(user_id, b'parent_menu')) == 5:
                    if len(categories) > 0:

                        label_id = int(self.my_labels.zrevrange(user_id, 0, -1)[int(self.users.hget(user_id, b'item'))])
                        query = "UPDATE labels SET subcategory = %s WHERE id = %s"
                        self.cursor.execute(query, (categories, label_id))
                        self.connection.commit()
                elif int(self.users.hget(user_id, b'parent_menu')) == 8:
                    if len(categories) > 0:
                        self.new_label.hset(user_id, b'subcategory_list', json.dumps(categories))
                    else:
                        self.new_label.hdel(user_id, b'subcategory_list')

                self.go_menu(bot, call.message, 3)

            if call.data == "rcat":
                self.users.hdel(user_id, b'cat_sel')
                self.go_menu(bot, call.message, 3)

            if call.data[:4] == "scat":
                sel_category = call.data.split('_')[1]
                self.users.hset(user_id, b'cat_sel', sel_category)
                self.go_menu(bot, call.message, 3)

            if call.data == "del_label":
                # Удаляю место из базы и из списка меток пользователя
                label_id = int(self.my_labels.zrevrange(user_id, 0, -1)[int(self.users.hget(user_id, b'item'))])
                query = "DELETE FROM labels WHERE id = %s"
                self.cursor.execute(query, (label_id,))
                self.connection.commit()
                if self.my_labels.zcard(user_id) == 1:
                    self.my_labels.delete(user_id)
                else:
                    self.my_labels.zrem(user_id, label_id)
                self.users.hset(user_id, b'item', 0)
                self.go_menu(bot, call.message, int(self.users.hget(user_id, b'parent_menu')))

            bot.answer_callback_query(call.id)

        bot.polling()
        #  try:
        #    bot.polling()
        #  except Exception as error:
        #    print("Error polling: ", error)


if __name__ == "__main__":
    space = Space()
    space.deploy()
