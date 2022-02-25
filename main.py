# belbek.space product by belbek.tech
# (telegram: @whitejoe)
# use for free
# donate bitcoin: 1MFy9M3g6nxFeg8X1GDYabMtYaiuRcYJPT

import psycopg2
import json
import redis
import telebot
from telebot import types
import time
import datetime
import os
import re
import Levenshtein

# Устанавливаем константы
BOTCHAT_ID = -1001508419451  # Айди чата для ботов
DEBUG_ID = 665812965  # Дебаг whitejoe
ABOUT_LIMIT = 1000  # Лимит символов в описании
DS_ID = "belbek_space"
FORMAT_TIME = "%d.%m.%y %H:%M"
FORMAT_DESC = "ДД.ММ.ГГ ЧЧ:ММ"


def is_date(ts, date_code):
    day_sec = 24 * 60 * 60
    wd = time.localtime(ts).tm_wday
    cur_time = time.time()
    x = time.localtime(cur_time)
    mid_night = cur_time - x.tm_sec - x.tm_min * 60 - x.tm_hour * 60 * 60
    if date_code == 0:
        return ts < mid_night and (ts > mid_night - day_sec * 7)
    if date_code == 1:
        return ts > mid_night and (ts < mid_night + day_sec * 1)
    if date_code == 2:
        return (ts > mid_night + day_sec * 1) and (ts < mid_night + day_sec * 2)
    if date_code == 3:
        return ts > mid_night and (ts < mid_night + day_sec * (7 - wd))
    if date_code == 4:
        return (ts > mid_night + day_sec * (7 - wd)) and (ts < mid_night + day_sec * (14 - wd))
    if date_code == 5:
        return ts > mid_night + day_sec * (14 - wd)


