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

# Устанавливаем константы
BOTCHAT_ID = -1001508419451  # Айди чата для ботов
DEBUG_ID = 665812965  # Дебаг whitejoe
ABOUT_LIMIT = 1000  # Лимит символов в описании
DS_ID = "belbek_space"
FORMAT_TIME = "%d.%m.%y %H:%M"
FORMAT_DESC = "ДД.ММ.ГГ ЧЧ:ММ"


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
        # self.search = redis.from_url(redis_url, db=4)
        self.deep_space = redis.from_url(redis_url, db=5)
        self.views = redis.from_url(redis_url, db=6)

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
        13 start_time
        '''

        # Подгрузка категорий
        self.categories = {}
        with open("categories.json") as json_file:
            cat_dict = json.load(json_file)
            for cat, scat in cat_dict.items():
                self.categories[cat] = dict.fromkeys(scat, 0)
        self.renew_cats()

        self.edit_items = ['Изменить', '📚', '❌', '🕰']
        self.additional_scat = ['🛸 Deep Space 🛰', '🌎 Все сферы 🌎', '📚 Все направления 📚', "🕰 Мероприятия 🕰"]
        self.limit_per_second = 5
        self.limit_counter = 0
        self.last_send_time = int(time.time())
        self.hellow_message = f"Канал поддержки: https://t.me/belbekspace\n" \
                              f"Такси и доставка: @BelbekTaxiBot\n" \
                              f"Для поиска отправьте любое слово, дату (ДД.ММ.ГГ) и/или фразу"
        self.day_today = -1
        self.date_code = {"Последняя неделя": 0,
                          "Сегодня": 1,
                          "Завтра": 2,
                          "На этой неделе": 3,
                          "На следующей неделе": 4,
                          "Через 2 недели и далее": 5}

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
        for cat, ucats in self.categories.items():
            for ucat in ucats.keys():
                self.categories[cat][ucat] = 0
        query = "SELECT * from labels"
        self.cursor.execute(query)
        while 1:
            row = self.cursor.fetchone()
            if row is None:
                break
            label_sub_list = row[3]
            for label_sub in label_sub_list:
                for cat, scat in self.categories.items():
                    for uscat in scat.keys():
                        if label_sub == uscat:
                            self.categories[cat][uscat] += 1

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

        item_menu = []
        if is_ds:
            message_text = f"📝 {self.deep_space.hget(item_id, b'text').decode('utf-8')}"
            if self.deep_space.hexists(item_id, b'start_time'):
                start_time = datetime.datetime.fromtimestamp(int(self.deep_space.hget(item_id, b'start_time')))

                message_text = message_text + f"\n🕰 {start_time.strftime(FORMAT_TIME)}"
            else:
                message_text = message_text + f"\n{self.additional_scat[0]}"
            # f"🆔 {item_id.decode('utf-8')}\n" \
        else:
            query = "SELECT * from labels WHERE id=%s"
            cursor = self.connection.cursor()
            cursor.execute(query, (item_id,))
            row = cursor.fetchone()
            message_text = "Удалено"
            if row is not None:

                if is_command:
                    message_text = f"/set_item {item_id}@{DS_ID}"
                    if row[13] > 0:
                        start_time = datetime.datetime.fromtimestamp(row[13])
                        message_text = message_text + f" {start_time.strftime(FORMAT_TIME)}"
                    message_text = message_text + f" {row[1]}"
                else:
                    message_text = row[1]
                    vs = int(row[8])
                    if not is_edited:
                        inc_views(item_id)
                    if self.views.exists(item_id):
                        vs += int(self.views.get(item_id))
                    message_text = f"📝 {message_text}\n👀 {vs}"
                    if row[13] > 0:
                        start_time = datetime.datetime.fromtimestamp(row[13])

                        message_text = message_text + f"\n🕰 {start_time.strftime(FORMAT_TIME)}"
                    else:
                        message_text = message_text + f"\n📚 {','.join(row[3])}"
                    #  🆔 {row[0]}@{DS_ID}\n"

                if is_edited:
                    item_menu.append(types.InlineKeyboardButton(text=self.edit_items[0],
                                                                callback_data=f"edit_{item_id}"))
                    if row[13] > 0:
                        item_menu.append(types.InlineKeyboardButton(text=self.edit_items[3],
                                                                    callback_data=f"time_{item_id}"))
                    else:
                        item_menu.append(types.InlineKeyboardButton(text=self.edit_items[1],
                                                                    callback_data=f"cat_{item_id}"))
                    item_menu.append(types.InlineKeyboardButton(text=self.edit_items[2],
                                                                callback_data=f"del_{item_id}"))
            elif is_command:
                message_text = f"/set_item {item_id}@{DS_ID}"

        keyboard = types.InlineKeyboardMarkup()
        keyboard.row(*item_menu)
        self.check_th()
        if is_command:
            user_id = BOTCHAT_ID
        try:
            if message_id is None:
                bot.send_message(user_id, message_text, reply_markup=keyboard)
            else:
                bot.edit_message_text(chat_id=user_id, message_id=message_id, text=message_text, reply_markup=keyboard)
        except Exception as error:
            print("Error: ", error)

    # Обработчик всех состояний меню
    def go_menu(self, bot, message, menu_id):
        user_id = message.chat.id

        keyboard = types.InlineKeyboardMarkup()

        if menu_id == 0:  # Редактирование и создание итема

            message_text = f"Пришлите описание затеи (лимит {ABOUT_LIMIT} символов), укажите контакты"
            if message.chat.username is not None:
                message_text = message_text + f" (например, ссылку на свой телеграмм:" \
                                              f" https://t.me/{message.chat.username})"
            message_text = message_text + f". Для отмены введите /cancel"
            self.check_th()
            bot.send_message(user_id, message_text, reply_markup=types.ReplyKeyboardRemove())

        elif menu_id == 1:  # Выбор сферы для поиска
            for cat in self.categories.keys():
                count = 0
                for scat, scol in self.categories[cat].items():
                    count += scol
                keyboard.row(types.InlineKeyboardButton(text=f"{cat} ({count})", callback_data=f"ucat_{cat}"))
            add_row_text = f"{self.additional_scat[0]} ({len(self.deep_space.keys())})"
            keyboard.row(types.InlineKeyboardButton(text=add_row_text, callback_data=f"ds_cat"))
            keyboard.row(types.InlineKeyboardButton(text=self.additional_scat[3], callback_data=f"events"))
            message_text = "Выберите сферу деятельности:"
            bot.send_message(user_id, message_text, reply_markup=keyboard)

        elif menu_id == 2:  # Выбор направления для поиска
            cat = self.users.hget(user_id, b'category').decode('utf-8')
            for sub, scol in self.categories[cat].items():
                keyboard.row(types.InlineKeyboardButton(text=f"{sub} ({scol})", callback_data=f"usub_{sub}"))
            keyboard.row(types.InlineKeyboardButton(text="📚 Все направления 📚", callback_data=f"dsub"))
            message_text = "Выберите направление:"
            try:
                bot.edit_message_text(chat_id=user_id, message_id=int(self.users.hget(user_id, b'message_id')),
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
                bot.edit_message_text(chat_id=user_id, message_id=int(self.users.hget(user_id, b'message_id')),
                                      text=message_text, reply_markup=keyboard)
            except Exception as error:
                print("Error: ", error)
                bot.send_message(user_id, message_text, reply_markup=keyboard)

        elif menu_id == 4:  # Подтверждение удаления
            message_text = "Вы действительно хотите ❌ убрать ❌ эту затею из нашего космоса?"
            keyboard.row(types.InlineKeyboardButton(text="Да, убираю 👎", callback_data=f"cdel_label"))
            keyboard.row(types.InlineKeyboardButton(text="Нет, пусть остаётся 👍",
                                                    callback_data=f"item_{int(self.users.hget(user_id, b'item'))}"))

            try:
                bot.edit_message_text(chat_id=user_id, message_id=int(self.users.hget(user_id, b'message_id')),
                                      text=message_text, reply_markup=keyboard)
            except Exception as error:
                print("Error: ", error)
                bot.send_message(user_id, message_text, reply_markup=keyboard)
        elif menu_id == 5:  # Редактирование времени итема
            now_time = datetime.datetime.fromtimestamp(int(time.time()))
            message_text = f"Пришлите дату и время меоприятия (в формате {FORMAT_DESC}), например:\n" \
                           f"{now_time.strftime(FORMAT_TIME)}\nЧто бы удалить время введите /no_time\n" \
                           f"Для отмены - /cancel"
            self.check_th()
            bot.send_message(user_id, message_text, reply_markup=types.ReplyKeyboardRemove())
        elif menu_id == 6:  # Поиск мероприятий
            for menu_item, date_code in self.date_code.items():
                keyboard.row(types.InlineKeyboardButton(text=menu_item, callback_data=f"stime_{date_code}"))
            message_text = "Выберите дату начала мероприятия или просто оптравьте текстом (ДД.ММ.ГГ)"
            try:
                bot.edit_message_text(chat_id=user_id, message_id=int(self.users.hget(user_id, b'message_id')),
                                      text=message_text, reply_markup=keyboard)
            except Exception as error:
                print("Error: ", error)
                bot.send_message(user_id, message_text, reply_markup=keyboard)

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
            if user_id == row[9]:
                self.send_item(bot, user_id, item_id, is_edited=True)
                count += 1

    # Формирование списка поиска из категорий
    def do_search(self, bot, message):

        user_id = message.chat.id
        count = 0
        keyboard = types.InlineKeyboardMarkup()
        # Deep space
        if not self.users.hexists(user_id, "category"):
            return
        category = self.users.hget(user_id, "category").decode("utf-8")
        message_text = f"{category}"
        if category == self.additional_scat[0]:

            for item_id in self.deep_space.keys():

                self.send_item(bot, user_id, item_id, is_ds=True)

        else:
            # Формируем список необходимых категорий

            target_subcategory_list = self.categories[category].keys()
            if self.users.hexists(user_id, "subcategory"):
                sub_c = self.users.hget(user_id, "subcategory").decode('utf-8')
                target_subcategory_list = [sub_c]
                message_text = message_text + f"\n{sub_c}"
            # Перебираем все метки
            query = "SELECT * from labels"
            self.cursor.execute(query)
            while 1:
                row = self.cursor.fetchone()
                if row is None:
                    break

                item_id = row[0]
                label_sub_list = row[3]
                if len(set(label_sub_list).intersection(set(target_subcategory_list))) > 0:
                    self.send_item(bot, user_id, item_id)
                    count += 1
        self.users.hdel(user_id, "category")
        self.users.hdel(user_id, "subcategory")
        self.check_th()

        message_text = message_text + f"\nНайдено {count} затей:"
        try:
            bot.edit_message_text(chat_id=user_id, message_id=int(self.users.hget(user_id, b'message_id')),
                                  text=message_text, reply_markup=keyboard)
        except Exception as error:
            print("Error: ", error)
        after_message = self.hellow_message
        self.check_th()
        bot.send_message(user_id, after_message)

        # Формирование списка поиска по словам

    # Формирование списка поиска из текста
    def do_search_text(self, bot, message, text):

        def is_contain(phrase: [], about_text: str):
            for word in phrase:
                if about_text.lower().find(word.lower()) < 0:
                    return False
            return True

        user_id = message.chat.id
        count = 0

        pre_words = text.split(' ')
        words = []
        for w in pre_words:
            if len(w) > 2:
                words.append(w)

        if len(words) > 0:
            query = "SELECT * from labels"
            self.cursor.execute(query)
            while 1:
                row = self.cursor.fetchone()
                if row is None:
                    break
                item_id = row[0]
                about = row[1]
                if is_contain(words, about):
                    self.send_item(bot, user_id, item_id)
                    count += 1
            for item_id in self.deep_space.keys():
                about = self.deep_space.hget(item_id, b'text').decode('utf-8')
                if self.deep_space.hexists(item_id, b'star_time'):
                    start_time = datetime.datetime.fromtimestamp(int(self.deep_space.hget(item_id, b'star_time')))
                    about = f"{start_time.strftime(FORMAT_TIME)} " + about
                if is_contain(words, about):
                    self.send_item(bot, user_id, item_id, is_ds=True)
                    count += 1

        self.check_th()
        after_message = f"Найдено затей: {count}\n"+self.hellow_message
        self.check_th()
        bot.send_message(user_id, after_message)

    # Поиск событий
    def do_search_date(self, bot, message, date_code):
        x = time.localtime(int(time.time()))
        mid_night = int(time.mktime(time.strptime(f"{x.tm_mday}.{x.tm_mon}.{x.tm_year} 00:00", "%d.%m.%Y %H:%M")))
        day_sec = 60 * 60 * 24
        wd = time.localtime().tm_mday

        def is_date(ts):
            if date_code == 0:
                return ts < mid_night
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

        user_id = message.chat.id
        count = 0
        query = "SELECT * from labels WHERE start_time > 0"
        self.cursor.execute(query)
        while 1:
            row = self.cursor.fetchone()
            if row is None:
                break
            item_id = row[0]
            start_time = row[13]
            if is_date(start_time):
                self.send_item(bot, user_id, item_id)
                count += 1

        for item_id in self.deep_space.keys():
            start_time = int(self.deep_space.hget(item_id, b'start_time'))
            if is_date(start_time):
                self.send_item(bot, user_id, item_id, is_ds=True)
                count += 1

        self.check_th()
        after_message = f"Найдено затей: {count}\n"+self.hellow_message
        self.check_th()
        bot.send_message(user_id, after_message)

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

        @bot.message_handler(commands=['set_item'])
        def set_item_message(message):
            user_id = message.chat.id
            if user_id == BOTCHAT_ID:
                id_pos = message.text.find(' ', 0)
                if id_pos < 0:
                    return
                id_pos_end = message.text.find(' ', id_pos+1)

                if id_pos_end < 0:
                    item_id = message.text[id_pos+1:]
                    self.deep_space.delete(item_id)
                    # bot.send_message(DEBUG_ID, f"{item_id}")
                else:
                    item_id = message.text[id_pos + 1:id_pos_end]
                    start_pos = 1 + id_pos_end
                    start_pos_end = message.text.find(' ', start_pos)
                    start_pos_end = message.text.find(' ', start_pos_end + 1)
                    try:
                        start_str = message.text[start_pos:start_pos_end]
                        start_time = int(time.mktime(time.strptime(start_str, FORMAT_TIME)))
                        self.deep_space.hset(item_id, b'start_time', start_time)
                        item_pos = start_pos_end + 1
                    except ValueError:
                        item_pos = 1 + id_pos_end
                        if self.deep_space.exists(item_id):
                            self.deep_space.hdel(item_id, b'start_time')

                    item = message.text[item_pos:]
                    self.deep_space.hset(item_id, b'text', item)
                    # bot.send_message(DEBUG_ID,f"{item_id} {item}")

        @bot.message_handler(commands=['new_item'])
        def new_item(message):
            user_id = message.chat.id
            self.users.hset(user_id, b'item', 0)
            self.users.hset(user_id, b'edit', 1)
            self.users.hdel(user_id, b'message_id')
            self.go_menu(bot, message, 0)

        @bot.message_handler(commands=['my_items'])
        def my_items(message):
            self.my_items(bot, message)

        @bot.message_handler(commands=['search'])
        def browse(message):
            self.go_menu(bot, message, 1)

        # Отмена ввода
        @bot.message_handler(commands=['cancel'])
        def cancel_message(message):
            user_id = message.chat.id
            if int(self.users.hget(user_id, b'edit')) > 0:
                self.users.hset(user_id, b'edit', 0)
                self.check_th()
                bot.send_message(user_id, "Ввод отменён")

        # Удаление времени
        @bot.message_handler(commands=['no_time'])
        def no_time(message):
            user_id = message.chat.id
            item_id = int(self.users.hget(user_id, b'item'))
            query = "UPDATE labels SET start_time = %s WHERE id = %s"
            self.cursor.execute(query, (0, item_id))
            self.connection.commit()
            self.send_item(bot, user_id, item_id, is_command=True)
            self.send_item(bot, user_id, item_id, message_id=int(self.users.hget(user_id, b'message_id')),
                           is_edited=True)
            self.check_th()
            bot.send_message(user_id, f"Вермя начала затеи удалено, что бы вернуть время,"
                                      f" следует отметить затею как {self.additional_scat[3]}")

        # Обработка всех текстовых команд
        @bot.message_handler(content_types=['text'])
        def message_text(message):
            user_id = message.chat.id
            cur_time = int(time.time())
            # Check new day
            if time.localtime().tm_mday != self.day_today:
                self.day_today = time.localtime().tm_mday
                self.save_views()
            if user_id == BOTCHAT_ID:
                return

            self.users.hset(user_id, b'last_login', cur_time)
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
                    self.send_item(bot, user_id, item_id, is_command=True)
                    self.send_item(bot, user_id, item_id, message_id=int(self.users.hget(user_id, b'message_id')),
                                   is_edited=True)
                    self.check_th()
                    bot.send_message(user_id, "Описание затеи изменено")

                if item_id == 0:
                    query = "INSERT INTO labels (about, subcategory, author, time_added, username) " \
                            "VALUES (%s, %s, %s, %s, %s)"
                    self.cursor.execute(query, (about, [], user_id, cur_time, message.chat.username))

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
            elif int(self.users.hget(user_id, b'edit')) == 2:
                try:
                    start_time = int(time.mktime(time.strptime(message.text, FORMAT_TIME)))
                    self.users.hset(user_id, b'edit', 0)
                    item_id = int(self.users.hget(user_id, b'item'))
                    query = "UPDATE labels SET start_time = %s WHERE id = %s"
                    self.cursor.execute(query, (start_time, item_id))
                    self.connection.commit()
                    self.send_item(bot, user_id, item_id, is_command=True)
                    self.send_item(bot, user_id, item_id, message_id=int(self.users.hget(user_id, b'message_id')),
                                   is_edited=True)
                    self.check_th()
                    bot.send_message(user_id, "Время начала затеи изменено")

                except ValueError:
                    self.go_menu(bot, message, 5)

        @bot.callback_query_handler(func=lambda call: True)
        def callback_worker(call):
            user_id = call.message.chat.id
            cur_time = int(time.time())
            bot.answer_callback_query(call.id)
            self.users.hset(user_id, b'last_login', cur_time)
            # Фиксируем ID сообщения
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

        bot.polling()
        #  try:
        #    bot.polling()
        #  except Exception as error:
        #    print("Error polling: ", error)


if __name__ == "__main__":
    space = Space()
    space.deploy()
