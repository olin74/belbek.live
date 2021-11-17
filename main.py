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

# Устанавливаем константы
# ADMIN_LIST = [665812965]  # Список админов для спец команд (тут только whitejoe)
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
        redis_url_snapshot = os.environ['REDIS_URL_SNAPSHOT']

        # База данных пользователей
        self.users = redis.from_url(redis_url, db=1)
        '''
        username
        menu
        parent_menu
        item
        last_login
        message_id
        geo_long
        geo_lat
        category
        subcategory
        search_string
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
        '''
                    {'wait': redis.from_url(redis_url, db=1),
                      'status': redis.from_url(redis_url, db=2),
                      'geo_long': redis.from_url(redis_url, db=3),
                      'geo_lat': redis.from_url(redis_url, db=4),
                      'category': redis.from_url(redis_url, db=5),
                      'subcategory': redis.from_url(redis_url, db=6),
                      'name': redis.from_url(redis_url, db=7),
                      'username': redis.from_url(redis_url, db=8),
                      'search': redis.from_url(redis_url, db=9),
                      'labels': redis.from_url(redis_url, db=10),
                      'last_login': redis.from_url(redis_url, db=11),
                      'message_id': redis.from_url(redis_url, db=12)
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
        # self.events = {'about': redis.from_url(redis_url_labels, db=1),
        #                    'description': redis.from_url(redis_url_labels, db=2),
        #                    'photos': redis.from_url(redis_url_labels, db=3),
        #                    'price': redis.from_url(redis_url_labels, db=4),
        #                    'category': redis.from_url(redis_url_labels, db=5),
        #                    'tags': redis.from_url(redis_url_labels, db=6),
        #                    'status_event': redis.from_url(redis_url_labels, db=7),
        #                    'time_start': redis.from_url(redis_url_labels, db=8),
        #                    'time_end': redis.from_url(redis_url_labels, db=9),
        #                    'views': redis.from_url(redis_url_labels, db=10),
        #                    'label_owner': redis.from_url(redis_url_labels, db=11),
        #                    'zoom': redis.from_url(redis_url_labels, db=12)
        #                        }
         '''

        # Подгрузка категорий
        with open("categories.json") as json_file:
            self.categories = json.load(json_file)

        # Снепшот
        # пока отключен (без базы)
        # today = str(int(time.time()) - int(time.time()) % (3600 * 24))[:-3]
        # redis.from_url(redis_url_snapshot).set('snapshot-' + today, self.snap_data())

        # Чистка базы
        # какой базы?

    def snap_data(self):
        s_data = []
        for label_id in self.labels['status_label'].keys():
            if int(self.labels['status_label'][label_id]) == 1:
                label = {
                    'about': self.labels['status_label'][label_id].decode('utf-8'),
                    'description': dict(self.labels['description']).get(label_id, "").decode('utf-8'),
                    'price': dict(self.labels['price']).get(label_id, "").decode('utf-8'),
                    'subcategory': self.labels['subcategory'][label_id].decode('utf-8'),
                    #  'tags': self.labels['tags'][label_id].decode('utf-8'),
                    'geo_lat': float(self.labels['geo_lat'][label_id]),
                    'geo_long': float(self.labels['geo_long'][label_id]),
                    'author': int(self.labels['author'][label_id]),
                    'views': int(self.labels['views'][label_id])
                }
                s_data.append(label)
        return json.dumps(s_data)

    # Обработчик всех состояний меню
    def go_menu(self, bot, message, menu_id):
        user_id = message.chat.id
        cur_time = int(time.time())

        user_info = self.users.hgetall(user_id)
        print(user_info)
        user_info['last_login'] = cur_time
        keyboard = types.InlineKeyboardMarkup()

        user_info['menu'] = menu_id

        if menu_id == 0:  # Главное меню
            user_info['parent_menu'] = menu_id
            user_info['item'] = 0

            if user_id in self.search:
                self.search.delete(user_id)

            # Кнопки меню
            start_menu_items = ['Как искать?', 'Мои места и затеи',
                                'Указать моё местоположение',
                                'Выбрать сферу', 'Выбрать направление',
                                'Поиск мест', 'Поиск затей']
            keyboard_line = [types.InlineKeyboardButton(text=start_menu_items[0], callback_data=f"go_4"),
                             types.InlineKeyboardButton(text=start_menu_items[1], callback_data=f"go_5")]
            keyboard.row(*keyboard_line)
            keyboard.row(types.InlineKeyboardButton(text=start_menu_items[2], callback_data=f"go_20"))
            keyboard_line = [types.InlineKeyboardButton(text=start_menu_items[3], callback_data=f"go_1")]
            if 'category' in user_info.keys():
                keyboard_line.append(types.InlineKeyboardButton(text=start_menu_items[4], callback_data=f"go_2"))
            keyboard.row(*keyboard_line)
            keyboard_line = [types.InlineKeyboardButton(text=start_menu_items[5], callback_data=f"go_6"),
                             types.InlineKeyboardButton(text=start_menu_items[6], callback_data=f"go_13")]
            keyboard.row(*keyboard_line)
            message_text = "Главное меню, приглашаю начать поиск написав текст или нажав кнопку. Предварительно " \
                           "можно настроить геолокацию и ограничить область поиска сферами деятельности, " \
                           "но поиск всё равно еще не работает"
            try:
                bot.edit_message_text(user_id, int(user_info['message_id']), message_text, reply_markup=keyboard)
            except:
                bot.send_message(user_id, message_text, reply_markup=keyboard)

        elif menu_id == 1:  # Выбор сферы
            for cat in self.categories.keys():
                keyboard.row(types.InlineKeyboardButton(text=cat, callback_data=f"ucat_{cat}"))
            keyboard.row(types.InlineKeyboardButton(text="Все сферы", callback_data=f"dcat"))
            message_text = "Выберите сферу деятельности:"
            try:
                bot.edit_message_text(user_id, int(user_info['message_id']), message_text, reply_markup=keyboard)
            except:
                bot.send_message(user_id, message_text, reply_markup=keyboard)

        elif menu_id == 2:  # Выбор направления
            cat = self.users.hget(user_id, 'category').decode('utf-8')
            for sub in self.categories[cat]:
                keyboard.row(types.InlineKeyboardButton(text=sub, callback_data=f"usub_{sub}"))
            keyboard.row(types.InlineKeyboardButton(text="Все направления", callback_data=f"dsub"))
            message_text = "Выберите направление:"
            try:
                bot.edit_message_text(user_id, int(user_info['message_id']), message_text, reply_markup=keyboard)
            except:
                bot.send_message(user_id, message_text, reply_markup=keyboard)

        elif menu_id == 3:  # Выбор направлений места

            selected_cats = []  # Список категорий выбранного места
            banned_cats = []  # Список категорий других мест пользователя

            for cat, sub_list in self.categories.items():
                for sub in sub_list:
                    pre = ""
                    call_st = f"lcat_{sub}"
                    if sub in selected_cats:
                        pre = "✅ "
                    elif sub in banned_cats:
                        pre = "🚫 "
                        call_st = "none"
                    keyboard.row(types.InlineKeyboardButton(text=f"{pre}{cat}: {sub}", callback_data=call_st))
            keyboard.row(types.InlineKeyboardButton(text=f"Готово",
                                                    callback_data=f"go_{int(user_info['parent_menu'])}"))
            message_text = "Следует отметить одно или несколько направлений:"
            try:
                bot.edit_message_text(user_id, int(user_info['message_id']), message_text, reply_markup=keyboard)
            except:
                bot.send_message(user_id, message_text, reply_markup=keyboard)

        elif menu_id == 4:  # Помощь "как искать?"
            message_text = "Давай разбирайся сам, это демонстрация, всё равно не работает почти никакой функционал"
            keyboard.row(types.InlineKeyboardButton(text=f"Спасибо",
                                                    callback_data=f"go_{int(user_info['parent_menu'])}"))
            try:
                bot.edit_message_text(user_id, int(user_info['message_id']), message_text, reply_markup=keyboard)
            except:
                bot.send_message(user_id, message_text, reply_markup=keyboard)

        elif menu_id == 5:  # Меню редактирования
            user_info['parent_menu'] = menu_id
            item = int(user_info['item'])
            if user_id in self.new_label.keys():
                self.new_label.delete(user_id)
            menu_edit_items = ['Как создавать места и затеи❓',
                               '❓', 'Новое место', 'Новая затея',
                               'Изменить описание', 'Изменить локацию',
                               'Изменить фотографии', 'Изменить направления', '🚮',
                               'Предыдущее', 'Выход', 'Следующее', 'Заново']
            keyboard_line = []
            message_text = "Здесь будут доступны для редактирования все ваши места и затеи, но пока их у вас нет"
            if user_id not in self.my_labels.keys():
                keyboard.row(types.InlineKeyboardButton(text=menu_edit_items[0], callback_data=f"go_16"))
            else:
                keyboard_line.append(types.InlineKeyboardButton(text=menu_edit_items[1], callback_data=f"go_16"))
                message_text = f"Здесь будет описание текущего {item} места"

            keyboard_line.append(types.InlineKeyboardButton(text=menu_edit_items[2], callback_data=f"go_8"))
            keyboard_line.append(types.InlineKeyboardButton(text=menu_edit_items[3], callback_data=f"go_13"))
            keyboard.row(*keyboard_line)
            if user_id in self.my_labels.keys():
                keyboard_line = [types.InlineKeyboardButton(text=menu_edit_items[4], callback_data=f"go_14"),
                                 types.InlineKeyboardButton(text=menu_edit_items[5], callback_data=f"go_20")]

                keyboard.row(*keyboard_line)
                keyboard_line = [types.InlineKeyboardButton(text=menu_edit_items[6], callback_data=f"go_13"),
                                 types.InlineKeyboardButton(text=menu_edit_items[7], callback_data=f"go_3"),
                                 types.InlineKeyboardButton(text=menu_edit_items[8], callback_data=f"go_15")]
                keyboard.row(*keyboard_line)
            keyboard_line = []

            if item > 0:
                keyboard_line.append(types.InlineKeyboardButton(text=menu_edit_items[9],
                                                                callback_data=f"select_{item-1}"))
            keyboard_line.append(types.InlineKeyboardButton(text=menu_edit_items[10], callback_data=f"go_0"))
            if user_id in self.my_labels.keys():

                if item < self.my_labels.hlen(user_id) - 1:
                    keyboard_line.append(types.InlineKeyboardButton(text=menu_edit_items[11],
                                                                    callback_data=f"select_{item+1}"))
                elif item > 0:
                    keyboard_line.append(types.InlineKeyboardButton(text=menu_edit_items[12],
                                                                    callback_data=f"select_0"))
            keyboard.row(*keyboard_line)

            try:
                bot.edit_message_text(user_id, int(user_info['message_id']), message_text, reply_markup=keyboard)
            except:
                bot.send_message(user_id, message_text, reply_markup=keyboard)

        elif menu_id == 6:  # Меню просмотра результатов поиска
            user_info['parent_menu'] = menu_id
            item = int(user_info['item'])
            menu_search_items = ['Хочу такси туда', 'Хочу доставку оттуда',
                                 'Показать на карте', 'Показать фотографии',
                                 'Предыдущее', 'Выход', 'Следующее', 'Заново']
            if user_id not in self.search.keys():
                pass  # Попытка наполнить спиок поисковых результатов

            message_text = "🤷‍ Ничего не найдено! Этот раздел еще не начал наполняться."
            if user_id in self.search.keys():
                message_text = "Тут результаты поиска, но вы их не увидите"
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
                keyboard_line.append(types.InlineKeyboardButton(text=menu_search_items[5], callback_data=f"go_0"))
                if item < self.search.hlen(user_id) - 1:
                    keyboard_line.append(types.InlineKeyboardButton(text=menu_search_items[6],
                                                                    callback_data=f"select_{item + 1}"))
                elif item > 0:
                    keyboard_line.append(types.InlineKeyboardButton(text=menu_search_items[7],
                                                                    callback_data=f"select_0"))
                keyboard.row(*keyboard_line)
            else:
                keyboard.row(types.InlineKeyboardButton(text=menu_search_items[5], callback_data=f"go_0"))

            try:
                bot.edit_message_text(user_id, int(user_info['message_id']), message_text, reply_markup=keyboard)
            except:
                bot.send_message(user_id, message_text, reply_markup=keyboard)

        elif menu_id == 7:  # Задать начальную локацию
            geo_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            geo_keyboard.row(types.KeyboardButton(text="Отправить геопозицию", request_location=True))
            message_text = "Ох, боже, как часто я это пишу в последние дни... Короче, если вы сидите с компа," \
                           " а может боитесь включать геолокацию и вообще у вас камера залеплена изолентой " \
                           "или ваше имя Антон, то отправьте геопозицию текстом (через запятую). " \
                           "Иначе просто нажмите на кнопку."
            try:
                bot.edit_message_text(user_id, int(user_info['message_id']), message_text, reply_markup=geo_keyboard)
            except:
                bot.send_message(user_id, message_text, reply_markup=geo_keyboard)

        elif menu_id == 8:  # Меню создания нового места
            if message.chat.username is not None:
                self.users.hset(user_id, 'username', message.chat.username)
                user_info['parent_menu'] = menu_id
                if user_id not in self.new_label.keys():
                    self.new_label.hmset(user_id, {'geo_lat': self.users.hget(user_id, 'geo_lat'),
                                                   'geo_long': self.users.hget(user_id, 'geo_long')})
                can_create = self.new_label.hexists(user_id, 'about') and self.new_label.hexists(user_id,
                                                                                                 'subcategory_list')
                menu_new_label_items = ['Изменить описание', 'Изменить локацию',
                                        'Изменить фотографии', 'Изменить направления',
                                        'Опубликовать', 'Отмена']
                message_text = f"Тут информация о новом месте и данные о необходимости заполнить те или иные поля" \
                               f" (геоданные стоят по-умолчанию ваши, осталось заполнить описание и категории)"
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
                    bot.edit_message_text(user_id, int(user_info['message_id']), message_text, reply_markup=keyboard)
                except:
                    bot.send_message(user_id, message_text, reply_markup=keyboard)
            else:
                message_text = f"‼️ Задайте имя пользователя в аккаунте Telegram," \
                               f" что бы бот мог направить Вам гостей и жителей долины ‼️ Для этого зайдите в" \
                               f" настройки, справа сверху нажмите 'Изменить' и заполните" \
                               f" поле 'Имя пользователя'."
                keyboard.row(
                    types.InlineKeyboardButton(text=f"Готово", callback_data=f"go_{int(user_info['parent_menu'])}"))
                try:
                    bot.edit_message_text(user_id, int(user_info['message_id']), message_text, reply_markup=keyboard)
                except:
                    bot.send_message(user_id, message_text, reply_markup=keyboard)

        elif menu_id == 9:  # Уведомление создание места
            user_info['item'] = 0
            message_text = "Новое место появилось в Belbek.Space !"

            # Занесение в базу self.new_label.hgetall(user_id)

            keyboard.row(types.InlineKeyboardButton(text="Замечательно", callback_data=f"go_5"))
            try:
                bot.edit_message_text(user_id, int(user_info['message_id']), message_text, reply_markup=keyboard)
            except:
                bot.send_message(user_id, message_text, reply_markup=keyboard)

        elif menu_id == 10:  # Показать на карте
            bot.delete_message(chat_id=message.chat.id, message_id=int(user_info['message_id']))

            lat = 44.5555  # пока так
            long = 33.9561

            keyboard.row(types.InlineKeyboardButton(text="OK", callback_data=f"dgo_{int(user_info['parent_menu'])}"))
            bot.send_location(chat_id=message.chat.id, longitude=long, latitude=lat, reply_markup=keyboard)

        elif menu_id == 11:  # Показ такси
            pass

        elif menu_id == 12:  # Показ доставки через такси
            pass

        elif menu_id == 13:  # Уведомление "в разработке"
            message_text = "Эта часть бота в разработке. Простите, но придётся подождать"
            keyboard.row(types.InlineKeyboardButton(text=f"Конечно, я подожду, спасибо",
                                                    callback_data=f"go_{int(user_info['parent_menu'])}"))
            try:
                bot.edit_message_text(user_id, int(user_info['message_id']), message_text, reply_markup=keyboard)
            except:
                bot.send_message(user_id, message_text, reply_markup=keyboard)

        elif menu_id == 14:  # Изменение описания места
            message_text = "Тут описание вашего места, но вы можете написать новое"
            keyboard.row(types.InlineKeyboardButton(text=f"Готово",
                                                    callback_data=f"go_{int(user_info['parent_menu'])}"))
            try:
                bot.edit_message_text(user_id, int(user_info['message_id']), message_text, reply_markup=keyboard)
            except:
                bot.send_message(user_id, message_text, reply_markup=keyboard)

        elif menu_id == 15:  # Подтверждение удаления
            message_text = "Вы действительно хотите убрать это место из нашего космоса?"
            keyboard_line = [types.InlineKeyboardButton(text="Да, это так", callback_data=f"del_label"),
                             types.InlineKeyboardButton(text="Нет, пусть остаётся",
                                                        callback_data=f"go_{int(user_info['parent_menu'])}")]
            keyboard.row(*keyboard_line)
            try:
                bot.edit_message_text(user_id, int(user_info['message_id']), message_text, reply_markup=keyboard)
            except:
                bot.send_message(user_id, message_text, reply_markup=keyboard)

        elif menu_id == 16:  # Помощь "как создать место и затею?"
            message_text = "Ты сможешь, я в тебя верю!"
            keyboard.row(
                types.InlineKeyboardButton(text=f"Спасибо", callback_data=f"go_{int(user_info['parent_menu'])}"))
            try:
                bot.edit_message_text(user_id, int(user_info['message_id']), message_text, reply_markup=keyboard)
            except:
                bot.send_message(user_id, message_text, reply_markup=keyboard)
        elif menu_id == 17:  #
            pass
        elif menu_id == 18:  #
            pass
        elif menu_id == 19:  #
            pass
        elif menu_id == 20:  # Геолокация текущая
            bot.delete_message(chat_id=message.chat.id, message_id=int(user_info['message_id']))

            lat = 44.5555  # пока так
            long = 33.9561

            keyboard.row(types.InlineKeyboardButton(text="OK", callback_data=f"dgo_23"))
            keyboard.row(types.InlineKeyboardButton(text="Изменить", callback_data=f"dgo_21"))
            bot.send_location(chat_id=message.chat.id, longitude=long, latitude=lat, reply_markup=keyboard)

        elif menu_id == 21:  # Предупреждение об локации
            message_text = "Не забудьте включить геолокацию"
            keyboard.row(types.InlineKeyboardButton(text=f"Хорошо", callback_data=f"go_22"))
            try:
                bot.edit_message_text(user_id, int(user_info['message_id']), message_text, reply_markup=keyboard)
            except:
                bot.send_message(user_id, message_text, reply_markup=keyboard)

        elif menu_id == 22:  # Смена локации
            geo_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            geo_keyboard.row(types.KeyboardButton(text="Отправить геопозицию", request_location=True))
            message_text = "Ох...отправьте геопозицию текстом (через запятую) " \
                           "или просто нажмите на кнопку. А еще нажми /cancel для отмены"
            try:
                bot.edit_message_text(user_id, int(user_info['message_id']), message_text, reply_markup=geo_keyboard)
            except:
                bot.send_message(user_id, message_text, reply_markup=geo_keyboard)
        elif menu_id == 23:  # Уведомление о смене локации
            message_text = "Гуолокация подтвеждена"
            keyboard.row(types.InlineKeyboardButton(text=f"Ок", callback_data=f"go_{int(user_info['parent_menu'])}"))
            try:
                bot.edit_message_text(user_id, int(user_info['message_id']), message_text, reply_markup=keyboard)
            except:
                bot.send_message(user_id, message_text, reply_markup=keyboard)

        self.users.hmset(user_id, user_info)

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

                dist = get_distance(location['latitude'], location['longitude'],
                                    float(self.labels['geo_lat'][label_id]),
                                    float(self.labels['geo_long'][label_id]),
                                    )
                geo[int(label_id)] = dist
        # return dist
        sorted_list = sorted(geo, key=geo.get)
        result = []
        for key in sorted_list:
            result.append(key)
            result.append(int(geo[key] * 1000))
        return result

    # Получены координаты тем или иным образом
    def go_location(self, bot, message, location):
        user_id = message.chat.id

        menu_geo_list = [7, 22]

        if int(self.users.hget(user_id, 'menu') in menu_geo_list):
            self.users.hset(user_id, 'geo_lat', location['latitude'])
            self.users.hset(user_id, 'geo_long', location['longitude'])
            self.users.hset(user_id, 'parent_menu', 0)
            self.go_menu(bot, message, 20)

    def deploy(self):
        bot = telebot.TeleBot(os.environ['TELEGRAM_TOKEN_SPACE'])

        # Стартовое сообщение
        @bot.message_handler(commands=['start'])
        def start_message(message):
            user_id = message.chat.id
            try:
                bot.delete_message(chat_id=message.chat.id, message_id=int(self.users.hget(user_id, 'message_id')))
                self.users.hdel(user_id, 'message_id')
            except Exception as error:
                print("Error: ", error)

            bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
            welcome_text = f"Приветствую, %USERNAME%! Эта версия бота не так функциональна, как ты бы хотел видеть, " \
                           f"так что и описывать толком нечего, можешь погулять по менюшкам, но к базе всё равно " \
                           f"подключения ещё нет "
            keyboard = types.InlineKeyboardMarkup()
            self.users.hset(user_id, 'menu', -1)
            keyboard.row(types.InlineKeyboardButton(text=f"Хорошо, приступим!", callback_data=f"go_7"))
            bot.send_message(user_id, welcome_text, reply_markup=keyboard)

        # Отмена ввода
        @bot.message_handler(commands=['cancel'])
        def cancel_message(message):
            user_id = message.chat.id
            if int(self.users.hget(user_id, 'menu')) == 22:
                self.go_menu(bot, message, 20)
            bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)

        # Обработка всех текстовых команд
        @bot.message_handler(content_types=['text'])
        def message_text(message):
            user_id = message.chat.id

            # Введена строка для поиска
            if int(self.users.hget(user_id, 'menu')) == 0:
                self.users.hset(user_id, 'search_string', message.text)
                self.go_menu(bot, message, 6)

            # Введена описание
            if int(self.users.hget(user_id, 'menu')) == 14:
                # вбиваю описание в разные места, обрезав лишние символы
                self.go_menu(bot, message, 14)

            # Обработка отправления координат текстом
            if re.fullmatch("^(-?\d+(\.\d+)?),\s*(-?\d+(\.\d+)?)$", message.text):
                location = {'latitude': float(message.text.split(',')[0]),
                            'longitude': float(message.text.split(',')[1])}
                self.go_location(bot, message, location)

            wtf_label = "Метка ✳️ - это точка на карте, в которой происходит производство или реализация" \
                        " ваших товаров и услуг." \
                        " Например, это может быть точка продажи хлеба, сдаваемая в аренду недвижимость," \
                        " студия массажа, или, в случае, если у" \
                        " вас доставка по долине, место производства. Эта точка будет" \
                        " использоваться для навигации к вам, если это потребуется, или просто давать информацию" \
                        " о том, из какой части долины будет производиться доставка." \
                        " Что бы разместить метку следует прислать свою геолокацию нажав на кнопку" \
                        " 'Отправить геолокацию' (геолокация на телефоне должна быть включена)" \
                        " или отправив текстом координаты (через запятую) места, в котором хотите создать метку." \
                        " После создания точки на карте, укажите" \
                        " назавние и дайте краткое описание метки. Затем выберите подкатегорию (или несколько)," \
                        " в которых ваша метка будет отображаться при поиске пользователями сервиса." \
                        " В каждой подкатегории у вас может быть не более одной метки. После создания метки вы" \
                        " можете заполнить необзательные поля, такие как 'подробное описание' или 'цена'. Далее" \
                        " вам следует опубликовать метку нажав на соответствующую кнопку. Для удаления метки" \
                        " снимие её с публикации и она удалится из списка ваших меток через сутки."

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
            self.users.hset(user_id, 'message_id', call.message.message_id)  # Фиксируем ID сообщения

            # Передаём управление главной функции
            if call.data[:2] == "go":
                self.go_menu(bot, call.message, int(call.data.split('_')[1]))

            # Передаём управление главной функции с удалением предыдущего сообщения
            if call.data[:3] == "dgo":
                bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
                self.users.hdel(user_id, 'message_id')
                self.go_menu(bot, call.message, int(call.data.split('_')[1]))

            # Выбираем сферу для поиска
            if call.data[:4] == "ucat":
                category = call.data.split('_')[1]
                self.users.hdel(user_id, 'subcategory')
                self.users.hset(user_id, 'category', category)
                self.go_menu(bot, call.message, int(self.users.hget(user_id, 'parent_menu')))

            # Выбираем все сферы для поиска
            if call.data == "dcat":
                self.users.hdel(user_id, 'category')
                self.users.hdel(user_id, 'subcategory')
                self.go_menu(bot, call.message, int(self.users.hget(user_id, 'parent_menu')))

            # Выбираем направление для поиска
            if call.data[:4] == "usub":
                subcategory = call.data.split('_')[1]
                self.users.hset(user_id, 'subcategory', subcategory)
                self.go_menu(bot, call.message, int(self.users.hget(user_id, 'parent_menu')))

            # Выбираем все направления для поиска
            if call.data == "dsub":
                self.users.hdel(user_id, 'subcategory')
                self.go_menu(bot, call.message, int(self.users.hget(user_id, 'parent_menu')))

            # Выбран item
            if call.data[:6] == "select":
                new_item = call.data.split('_')[1]
                self.users.hset(user_id, 'item', new_item)
                self.go_menu(bot, call.message, int(self.users.hget(user_id, 'parent_menu')))

            # Отмечена подкатегория
            if call.data[:4] == "lcat":
                cat = call.data.split('_')[1]

                categories = []  # Извлекаем список направдлений у метки

                if cat in categories:
                    categories.remove(cat)
                else:
                    categories.append(cat)

                # Сохраняем список категорий

                self.go_menu(bot, call.message, 3)

            if call.data == "del_label":
                # Удаляю место из базы и из списка меток пользователя

                self.go_menu(bot, call.message, int(self.users.hget(user_id, 'parent_menu')))

            bot.answer_callback_query(call.id)

        bot.polling()


if __name__ == "__main__":
    space = Space()
    space.deploy()