class Space:
    def __init__(self):

        # Подгружаем из системы ссылки на базы данных
        redis_url = os.environ['REDIS_URL_SPACE']
        # redis_url = "redis://:@localhost:6379"

        # База данных пользователей
        self.users = redis.from_url(redis_url, db=1)
        '''
        username
          edit
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
        # self.my_labels = redis.from_url(redis_url, db=3)
        self.search = redis.from_url(redis_url, db=4)
        self.deep_space = redis.from_url(redis_url, db=5)
        self.views = redis.from_url(redis_url, db=6)

        # Подключемся к базе данных
        self.connection = psycopg2.connect(os.environ['POSTGRES_URL'])
        self.cursor = self.connection.cursor()
        '''
        0 id
        1 about
        2 subcategory 
        3 tags
        4 status_label
        5 geo_lat
        6 geo_long
        7 views
        8 author
        9 zoom
        10 time_added
        11 username
        12 start_time
        13 photo
        '''

        # Подгрузка категорий
        self.categories = {}
        self.cat_stat = {}
        with open("categories.json") as json_file:
            cat_dict = json.load(json_file)
            for cat, scat in cat_dict.items():
                self.categories[cat] = dict.fromkeys(scat, 0)
        self.events_count = {}
        self.events_total = 0
        self.total = 0
        self.date_code = {"Последняя неделя": 0,
                          "Сегодня": 1,
                          "Завтра": 2,
                          "На этой неделе": 3,
                          "На следующей неделе": 4,
                          "Через 2 недели и далее": 5}
        self.renew_cats()

        self.edit_items = ['📝 Описание', '📚 Направления', '❌ Удалить', '🕰 Дата и время', '📸 Фото', '🗺 Карта']
        self.additional_scat = ['🛸 Другие площадки 🛰', '🌎 Все сферы 🌎', '📚 Все направления 📚', "🕰 Мероприятия 🕰"]
        self.limit_per_second = 5
        self.limit_counter = 0
        self.last_send_time = int(time.time())
        self.hellow_message = f"Канал поддержки: https://t.me/belbekspace\n" \
                              f"Такси и доставка: @BelbekTaxiBot\n" \
                              f"Для нового поиска отправьте любое слово, дату или фразу\n" \
                              f"Бот будет искать и присылать затеи пока не увидит команду /stop"
        self.day_today = -1

        with open("geo_dolina.json") as json_file:
            self.points = json.load(json_file)

    # Определяем введённый населённый пункт и возвращаем его координаты
    def get_point(self, text):
        min_r_dist = -1
        result = None
        for key, geo in self.points.items():
            r_dist = Levenshtein.distance(text, key)
            if min_r_dist < 0 or r_dist < min_r_dist:
                min_r_dist = r_dist
                result = key, geo
            if min_r_dist == 0:
                break
        return result

    def save_views(self):
        for bitem_id in self.views.keys():
            item_id = int(bitem_id)
            query = "SELECT views from labels WHERE id=%s"
            self.cursor.execute(query, (item_id,))
            row = self.cursor.fetchone()
            svid = int(self.views[bitem_id])
            if row is not None and svid > 0:
                vs = row[0] + svid
                query = "UPDATE labels SET views = %s WHERE id = %s"
                self.cursor.execute(query, (vs, item_id))
                self.connection.commit()
                self.views[bitem_id] = 0

    def renew_cats(self):
        def check_date(date_event):
            res = False
            for evnt, code in self.date_code.items():
                if is_date(date_event, code):
                    self.events_count[evnt] += 1
                    res = True
            return res

        for cat, ucats in self.categories.items():
            for ucat in ucats.keys():
                self.categories[cat][ucat] = 0
            self.cat_stat[cat] = 0
        for evt in self.date_code.keys():
            self.events_count[evt] = 0
        self.events_total = 0
        self.total = len(self.deep_space.keys())
        query = "SELECT * from labels"
        self.cursor.execute(query)
        while 1:
            row = self.cursor.fetchone()
            if row is None:
                break
            self.total += 1
            label_sub_list = row[2]
            for cat, scat in self.categories.items():
                yes_cat = False
                for uscat in scat.keys():
                    for label_sub in label_sub_list:
                        if label_sub == uscat:
                            self.categories[cat][uscat] += 1
                            yes_cat = True
                if yes_cat:
                    self.cat_stat[cat] += 1
            if row[12] > 0:
                check_date(row[12])
        for ds_id in self.deep_space.keys():
            if self.deep_space.hexists(ds_id, b'start_time'):
                if check_date(int(self.deep_space.hget(ds_id, b'start_time'))):
                    self.events_total += 1

    def check_th(self):
        while 1:
            cur_time = int(time.time())
            if self.last_send_time < cur_time:
                self.limit_counter = 0
                self.last_send_time = cur_time
            self.limit_counter += 1
            if self.limit_counter <= self.limit_per_second:
                return cur_time
            time.sleep(1)

    def send_item(self, bot, user_id, item_id, is_command=False, is_edited=False, is_ds=False, message_id=None):
        def inc_views(iid):
            ovs = 0
            if self.views.exists(iid):
                ovs = int(self.views.get(iid))
            self.views.set(iid, ovs + 1)
            return int(self.views.get(iid))

        item_menu = [[], []]
        photo_id = None
        if is_ds:
            message_text = f"📝 {self.deep_space.hget(item_id, b'text').decode('utf-8')}"
            if self.deep_space.hexists(item_id, b'start_time'):
                start_time = datetime.datetime.fromtimestamp(int(self.deep_space.hget(item_id, b'start_time')))

                message_text = message_text + f"\n🕰 {start_time.strftime(FORMAT_TIME)}"
            else:
                message_text = message_text + f"\n{self.additional_scat[0]}"
            # f"🆔 {item_id.decode('utf-8')}\n" \
            if self.deep_space.hexists(item_id, b'photo'):
                photo_id = self.deep_space.hget(item_id, b'photo').decode('utf-8')
            if self.deep_space.hexists(item_id, b'geo_lat'):
                item_menu[0].append(types.InlineKeyboardButton(text="🗺 На карте",
                                                               callback_data=f"loc_{item_id}"))

        else:
            query = "SELECT * from labels WHERE id=%s"
            cursor = self.connection.cursor()
            cursor.execute(query, (item_id,))
            row = cursor.fetchone()
            message_text = "Удалено"
            if row is not None:
                if type(row[13]) is str:
                    photo_id = row[13]
                if is_command:
                    message_text = f"{item_id}@{DS_ID}"
                    if row[12] > 0:
                        start_time = datetime.datetime.fromtimestamp(row[12])
                        message_text = message_text + f" {start_time.strftime(FORMAT_TIME)}"
                    if type(row[5]) is float:
                        message_text = message_text + f" {row[5]}, {row[6]}"
                    message_text = message_text + f" {row[1]}"
                else:
                    message_text = row[1]
                    vs = int(row[7])
                    if not is_edited:
                        inc_views(item_id)
                    if self.views.exists(item_id):
                        vs += int(self.views.get(item_id))
                    message_text = f"📝 {message_text}\n👀 {vs}"
                    if row[12] > 0:
                        start_time = datetime.datetime.fromtimestamp(row[12])

                        message_text = message_text + f"\n🕰 {start_time.strftime(FORMAT_TIME)}"
                    else:
                        message_text = message_text + f"\n📚 {','.join(row[2])}"
                    #  🆔 {row[0]}@{DS_ID}\n"

                if is_edited:
                    message_text = message_text + f"\n\nЧто бы изменить затею, нажмите одну из кнопок под сообщением"
                    item_menu[0].append(types.InlineKeyboardButton(text=self.edit_items[0],
                                                                   callback_data=f"edit_{item_id}"))
                    if row[12] > 0:
                        item_menu[0].append(types.InlineKeyboardButton(text=self.edit_items[3],
                                                                       callback_data=f"time_{item_id}"))
                    else:
                        item_menu[0].append(types.InlineKeyboardButton(text=self.edit_items[1],
                                                                       callback_data=f"cat_{item_id}"))
                    item_menu[1].append(types.InlineKeyboardButton(text=self.edit_items[4],
                                                                   callback_data=f"pic_{item_id}"))
                    item_menu[1].append(types.InlineKeyboardButton(text=self.edit_items[5],
                                                                   callback_data=f"map_{item_id}"))
                    item_menu[1].append(types.InlineKeyboardButton(text=self.edit_items[2],
                                                                   callback_data=f"del_{item_id}"))
                elif not is_command and type(row[5]) is float:
                    item_menu[0].append(types.InlineKeyboardButton(text="🗺 На карте",
                                                                   callback_data=f"loc_{item_id}"))

            elif is_command:
                message_text = f"{item_id}@{DS_ID}"

        keyboard = types.InlineKeyboardMarkup()
        keyboard.row(*item_menu[0])
        keyboard.row(*item_menu[1])
        self.check_th()
        if is_command:
            user_id = BOTCHAT_ID
        try:
            message_id = message_id + 1
            message_id = message_id - 1
            if photo_id is None:
                bot.edit_message_text(chat_id=user_id, message_id=message_id, text=message_text, reply_markup=keyboard)
            else:
                bot.edit_message_caption(caption=message_text, chat_id=user_id, message_id=message_id,
                                         reply_markup=keyboard)
        except Exception as error:
            print("Error: ", error)
            if photo_id is None:
                bot.send_message(user_id, message_text, reply_markup=keyboard)
            else:
                bot.send_photo(user_id, photo_id, message_text, reply_markup=keyboard)

    # Обработчик всех состояний меню
    def go_menu(self, bot, message, menu_id):
        user_id = message.chat.id

        keyboard = types.InlineKeyboardMarkup()

        if menu_id == 0:  # Редактирование и создание итема

            message_text = f"Пришлите описание затеи (лимит {ABOUT_LIMIT} символов),\n‼️ укажите контакты ‼️"
            if message.chat.username is not None:
                message_text = message_text + f" (например, ссылку на свой телеграмм:" \
                                              f" https://t.me/{message.chat.username})"
            message_text = message_text + f"\nДля отмены введите /cancel"
            self.check_th()
            bot.send_message(user_id, message_text, reply_markup=types.ReplyKeyboardRemove())

        elif menu_id == 1:  # Выбор сферы для поиска
            self.users.hdel(user_id, "category")
            self.users.hdel(user_id, "subcategory")
            for cat in self.categories.keys():
                keyboard.row(types.InlineKeyboardButton(text=f"{cat} ({self.cat_stat[cat]})",
                                                        callback_data=f"ucat_{cat}"))
            add_row_text = f"{self.additional_scat[0]} ({len(self.deep_space.keys())})"
            keyboard.row(types.InlineKeyboardButton(text=add_row_text, callback_data=f"ds_cat"))
            keyboard.row(types.InlineKeyboardButton(text=f"{self.additional_scat[3]} ({self.events_total})",
                                                    callback_data=f"events"))
            keyboard.row(types.InlineKeyboardButton(text=f"{self.additional_scat[1]} ({self.total})",
                                                    callback_data=f"all"))
            message_text = "Выберите сферу деятельности:"
            bot.send_message(user_id, message_text, reply_markup=keyboard)

        elif menu_id == 2:  # Выбор направления для поиска
            cat = self.users.hget(user_id, b'category').decode('utf-8')
            for sub, scol in self.categories[cat].items():
                keyboard.row(types.InlineKeyboardButton(text=f"{sub} ({scol})", callback_data=f"usub_{sub}"))
            keyboard.row(types.InlineKeyboardButton(text="📚 Все направления 📚", callback_data=f"dsub"))
            message_text = "Выберите направление:"
            try:
                bot.edit_message_text(chat_id=user_id, message_id=message.message_id,
                                      text=message_text, reply_markup=keyboard)
            except Exception as error:
                print("Error: ", error)
                bot.send_message(user_id, message_text, reply_markup=keyboard)

        elif menu_id == 3:  # Редактирование направлений

            item_id = int(self.users.hget(user_id, b'item'))
            query = "SELECT subcategory from labels WHERE id=%s"
            self.cursor.execute(query, (item_id,))
            row = self.cursor.fetchone()
            selected_cats = row[0]
            photo_id = None
            if type(message.photo) is list:
                photo_id = message.photo[0].file_id
            keyboard_line = []
            message_text = f"Выберите одно или несколько направлений:\n" \
                           f"Выбрано {len(selected_cats)}\n"
            if self.users.hexists(user_id, b'cat_sel'):
                sub_list = self.categories.get(self.users.hget(user_id, b'cat_sel').decode('utf-8')).keys()
                for sub in sub_list:
                    pre = ""
                    call_st = f"lcat_{sub}"
                    if sub in selected_cats:
                        pre = "✅ "
                    keyboard.row(types.InlineKeyboardButton(text=f"{pre}{sub}", callback_data=call_st))
                keyboard_line.append(types.InlineKeyboardButton(text=f"↩️ Назад",
                                                                callback_data=f"rcat"))
            else:
                message_text = f"Для удобства поиска Вы можете отметить одно или несколько направлений.\n" \
                               f"Выберите сферу дейтельности:"
                keyboard_line.append(types.InlineKeyboardButton(text=self.additional_scat[3],
                                                                callback_data=f"time_{item_id}"))
                for cat in self.categories.keys():
                    keyboard.row(types.InlineKeyboardButton(text=f"{cat}", callback_data=f"scat_{cat}"))
            keyboard_line.append(types.InlineKeyboardButton(text=f"☑️ Готово",
                                 callback_data=f"done_{item_id}"))
            keyboard.row(*keyboard_line)
            try:
                if photo_id is None:
                    bot.edit_message_text(chat_id=user_id, message_id=message.message_id, text=message_text,
                                          reply_markup=keyboard)
                else:
                    bot.edit_message_caption(caption=message_text, chat_id=user_id, message_id=message.message_id,
                                             reply_markup=keyboard)
            except Exception as error:
                print("Error: ", error)
                if photo_id is None:
                    bot.send_message(user_id, message_text, reply_markup=keyboard)
                else:
                    bot.send_photo(user_id, photo_id, message_text, reply_markup=keyboard)

        elif menu_id == 4:  # Подтверждение удаления
            message_text = "Вы действительно хотите ❌ убрать ❌ эту затею из нашего космоса?"
            keyboard.row(types.InlineKeyboardButton(text="Да, убираю 👎", callback_data=f"cdel_label"))
            keyboard.row(types.InlineKeyboardButton(text="Нет, пусть остаётся 👍",
                                                    callback_data=f"item_{int(self.users.hget(user_id, b'item'))}"))
            photo_id = None
            if type(message.photo) is list:
                photo_id = message.photo[0].file_id
            try:
                if photo_id is None:
                    bot.edit_message_text(chat_id=user_id, message_id=message.message_id, text=message_text,
                                          reply_markup=keyboard)
                else:
                    bot.edit_message_caption(caption=message_text, chat_id=user_id, message_id=message.message_id,
                                             reply_markup=keyboard)
            except Exception as error:
                print("Error: ", error)
                if photo_id is None:
                    bot.send_message(user_id, message_text, reply_markup=keyboard)
                else:
                    bot.send_photo(user_id, photo_id, message_text, reply_markup=keyboard)
        elif menu_id == 5:  # Редактирование времени итема
            now_time = datetime.datetime.fromtimestamp(int(time.time()))
            message_text = f"Пришлите дату и время меоприятия (в формате {FORMAT_DESC}), например:\n" \
                           f"{now_time.strftime(FORMAT_TIME)}\nЧто бы удалить время введите /no_time\n" \
                           f"Для отмены - /cancel"
            self.check_th()
            bot.send_message(user_id, message_text, reply_markup=types.ReplyKeyboardRemove(),
                             reply_to_message_id=int(self.users.hget(user_id, b'message_id')))
        elif menu_id == 6:  # Поиск мероприятий
            for menu_item, date_code in self.date_code.items():
                text_item = f"{menu_item} ({self.events_count[menu_item]})"
                keyboard.row(types.InlineKeyboardButton(text=text_item, callback_data=f"ctime_{date_code}"))
            message_text = "Выберите дату начала мероприятия или просто оптравьте текстом (ДД.ММ.ГГ)"
            try:
                bot.edit_message_text(chat_id=user_id, message_id=message.message_id,
                                      text=message_text, reply_markup=keyboard)
            except Exception as error:
                print("Error: ", error)
                bot.send_message(user_id, message_text, reply_markup=keyboard)
        elif menu_id == 7:  # Редактирование фото
            message_text = f"Пришлите фотографию и она будет прикреплена к вашей затее\n" \
                           f"Что бы убрать фото, отправьте /no_pic\n" \
                           f"Для отмены - /cancel"
            self.check_th()
            bot.send_message(user_id, message_text, reply_markup=types.ReplyKeyboardRemove(),
                             reply_to_message_id=int(self.users.hget(user_id, b'message_id')))
        elif menu_id == 8:  # Редактирование геометки
            message_text = f"Пришлите геопозицию или отпавьте координаты текстом\n" \
                           f"Что бы убрать геопозицию, отправьте /no_map\n" \
                           f"Для отмены - /cancel"
            self.check_th()
            loc_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            loc_keyboard.row(types.KeyboardButton(text="Отправить геопозицию", request_location=True))
            bot.send_message(user_id, message_text, reply_markup=loc_keyboard,
                             reply_to_message_id=int(self.users.hget(user_id, b'message_id')))

    def my_items(self, bot, message):
        user_id = message.chat.id
        count = 0
        # Перебираем все метки
        query = "SELECT * from labels"
        self.cursor.execute(query)
        while 1:
            row = self.cursor.fetchone()
            if row is None:
                break
            item_id = row[0]
            if user_id == row[8]:
                self.send_item(bot, user_id, item_id, is_edited=True)
                count += 1

    def research(self, bot, item_id, if_cat=True, if_text=True, if_date=True):
        for user_id in self.search.keys():
            s_string = self.search.get(user_id).decode('utf-8')
            if if_cat and s_string == "cat":
                self.do_search(bot, None, item_fix=item_id, user_id=int(user_id))
            if if_text and s_string[:5] == "text:":
                self.do_search_text(bot, None, s_string[5:], item_fix=item_id, user_id=int(user_id))
            if if_date and s_string[:5] == "date:":
                self.do_search_date(bot, None, int(s_string[5:]), item_fix=item_id, user_id=int(user_id))

    # Формирование списка поиска из категорий
    def do_search(self, bot, message, item_fix=None, user_id=None):
        def send_ds():
            cnt = 0
            if item_fix is not None:
                self.send_item(bot, user_id, item_fix, is_ds=True)
            else:
                for i_id in self.deep_space.keys():
                    self.send_item(bot, user_id, i_id, is_ds=True)
                    cnt += 1
            return cnt

        if user_id is None:
            user_id = message.chat.id
        cur_time = int(time.time())
        self.users.hset(user_id, b'last_login', cur_time)
        count = 0
        keyboard = types.InlineKeyboardMarkup()
        if not self.users.hexists(user_id, "category"):
            return
        category = self.users.hget(user_id, "category").decode("utf-8")
        # Deep space
        if category == self.additional_scat[0]:
            count = send_ds()
        elif category == self.additional_scat[1]:
            count = send_ds()
            if item_fix is None or type(item_fix) is int:
                if item_fix is None:
                    query = "SELECT * from labels"
                    self.cursor.execute(query)
                else:
                    query = "SELECT * from labels WHERE id = %s"
                    self.cursor.execute(query, (item_fix,))
                while 1:
                    row = self.cursor.fetchone()
                    if row is None:
                        break
                    item_id = row[0]
                    self.send_item(bot, user_id, item_id)
                    count += 1
        elif item_fix is None or type(item_fix) is int:
            # Формируем список необходимых категорий

            target_subcategory_list = self.categories[category].keys()
            if self.users.hexists(user_id, "subcategory"):
                sub_c = self.users.hget(user_id, "subcategory").decode('utf-8')
                target_subcategory_list = [sub_c]
            # Перебираем метки
            if item_fix is None:
                query = "SELECT * from labels"
                self.cursor.execute(query)
            else:
                query = "SELECT * from labels WHERE id = %s"
                self.cursor.execute(query, (item_fix,))

            while 1:
                row = self.cursor.fetchone()

                if row is None:
                    break

                item_id = row[0]
                label_sub_list = row[2]
                if len(set(label_sub_list).intersection(set(target_subcategory_list))) > 0:
                    self.send_item(bot, user_id, item_id)
                    count += 1
        if item_fix is None:
            category = self.users.hget(user_id, "category").decode("utf-8")
            message_text = f"🔎 {category}"
            if category != self.additional_scat[0] and self.users.hexists(user_id, "subcategory"):
                sub_c = self.users.hget(user_id, "subcategory").decode('utf-8')
                message_text = message_text + f"\n{sub_c}"
            message_text = message_text + f"\nНайдено затей: {count}"
            try:
                self.check_th()
                bot.edit_message_text(chat_id=user_id, message_id=message.message_id,
                                      text=message_text, reply_markup=keyboard)
            except Exception as error:
                bot.send_message(chat_id=user_id, text=message_text, reply_markup=keyboard)
                print("Error: ", error)
            after_message = self.hellow_message
            self.check_th()
            bot.send_message(user_id, after_message)
            self.search.set(user_id, "cat")

    # Формирование списка поиска из текста
    def do_search_text(self, bot, message, text, item_fix=None, user_id=None):
        def is_contain(phrase: [], about_text: str):
            for word in phrase:
                if word.lower() == "сегодня":
                    search_time = datetime.datetime.fromtimestamp(int(time.time()))
                    word = search_time.strftime('%d.%m.%y')
                if word.lower() == "завтра":
                    search_time = datetime.datetime.fromtimestamp(24*60*60 + int(time.time()))
                    word = search_time.strftime('%d.%m.%y')
                if about_text.lower().find(word.lower()) < 0:
                    return False
            return True

        def check_ds(label_id):
            if self.deep_space.exists(label_id):
                about_text = self.deep_space.hget(label_id, b'text').decode('utf-8')
                if self.deep_space.hexists(label_id, b'start_time'):
                    s_time = datetime.datetime.fromtimestamp(int(self.deep_space.hget(label_id, b'start_time')))
                    about_text = f"{s_time.strftime(FORMAT_TIME)} " + about_text
                if is_contain(words, about_text):
                    self.send_item(bot, user_id, label_id, is_ds=True)
                    return True
            return False

        if user_id is None:
            user_id = message.chat.id
        count = 0
        cur_time = int(time.time())
        self.users.hset(user_id, b'last_login', cur_time)
        pre_words = text.split(' ')
        words = []
        for w in pre_words:
            if len(w) > 2:
                words.append(w)

        if len(words) > 0:
            if item_fix is None or type(item_fix) is int:
                if item_fix is None:
                    query = "SELECT * from labels"
                    self.cursor.execute(query)
                else:
                    query = "SELECT * from labels WHERE id = %s"
                    self.cursor.execute(query, (item_fix,))
                while 1:
                    row = self.cursor.fetchone()
                    if row is None:
                        break
                    item_id = row[0]
                    about = row[1]
                    if row[12] > 0:
                        start_time = datetime.datetime.fromtimestamp(row[12])
                        about = f"{start_time.strftime(FORMAT_TIME)} " + about
                    if is_contain(words, about):
                        self.send_item(bot, user_id, item_id)
                        count += 1

            if item_fix is None:
                for item_id in self.deep_space.keys():
                    if check_ds(item_id):
                        count += 1
            else:
                check_ds(item_fix)
        if item_fix is None:
            message_text = "🔎 " + ', '.join(words) + f"\nНайдено затей: {count}\n" + self.hellow_message
            self.check_th()
            bot.send_message(user_id, message_text)
            self.search.set(user_id, f"text:{text}")

    # Поиск событий
    def do_search_date(self, bot, message, date_code, item_fix=None, user_id=None):
        if user_id is None:
            user_id = message.chat.id
        cur_time = int(time.time())
        self.users.hset(user_id, b'last_login', cur_time)
        count = 0
        if item_fix is None or type(item_fix) is int:
            if item_fix is None:
                query = "SELECT * from labels WHERE start_time > 0"
                self.cursor.execute(query)
            else:
                query = "SELECT * from labels WHERE id = %s AND start_time > 0"
                self.cursor.execute(query, (item_fix,))
            while 1:
                row = self.cursor.fetchone()
                if row is None:
                    break
                item_id = row[0]
                start_time = int(row[12])
                if is_date(start_time, date_code):
                    self.send_item(bot, user_id, item_id)
                    count += 1

        if item_fix is None:
            for item_id in self.deep_space.keys():
                if self.deep_space.hexists(item_id, b'start_time'):
                    start_time = int(self.deep_space.hget(item_id, b'start_time'))
                    if is_date(start_time, date_code):
                        self.send_item(bot, user_id, item_id, is_ds=True)
                        count += 1
            keyboard = types.InlineKeyboardMarkup()
            message_text = "🔎 "
            for ds, code in self.date_code.items():
                if date_code == code:
                    message_text = message_text + ds
                    break
            message_text = message_text + f"\nНайдено затей: {count}"
            try:
                bot.edit_message_text(chat_id=user_id, message_id=message.message_id,
                                      text=message_text, reply_markup=keyboard)
            except Exception as error:
                print("Error: ", error)
                bot.send_message(chat_id=user_id, text=message_text, reply_markup=keyboard)
            after_message = self.hellow_message
            self.check_th()
            bot.send_message(user_id, after_message)
            self.search.set(user_id, f"date:{date_code}")
        else:
            if self.deep_space.hexists(item_fix, b'start_time'):
                start_time = int(self.deep_space.hget(item_fix, b'start_time'))
                if is_date(start_time, date_code):
                    self.send_item(bot, user_id, item_fix, is_ds=True)

    # Устанавливаем локацию у затеи
    def go_location(self, bot, message, location):
        user_id = message.chat.id
        item_id = int(self.users.hget(user_id, b'item'))
        query = "UPDATE labels SET geo_lat = %s, geo_long = %s WHERE id = %s"
        self.cursor.execute(query, (location['latitude'], location['longitude'], item_id))
        self.connection.commit()
        self.send_item(bot, user_id, item_id, is_command=True)
        self.check_th()
        bot.send_message(user_id, "Место затеи обновлено")
        self.users.hset(user_id, b'edit', 0)
        bot.send_location(user_id, location['latitude'], location['longitude'],
                          reply_to_message_id=int(self.users.hget(user_id, b'message_id')))

    def deploy(self):
        bot = telebot.TeleBot(os.environ['TELEGRAM_TOKEN_SPACE'])

        if len(self.deep_space.keys()) == 0:
            bot.send_message(BOTCHAT_ID, "/get_all_items")

        # Стартовое сообщение
        @bot.message_handler(commands=['start'])
        def start_message(message):
            user_id = message.chat.id

            welcome_text = f"Для управления ботом используйте меню в нижней левой части экрана\n"

            welcome_text = welcome_text + self.hellow_message

            self.users.hset(user_id, b'item', -1)
            self.users.hset(user_id, b'edit', 0)
            self.check_th()
            bot.send_message(user_id, welcome_text)

        @bot.message_handler(commands=['get_all_items'])
        def get_all_message(message):
            user_id = message.chat.id

            if user_id == BOTCHAT_ID:
                query = "SELECT id from labels"
                self.cursor.execute(query)
                while 1:
                    row = self.cursor.fetchone()
                    if row is None:
                        break
                    self.send_item(bot, user_id, row[0], is_command=True)

        @bot.message_handler(commands=['new_item'])
        def new_item(message):
            user_id = message.chat.id
            self.users.hset(user_id, b'item', 0)
            self.users.hset(user_id, b'edit', 1)
            self.users.hdel(user_id, b'message_id')
            self.go_menu(bot, message, 0)

        @bot.message_handler(commands=['my_items'])
        def my_items(message):
            self.users.hset(message.chat.id, b'edit', 0)
            self.my_items(bot, message)

        @bot.message_handler(commands=['search'])
        def browse(message):
            self.users.hset(message.chat.id, b'edit', 0)
            self.go_menu(bot, message, 1)

        # Отмена ввода
        @bot.message_handler(commands=['cancel'])
        def cancel_message(message):
            user_id = message.chat.id
            if int(self.users.hget(user_id, b'edit')) > 0:
                self.users.hset(user_id, b'edit', 0)
                self.check_th()
                bot.send_message(user_id, "Ввод отменён")

        # Остановка поиска
        @bot.message_handler(commands=['stop'])
        def stop_search(message):
            user_id = message.chat.id
            self.users.hset(message.chat.id, b'edit', 0)
            if self.search.exists(user_id):
                self.search.delete(user_id)
                self.check_th()
                bot.send_message(user_id, "Поиск остановлен")

        # Удаление времени
        @bot.message_handler(commands=['no_time'])
        def no_time(message):
            user_id = message.chat.id
            item_id = int(self.users.hget(user_id, b'item'))
            query = "UPDATE labels SET start_time = %s WHERE id = %s"
            self.cursor.execute(query, (0, item_id))
            self.connection.commit()
            self.send_item(bot, user_id, item_id, is_command=True)
            self.check_th()
            bot.send_message(user_id, f"Вермя начала затеи удалено, что бы вернуть время,"
                                      f" следует отметить затею как {self.additional_scat[3]}")
            try:
                bot.delete_message(user_id, int(self.users.hget(user_id, b'message_id')))
            finally:
                self.send_item(bot, user_id, item_id, is_edited=True)

        # Удаление фото
        @bot.message_handler(commands=['no_pic'])
        def no_pic(message):
            user_id = message.chat.id
            item_id = int(self.users.hget(user_id, b'item'))
            query = "UPDATE labels SET photo = %s WHERE id = %s"
            self.cursor.execute(query, (None, item_id,))
            self.connection.commit()
            self.send_item(bot, user_id, item_id, is_command=True)
            self.check_th()
            bot.send_message(user_id, f"Фото удалено, вы всегда можете его загрузить другое")
            try:
                bot.delete_message(user_id, int(self.users.hget(user_id, b'message_id')))
            finally:
                self.send_item(bot, user_id, item_id, is_edited=True)

        # Удаление локации
        @bot.message_handler(commands=['no_map'])
        def no_pic(message):
            user_id = message.chat.id
            item_id = int(self.users.hget(user_id, b'item'))
            query = "UPDATE labels SET geo_lat = %s, geo_long = %s WHERE id = %s"
            self.cursor.execute(query, (0, 0, item_id))
            self.connection.commit()
            self.send_item(bot, user_id, item_id, is_command=True)
            self.check_th()
            bot.send_message(user_id, f"Затея на карте больше не отмечена, вы всегда можете отметить её снова")
            try:
                bot.delete_message(user_id, int(self.users.hget(user_id, b'message_id')))
            finally:
                self.send_item(bot, user_id, item_id, is_edited=True)

        # Обработка сообщений из deep space
        def ds_message(m_text, photo_id=None):
            end_pos = m_text.find(' ')
            ds_id = m_text[:end_pos]
            if ds_id.find('@') < 0:
                return
            if end_pos < 0:
                self.deep_space.delete(m_text)
                return
            start_pos = end_pos + 1
            start_time = None
            try:
                end_pos = m_text.find(' ', start_pos)
                end_pos = m_text.find(' ', end_pos + 1)
                start_str = m_text[start_pos:end_pos]
                start_time = int(time.mktime(time.strptime(start_str, FORMAT_TIME)))
                start_pos = end_pos + 1
            except ValueError:
                if self.deep_space.exists(ds_id):
                    self.deep_space.hdel(ds_id, b'start_time')
            end_pos = m_text.find(' ', start_pos)
            end_pos = m_text.find(' ', end_pos + 1)
            latitude = None
            longitude = None
            if re.fullmatch("^(-?\d+(\.\d+)?),\s*(-?\d+(\.\d+)?)$", m_text[start_pos:end_pos]):
                latitude = float(m_text[start_pos:end_pos].split(',')[0])
                longitude = float(m_text[start_pos:end_pos].split(',')[1])
                start_pos = end_pos + 1
            item = m_text[start_pos:]
            if len(item) == 0:
                return
            if start_time is not None:
                self.deep_space.hset(ds_id, b'start_time', start_time)
            if latitude is not None:
                self.deep_space.hset(ds_id, b'geo_lat', latitude)
                self.deep_space.hset(ds_id, b'geo_long', longitude)
            else:
                self.deep_space.hdel(ds_id, b'geo_lat')
                self.deep_space.hdel(ds_id, b'geo_long')
            if photo_id is not None:
                self.deep_space.hset(ds_id, b'photo', photo_id)
            else:
                self.deep_space.hdel(ds_id, b'photo')
            self.deep_space.hset(ds_id, b'text', item)
            self.research(bot, ds_id)
            self.renew_cats()
            return

        # Реакция на отправление геопозиции
        @bot.message_handler(content_types=['location'])
        def message_geo(message):
            user_id = message.chat.id
            if int(self.users.hget(user_id, b'edit')) == 4:
                location = {'longitude': message.location.longitude, 'latitude': message.location.latitude}
                self.go_location(bot, message, location)

        # Обработка фото
        @bot.message_handler(content_types=['photo'])
        def message_photo(message):
            user_id = message.chat.id
            if message.chat.id == BOTCHAT_ID:
                ds_message(message.caption, message.photo[0].file_id)
                return
            if int(self.users.hget(user_id, b'edit')) == 3:
                self.users.hset(user_id, b'edit', 0)
                item_id = int(self.users.hget(user_id, b'item'))
                query = "UPDATE labels SET photo = %s WHERE id = %s"
                self.cursor.execute(query, (message.photo[0].file_id, item_id))
                self.connection.commit()
                self.send_item(bot, user_id, item_id, is_command=True)
                self.check_th()
                bot.send_message(user_id, "Фото затеи обновлено")
                try:
                    bot.delete_message(user_id, int(self.users.hget(user_id, b'message_id')))
                finally:
                    self.send_item(bot, user_id, item_id, is_edited=True)

        # Обработка всех текстовых команд
        @bot.message_handler(content_types=['text'])
        def message_text(message):
            user_id = message.chat.id
            cur_time = int(time.time())

            # Check new day
            if time.localtime().tm_mday != self.day_today:
                x = time.localtime(cur_time)
                mid_night = cur_time - x.tm_sec - x.tm_min * 60 - x.tm_hour * 60 * 60
                self.day_today = time.localtime().tm_mday
                for buser_id in self.search.keys():
                    ss = self.search.get(buser_id).decode('utf-8')
                    if self.users.hexists(buser_id, b'last_login'):
                        login_time = int(self.users.hget(buser_id, b'last_login'))
                        if login_time < mid_night:
                            if ss[:5] == "date:":
                                self.do_search_date(bot, None, int(ss[5]), item_fix=None, user_id=int(buser_id))
                self.save_views()
            if message.chat.id == BOTCHAT_ID:
                ds_message(message.text)
                return

            if not self.users.hexists(user_id, b'edit'):
                bot.send_message(user_id, "Бот обновился, нажмите /start")
                return

            if int(self.users.hget(user_id, b'edit')) == 0:
                self.do_search_text(bot, message, message.text)

            elif int(self.users.hget(user_id, b'edit')) == 1:
                self.users.hset(user_id, b'edit', 0)
                item_id = int(self.users.hget(user_id, b'item'))

                about = message.text[:ABOUT_LIMIT]
                # Редактируем итем
                if item_id > 0:
                    query = "UPDATE labels SET about = %s WHERE id = %s"
                    self.cursor.execute(query, (about, item_id))
                    self.connection.commit()
                    self.check_th()
                    bot.send_message(user_id, "Описание затеи изменено")
                    self.send_item(bot, user_id, item_id, is_command=True)
                    try:
                        bot.delete_message(user_id, int(self.users.hget(user_id, b'message_id')))
                    finally:
                        self.send_item(bot, user_id, item_id, is_edited=True)
                    self.research(bot, item_id, if_cat=False, if_date=False)
                if item_id == 0:
                    query = "INSERT INTO labels (about, subcategory, author, time_added, username) " \
                            "VALUES (%s, %s, %s, %s, %s)"
                    self.cursor.execute(query, (about, [], user_id, int(time.time()), message.chat.username))

                    self.connection.commit()
                    query = "SELECT LASTVAL()"
                    self.cursor.execute(query)
                    row = self.cursor.fetchone()
                    self.users.hset(user_id, b'item', int(row[0]))
                    self.send_item(bot, user_id, row[0], is_command=True)
                    bot.send_message(user_id, "Затея опубликована. "
                                              "Хотите помочь проекту? https://t.me/belbekspace_chat/10")
                    # self.send_item(bot, user_id, row[0], is_edited=True,
                    #               message_id=int(self.users.hget(user_id, b'message_id')))
                    self.go_menu(bot, message, 3)
                    self.research(bot, user_id, if_cat=False)
            elif int(self.users.hget(user_id, b'edit')) == 2:
                try:
                    start_time = int(time.mktime(time.strptime(message.text, FORMAT_TIME)))
                    self.users.hset(user_id, b'edit', 0)
                    item_id = int(self.users.hget(user_id, b'item'))
                    query = "UPDATE labels SET start_time = %s WHERE id = %s"
                    self.cursor.execute(query, (start_time, item_id))
                    self.connection.commit()
                    self.send_item(bot, user_id, item_id, is_command=True)
                    self.check_th()
                    bot.send_message(user_id, "Время начала затеи изменено")
                    try:
                        bot.delete_message(user_id, int(self.users.hget(user_id, b'message_id')))
                    finally:
                        self.send_item(bot, user_id, item_id, is_edited=True)
                    self.research(bot, user_id, if_cat=False)
                    self.renew_cats()

                except ValueError:
                    self.go_menu(bot, message, 5)
            elif int(self.users.hget(user_id, b'edit')) == 4:
                if re.fullmatch("^(-?\d+(\.\d+)?),\s*(-?\d+(\.\d+)?)$", message.text):
                    location = {'latitude': float(message.text.split(',')[0]),
                                'longitude': float(message.text.split(',')[1])}
                    self.go_location(bot, message, location)

        @bot.callback_query_handler(func=lambda call: True)
        def callback_worker(call):
            user_id = call.message.chat.id

            bot.answer_callback_query(call.id)

            self.users.hset(user_id, b'message_id', call.message.message_id)  # Фиксируем ID сообщения
            if not self.users.hexists(user_id, b'edit'):
                bot.send_message(user_id, "Бот обновился, нажмите /start")
                return
            # Показываем итем на месте меню
            if call.data[:4] == "item":
                self.send_item(bot, user_id, int(call.data.split('_')[1]), is_edited=True,
                               message_id=int(self.users.hget(user_id, b'message_id')))

            # Редактирование итема
            if call.data[:4] == "edit":
                item = int(call.data.split('_')[1])
                self.users.hset(user_id, b'item', item)
                self.users.hset(user_id, b'edit', 1)
                self.go_menu(bot, call.message, 0)

            # Редактирование итема
            if call.data[:4] == "done":
                item = int(call.data.split('_')[1])
                self.renew_cats()
                self.users.hdel(user_id, b'cat_sel')
                self.research(bot, user_id, if_text=False, if_date=False)
                self.send_item(bot, user_id, item, is_edited=True,
                               message_id=int(self.users.hget(user_id, b'message_id')))

            # Редактируем категорию
            if call.data[:3] == "cat":
                item_id = int(call.data.split('_')[1])
                self.users.hset(user_id, b'item', item_id)
                self.go_menu(bot, call.message, 3)
            # Подтверждение удаления
            if call.data[:3] == "del":
                item_id = int(call.data.split('_')[1])
                self.users.hset(user_id, b'item', item_id)
                self.go_menu(bot, call.message, 4)

            # Выбираем сферу для поиска
            if call.data[:4] == "ucat":
                category = call.data.split('_')[1]
                self.users.hdel(user_id, b'subcategory')
                self.users.hset(user_id, b'category', category)
                self.go_menu(bot, call.message, 2)
            # Выбираем все сферы для поиска
            if call.data == "all":
                self.users.hset(user_id, b'category', self.additional_scat[1])
                self.do_search(bot, call.message)

            # Выбран глубокий космос
            if call.data == "ds_cat":
                self.users.hset(user_id, b'category', self.additional_scat[0])
                self.do_search(bot, call.message)
            # Выбираем направление для поиска
            if call.data[:4] == "usub":
                subcategory = call.data.split('_')[1]
                self.users.hset(user_id, b'subcategory', subcategory)
                self.do_search(bot, call.message)

            # Выбираем все направления для поиска
            if call.data == "dsub":
                self.users.hdel(user_id, b'subcategory')
                self.do_search(bot, call.message)

            # Отмечена подкатегория
            if call.data[:4] == "lcat":
                cat = call.data.split('_')[1]

                label_id = int(self.users.hget(user_id, b'item'))
                query = "SELECT subcategory FROM labels WHERE id = %s"
                self.cursor.execute(query, (label_id,))
                row = self.cursor.fetchone()
                categories = row[0]

                if cat in categories:
                    categories.remove(cat)
                else:
                    categories.append(cat)

                # Сохраняем список направлений

                if len(categories) > 0:

                    label_id = int(self.users.hget(user_id, b'item'))

                    query = "UPDATE labels SET subcategory = %s WHERE id = %s"
                    self.cursor.execute(query, (categories, label_id))
                    self.connection.commit()

                self.go_menu(bot, call.message, 3)

            if call.data == "rcat":
                self.users.hdel(user_id, b'cat_sel')
                self.go_menu(bot, call.message, 3)

            if call.data[:4] == "scat":
                sel_category = call.data.split('_')[1]
                self.users.hset(user_id, b'cat_sel', sel_category)
                self.go_menu(bot, call.message, 3)

            if call.data == "cdel_label":
                # Удаляю затею из базы и из списка меток пользователя
                label_id = int(self.users.hget(user_id, b'item'))
                query = "DELETE FROM labels WHERE id = %s"
                self.cursor.execute(query, (label_id,))
                self.connection.commit()
                self.send_item(bot, user_id, label_id, is_command=True)
                self.send_item(bot, user_id, label_id,
                               message_id=int(self.users.hget(user_id, b'message_id')))
                bot.send_message(user_id, "Затея удалена")
                self.renew_cats()

            if call.data[:4] == "time":
                item_id = int(call.data.split('_')[1])
                self.users.hset(user_id, b'item', item_id)
                self.users.hset(user_id, b'edit', 2)
                self.go_menu(bot, call.message, 5)

            if call.data[:5] == "ctime":
                date_code = int(call.data.split('_')[1])
                self.do_search_date(bot, call.message, date_code)

            if call.data == "events":
                self.go_menu(bot, call.message, 6)

            if call.data[:3] == "pic":
                item_id = int(call.data.split('_')[1])
                self.users.hset(user_id, b'item', item_id)
                self.users.hset(user_id, b'edit', 3)
                self.go_menu(bot, call.message, 7)

            if call.data[:3] == "map":
                item_id = int(call.data.split('_')[1])
                self.users.hset(user_id, b'item', item_id)
                self.users.hset(user_id, b'edit', 4)
                self.go_menu(bot, call.message, 8)

            if call.data[:3] == "loc":
                item_id = call.data[4:]
                if item_id.find('@') < 0:
                    query = "SELECT geo_lat, geo_long FROM labels WHERE id = %s"
                    self.cursor.execute(query, (int(item_id),))
                    row = self.cursor.fetchone()
                    if row is not None:
                        self.check_th()
                        bot.send_location(user_id, row[0], row[1], reply_to_message_id=call.message.message_id)
                else:

                    if self.deep_space.exists(item_id) and\
                            self.deep_space.hexists(item_id, b'geo_lat'):
                        self.check_th()
                        bot.send_location(user_id, float(self.deep_space.hget(item_id, b'geo_lat')),
                                          float(self.deep_space.hget(item_id, b'geo_long')),
                                          reply_to_message_id=call.message.message_id)

        bot.polling()
        #  try:
        #    bot.polling()
        #  except Exception as error:
        #    print("Error polling: ", error)


if __name__ == "__main__":
    space = Space()
    space.deploy()
