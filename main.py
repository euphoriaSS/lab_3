# main.py
import asyncio
import logging
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=os.getenv('BOT_TOKEN'))
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Конфигурация администраторов
ADMIN_IDS = [int(id) for id in os.getenv('ADMIN_IDS', '').split(',') if id]


# Класс для работы с базой данных
class Database:
    def __init__(self):
        self.users_file = 'users.txt'
        self.events_file = 'events.txt'
        self.registrations_file = 'registrations.txt'
        self.parent_consent_file = 'parent_consent.txt'
        self.init_files()

    def init_files(self):
        """Инициализация файлов с заголовками"""
        files_content = {
            self.users_file: 'user_id|username|first_name|last_name|registration_date|role\n',
            self.events_file: 'event_id|title|description|date|time|location|max_participants|current_participants\n',
            self.registrations_file: 'registration_id|user_id|event_id|registration_date|status\n',
            self.parent_consent_file: 'consent_id|user_id|event_id|consent|consent_date\n'
        }

        for file_path, header in files_content.items():
            if not os.path.exists(file_path):
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(header)

    def add_user(self, user_id, username, first_name, last_name):
        """Добавление пользователя в БД"""
        # Проверяем, существует ли уже пользователь
        if self.user_exists(user_id):
            return

        with open(self.users_file, 'a', encoding='utf-8') as f:
            f.write(f"{user_id}|{username}|{first_name}|{last_name}|{datetime.now()}|user\n")

    def user_exists(self, user_id):
        """Проверка существования пользователя"""
        try:
            with open(self.users_file, 'r', encoding='utf-8') as f:
                next(f)  # Пропускаем заголовок
                for line in f:
                    data = line.strip().split('|')
                    if int(data[0]) == user_id:
                        return True
            return False
        except:
            return False

    def get_user_role(self, user_id):
        """Получение роли пользователя"""
        try:
            with open(self.users_file, 'r', encoding='utf-8') as f:
                next(f)  # Пропускаем заголовок
                for line in f:
                    data = line.strip().split('|')
                    if int(data[0]) == user_id:
                        return data[5]
            return 'user'
        except:
            return 'user'

    def add_event(self, title, description, date, time, location, max_participants):
        """Добавление нового мероприятия"""
        # Генерируем ID мероприятия
        events = self.get_all_events()
        event_id = len(events) + 1

        with open(self.events_file, 'a', encoding='utf-8') as f:
            f.write(f"{event_id}|{title}|{description}|{date}|{time}|{location}|{max_participants}|0\n")
        return event_id

    def get_all_events(self):
        """Получение всех мероприятий"""
        events = []
        try:
            with open(self.events_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if len(lines) <= 1:  # Только заголовок
                    return events

                # Пропускаем заголовок
                for line in lines[1:]:
                    line = line.strip()
                    if not line:  # Пропускаем пустые строки
                        continue

                    data = line.split('|')
                    if len(data) >= 8:  # Проверяем, что все поля есть
                        event = {
                            'id': int(data[0]),
                            'title': data[1],
                            'description': data[2],
                            'date': data[3],
                            'time': data[4],
                            'location': data[5],
                            'max_participants': int(data[6]),
                            'current_participants': int(data[7])
                        }
                        events.append(event)
                    else:
                        logging.warning(f"Некорректная строка в файле мероприятий: {line}")
        except FileNotFoundError:
            logging.warning("Файл мероприятий не найден, создаем новый")
            self.init_files()
        except Exception as e:
            logging.error(f"Ошибка при чтении мероприятий: {e}")

        return events

    def get_event(self, event_id):
        """Получение конкретного мероприятия"""
        events = self.get_all_events()
        for event in events:
            if event['id'] == event_id:
                return event
        return None

    def register_for_event(self, user_id, event_id):
        """Регистрация на мероприятие"""
        # Проверяем, есть ли уже регистрация
        registrations = self.get_user_registrations(user_id)
        for reg in registrations:
            if reg['event_id'] == event_id:
                return False, "Вы уже зарегистрированы на это мероприятие"

        # Проверяем, есть ли места
        event = self.get_event(event_id)
        if not event:
            return False, "Мероприятие не найдено"

        if event['current_participants'] >= event['max_participants']:
            return False, "Нет свободных мест"

        # Регистрируем
        reg_id = len(self.get_all_registrations()) + 1
        with open(self.registrations_file, 'a', encoding='utf-8') as f:
            f.write(f"{reg_id}|{user_id}|{event_id}|{datetime.now()}|pending\n")

        # Обновляем количество участников в мероприятии
        self.update_event_participants(event_id, 1)

        return True, "Регистрация успешна! Требуется согласие родителей."

    def update_event_participants(self, event_id, change):
        """Обновление количества участников мероприятия"""
        events = self.get_all_events()
        with open(self.events_file, 'w', encoding='utf-8') as f:
            f.write('event_id|title|description|date|time|location|max_participants|current_participants\n')
            for event in events:
                if event['id'] == event_id:
                    event['current_participants'] += change
                    # Не допускаем отрицательного количества
                    if event['current_participants'] < 0:
                        event['current_participants'] = 0
                f.write(f"{event['id']}|{event['title']}|{event['description']}|{event['date']}|"
                        f"{event['time']}|{event['location']}|{event['max_participants']}|"
                        f"{event['current_participants']}\n")

    def get_user_registrations(self, user_id):
        """Получение регистраций пользователя"""
        registrations = []
        try:
            with open(self.registrations_file, 'r', encoding='utf-8') as f:
                next(f)
                for line in f:
                    data = line.strip().split('|')
                    if int(data[1]) == user_id:
                        registrations.append({
                            'id': int(data[0]),
                            'user_id': int(data[1]),
                            'event_id': int(data[2]),
                            'date': data[3],
                            'status': data[4]
                        })
        except Exception as e:
            logging.error(f"Ошибка при чтении регистраций: {e}")
        return registrations

    def get_all_registrations(self):
        """Получение всех регистраций"""
        registrations = []
        try:
            with open(self.registrations_file, 'r', encoding='utf-8') as f:
                next(f)
                for line in f:
                    data = line.strip().split('|')
                    registrations.append({
                        'id': int(data[0]),
                        'user_id': int(data[1]),
                        'event_id': int(data[2]),
                        'date': data[3],
                        'status': data[4]
                    })
        except Exception as e:
            logging.error(f"Ошибка при чтении регистраций: {e}")
        return registrations

    def save_parent_consent(self, user_id, event_id, consent):
        """Сохранение согласия родителей"""
        consents = self.get_all_consents()
        consent_id = len(consents) + 1
        with open(self.parent_consent_file, 'a', encoding='utf-8') as f:
            f.write(f"{consent_id}|{user_id}|{event_id}|{consent}|{datetime.now()}\n")

        # Обновляем статус регистрации
        self.update_registration_status(user_id, event_id, 'confirmed' if consent == 'yes' else 'cancelled')

        # Если согласие отрицательное, уменьшаем счетчик участников
        if consent == 'no':
            self.update_event_participants(event_id, -1)

    def update_registration_status(self, user_id, event_id, status):
        """Обновление статуса регистрации"""
        registrations = self.get_all_registrations()
        with open(self.registrations_file, 'w', encoding='utf-8') as f:
            f.write('registration_id|user_id|event_id|registration_date|status\n')
            for reg in registrations:
                if reg['user_id'] == user_id and reg['event_id'] == event_id:
                    reg['status'] = status
                f.write(f"{reg['id']}|{reg['user_id']}|{reg['event_id']}|{reg['date']}|{reg['status']}\n")

    def get_all_consents(self):
        """Получение всех согласий"""
        consents = []
        try:
            with open(self.parent_consent_file, 'r', encoding='utf-8') as f:
                next(f)
                for line in f:
                    data = line.strip().split('|')
                    consents.append({
                        'id': int(data[0]),
                        'user_id': int(data[1]),
                        'event_id': int(data[2]),
                        'consent': data[3],
                        'date': data[4]
                    })
        except Exception as e:
            logging.error(f"Ошибка при чтении согласий: {e}")
        return consents

    def get_event_participants(self, event_id):
        """Получение списка участников мероприятия"""
        participants = []
        registrations = self.get_all_registrations()

        # Загружаем пользователей
        users = {}
        try:
            with open(self.users_file, 'r', encoding='utf-8') as f:
                next(f)
                for line in f:
                    data = line.strip().split('|')
                    users[int(data[0])] = {
                        'username': data[1],
                        'first_name': data[2],
                        'last_name': data[3]  # Исправлено: правильная кавычка
                    }
        except Exception as e:
            logging.error(f"Ошибка при чтении пользователей: {e}")

        for reg in registrations:
            if reg['event_id'] == event_id and reg['status'] == 'confirmed':
                user = users.get(reg['user_id'], {})
                participants.append({
                    'user_id': reg['user_id'],
                    'username': user.get('username', ''),
                    'first_name': user.get('first_name', ''),
                    'last_name': user.get('last_name', ''),
                    'status': reg['status']
                })

        return participants


# Состояния для FSM
class EventStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_location = State()
    waiting_for_max_participants = State()


# Инициализация базы данных
db = Database()


# Функция для получения главной клавиатуры
def get_main_keyboard(user_id):
    keyboard = InlineKeyboardMarkup(row_width=2)

    # Общие кнопки для всех пользователей
    keyboard.add(
        InlineKeyboardButton("📅 Список мероприятий", callback_data="events_list"),
        InlineKeyboardButton("📋 Мои регистрации", callback_data="my_registrations")
    )
    keyboard.add(
        InlineKeyboardButton("ℹ️ О боте", callback_data="about"),
        InlineKeyboardButton("❓ Помощь", callback_data="help")
    )

    # Дополнительные кнопки для администратора
    if user_id in ADMIN_IDS or db.get_user_role(user_id) == 'admin':
        keyboard.add(
            InlineKeyboardButton("➕ Добавить мероприятие", callback_data="add_event"),
            InlineKeyboardButton("📊 Отчеты", callback_data="reports")
        )

    return keyboard


# Обработчики команд
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or ''
    first_name = message.from_user.first_name or ''
    last_name = message.from_user.last_name or ''

    # Сохраняем пользователя в БД
    db.add_user(user_id, username, first_name, last_name)

    # Приветствие с обращением по имени
    greeting = f"👋 Здравствуйте, {first_name}!\n\n"
    greeting += "Я бот для выбора мероприятий и экскурсий для школьников. "
    greeting += "С моей помощью вы можете:\n"
    greeting += "• Просматривать доступные мероприятия\n"
    greeting += "• Регистрироваться на экскурсии\n"
    greeting += "• Давать согласие родителей\n"
    greeting += "• Получать информацию о событиях\n\n"
    greeting += "Выберите действие:"

    await message.answer(greeting, reply_markup=get_main_keyboard(user_id))


@dp.message_handler(commands=['help'])
async def cmd_help(message: types.Message):
    help_text = "📚 <b>Справка по использованию бота:</b>\n\n"
    help_text += "<b>Команды:</b>\n"
    help_text += "• /start - Начать работу с ботом\n"
    help_text += "• /help - Показать эту справку\n"
    help_text += "• /menu - Показать главное меню\n"
    help_text += "• /events - Список мероприятий\n"
    help_text += "• /my_events - Мои регистрации\n\n"
    help_text += "<b>Как пользоваться:</b>\n"
    help_text += "1. Просмотрите список доступных мероприятий\n"
    help_text += "2. Выберите интересующее мероприятие\n"
    help_text += "3. Зарегистрируйтесь и подтвердите согласие родителей\n\n"
    help_text += "Если у вас возникли проблемы, обратитесь к администратору."

    await message.answer(help_text, parse_mode=types.ParseMode.HTML)


@dp.message_handler(commands=['menu'])
async def cmd_menu(message: types.Message):
    await message.answer("Главное меню:", reply_markup=get_main_keyboard(message.from_user.id))


@dp.message_handler(commands=['events'])
async def cmd_events(message: types.Message):
    """Обработчик команды /events - показывает список мероприятий"""
    events = db.get_all_events()

    if not events:
        await message.answer("📭 На данный момент нет доступных мероприятий.")
        return

    keyboard = InlineKeyboardMarkup(row_width=1)
    for event in events:
        if event['current_participants'] < event['max_participants']:
            status = "✅ Есть места"
        else:
            status = "❌ Мест нет"

        button_text = f"{event['title']} ({event['date']}) - {status}"
        keyboard.add(InlineKeyboardButton(button_text, callback_data=f"event_{event['id']}"))

    keyboard.add(InlineKeyboardButton("« В меню", callback_data="back_to_menu"))

    await message.answer("📅 Доступные мероприятия:", reply_markup=keyboard)


@dp.message_handler(commands=['my_events'])
async def cmd_my_events(message: types.Message):
    """Обработчик команды /my_events - показывает регистрации пользователя"""
    registrations = db.get_user_registrations(message.from_user.id)

    if not registrations:
        await message.answer("📭 У вас нет активных регистраций.")
        return

    response = "📋 <b>Ваши регистрации:</b>\n\n"

    for reg in registrations:
        event = db.get_event(reg['event_id'])
        if event:
            status_emoji = "✅" if reg['status'] == 'confirmed' else "⏳"
            status_text = "Подтверждено" if reg['status'] == 'confirmed' else "Ожидает согласия"
            response += f"{status_emoji} <b>{event['title']}</b>\n"
            response += f"   Дата: {event['date']}\n"
            response += f"   Статус: {status_text}\n\n"

    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("« В меню", callback_data="back_to_menu")
    )

    await message.answer(response, reply_markup=keyboard, parse_mode=types.ParseMode.HTML)


# Обработчики callback-запросов
@dp.callback_query_handler(lambda c: c.data == "events_list")
async def process_events_list(callback_query: CallbackQuery):
    await bot.answer_callback_query(callback_query.id)

    try:
        # Принудительно загружаем свежие данные
        events = db.get_all_events()

        if not events:
            await bot.send_message(callback_query.from_user.id,
                                   "📭 На данный момент нет доступных мероприятий.")
            return

        keyboard = InlineKeyboardMarkup(row_width=1)
        for event in events:
            # Проверяем, что все необходимые ключи есть в словаре
            if all(key in event for key in ['title', 'date', 'current_participants', 'max_participants', 'id']):
                if event['current_participants'] < event['max_participants']:
                    status = "✅ Есть места"
                else:
                    status = "❌ Мест нет"

                # Упрощенный текст кнопки без лишних символов
                button_text = f"{event['title']} ({event['date']}) - {status}"
                keyboard.add(InlineKeyboardButton(button_text, callback_data=f"event_{event['id']}"))

        keyboard.add(InlineKeyboardButton("« В меню", callback_data="back_to_menu"))

        await bot.send_message(callback_query.from_user.id,
                               "📅 Доступные мероприятия:",
                               reply_markup=keyboard)
    except Exception as e:
        logging.error(f"Ошибка в process_events_list: {e}")
        await bot.send_message(callback_query.from_user.id,
                               f"Произошла ошибка при загрузке списка мероприятий: {str(e)}")

@dp.callback_query_handler(lambda c: c.data.startswith("event_"))
async def process_event_detail(callback_query: CallbackQuery):
    await bot.answer_callback_query(callback_query.id)

    event_id = int(callback_query.data.split("_")[1])
    event = db.get_event(event_id)

    if not event:
        await bot.send_message(callback_query.from_user.id,
                               "Мероприятие не найдено.")
        return

    # Формируем карточку события
    event_card = f"🎫 <b>{event['title']}</b>\n\n"
    event_card += f"📝 {event['description']}\n\n"
    event_card += f"📅 Дата: {event['date']}\n"
    event_card += f"⏰ Время: {event['time']}\n"
    event_card += f"📍 Место: {event['location']}\n"
    event_card += f"👥 Участники: {event['current_participants']}/{event['max_participants']}\n\n"

    if event['current_participants'] >= event['max_participants']:
        event_card += "❌ <b>Мест нет</b>"
    else:
        event_card += "✅ <b>Есть свободные места</b>"

    # Кнопки для действия
    keyboard = InlineKeyboardMarkup(row_width=2)

    # Проверяем, зарегистрирован ли пользователь
    user_registrations = db.get_user_registrations(callback_query.from_user.id)
    is_registered = any(reg['event_id'] == event_id for reg in user_registrations)

    if not is_registered and event['current_participants'] < event['max_participants']:
        keyboard.add(InlineKeyboardButton("📝 Записаться", callback_data=f"register_{event_id}"))

    keyboard.add(
        InlineKeyboardButton("« К списку", callback_data="events_list"),
        InlineKeyboardButton("« В меню", callback_data="back_to_menu")
    )

    await bot.send_message(callback_query.from_user.id,
                           event_card,
                           reply_markup=keyboard,
                           parse_mode=types.ParseMode.HTML)


@dp.callback_query_handler(lambda c: c.data.startswith("register_"))
async def process_register(callback_query: CallbackQuery):
    await bot.answer_callback_query(callback_query.id)

    event_id = int(callback_query.data.split("_")[1])
    user_id = callback_query.from_user.id

    success, message = db.register_for_event(user_id, event_id)

    if success:
        # Запрашиваем согласие родителей
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("✅ Да", callback_data=f"consent_yes_{event_id}"),
            InlineKeyboardButton("❌ Нет", callback_data=f"consent_no_{event_id}")
        )

        await bot.send_message(user_id,
                               "👪 <b>Требуется согласие родителей</b>\n\n"
                               "Для участия в мероприятии необходимо согласие родителей.\n\n"
                               "Вы даете согласие?",
                               reply_markup=keyboard,
                               parse_mode=types.ParseMode.HTML)
    else:
        await bot.send_message(user_id, f"❌ {message}")


@dp.callback_query_handler(lambda c: c.data.startswith("consent_"))
async def process_parent_consent(callback_query: CallbackQuery):
    await bot.answer_callback_query(callback_query.id)

    parts = callback_query.data.split("_")
    consent = parts[1]
    event_id = int(parts[2])
    user_id = callback_query.from_user.id

    db.save_parent_consent(user_id, event_id, consent)

    if consent == 'yes':
        await bot.send_message(callback_query.from_user.id,
                               "✅ <b>Спасибо!</b>\n\n"
                               "Согласие родителей получено.\n"
                               "Вы успешно зарегистрированы на мероприятие.",
                               parse_mode=types.ParseMode.HTML)
    else:
        await bot.send_message(callback_query.from_user.id,
                               "❌ <b>Регистрация отменена</b>\n\n"
                               "Для участия в мероприятии требуется согласие родителей.\n"
                               "Вы можете записаться на другое мероприятие.",
                               parse_mode=types.ParseMode.HTML)


@dp.callback_query_handler(lambda c: c.data == "my_registrations")
async def process_my_registrations(callback_query: CallbackQuery):
    await bot.answer_callback_query(callback_query.id)

    registrations = db.get_user_registrations(callback_query.from_user.id)

    if not registrations:
        await bot.send_message(callback_query.from_user.id,
                               "📭 У вас нет активных регистраций.")
        return

    response = "📋 <b>Ваши регистрации:</b>\n\n"

    for reg in registrations:
        event = db.get_event(reg['event_id'])
        if event:
            status_emoji = "✅" if reg['status'] == 'confirmed' else "⏳"
            status_text = "Подтверждено" if reg['status'] == 'confirmed' else "Ожидает согласия"
            response += f"{status_emoji} <b>{event['title']}</b>\n"
            response += f"   Дата: {event['date']}\n"
            response += f"   Статус: {status_text}\n\n"

    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("« В меню", callback_data="back_to_menu")
    )

    await bot.send_message(callback_query.from_user.id,
                           response,
                           reply_markup=keyboard,
                           parse_mode=types.ParseMode.HTML)


@dp.callback_query_handler(lambda c: c.data == "about")
async def process_about(callback_query: CallbackQuery):
    await bot.answer_callback_query(callback_query.id)

    about_text = "ℹ️ <b>О боте</b>\n\n"
    about_text += "Этот бот создан для организации мероприятий и экскурсий для школьников.\n\n"
    about_text += "<b>Возможности:</b>\n"
    about_text += "• Просмотр доступных мероприятий (/events)\n"
    about_text += "• Регистрация на экскурсии\n"
    about_text += "• Сбор согласий родителей\n"
    about_text += "• Просмотр своих регистраций (/my_events)\n"
    about_text += "• Управление мероприятиями (для администраторов)\n\n"
    about_text += "<b>Команды:</b>\n"
    about_text += "• /start - Начать работу\n"
    about_text += "• /help - Справка\n"
    about_text += "• /menu - Главное меню\n"
    about_text += "• /events - Список мероприятий\n"
    about_text += "• /my_events - Мои регистрации\n\n"
    about_text += "Версия: 1.0\n"
    about_text += "Разработчик: @your_username"

    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("« В меню", callback_data="back_to_menu")
    )

    await bot.send_message(callback_query.from_user.id,
                           about_text,
                           reply_markup=keyboard,
                           parse_mode=types.ParseMode.HTML)


@dp.callback_query_handler(lambda c: c.data == "help")
async def process_help(callback_query: CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await cmd_help(callback_query.message)


@dp.callback_query_handler(lambda c: c.data == "back_to_menu")
async def process_back_to_menu(callback_query: CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id,
                           "Главное меню:",
                           reply_markup=get_main_keyboard(callback_query.from_user.id))


# Административные функции
@dp.callback_query_handler(lambda c: c.data == "add_event")
async def process_add_event(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id

    if user_id not in ADMIN_IDS and db.get_user_role(user_id) != 'admin':
        await bot.answer_callback_query(callback_query.id, "У вас нет прав администратора", show_alert=True)
        return

    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(user_id,
                           "➕ <b>Добавление нового мероприятия</b>\n\n"
                           "Введите название мероприятия:",
                           parse_mode=types.ParseMode.HTML)
    await EventStates.waiting_for_title.set()


@dp.message_handler(state=EventStates.waiting_for_title)
async def process_event_title(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['title'] = message.text

    await message.answer("Введите описание мероприятия:")
    await EventStates.waiting_for_description.set()


@dp.message_handler(state=EventStates.waiting_for_description)
async def process_event_description(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['description'] = message.text

    await message.answer("Введите дату мероприятия (в формате ДД.ММ.ГГГГ):")
    await EventStates.waiting_for_date.set()


@dp.message_handler(state=EventStates.waiting_for_date)
async def process_event_date(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['date'] = message.text

    await message.answer("Введите время мероприятия (в формате ЧЧ:ММ):")
    await EventStates.waiting_for_time.set()


@dp.message_handler(state=EventStates.waiting_for_time)
async def process_event_time(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['time'] = message.text

    await message.answer("Введите место проведения:")
    await EventStates.waiting_for_location.set()


@dp.message_handler(state=EventStates.waiting_for_location)
async def process_event_location(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['location'] = message.text

    await message.answer("Введите максимальное количество участников (число):")
    await EventStates.waiting_for_max_participants.set()


@dp.message_handler(state=EventStates.waiting_for_max_participants)
async def process_event_max_participants(message: types.Message, state: FSMContext):
    try:
        max_participants = int(message.text)
        if max_participants <= 0:
            await message.answer("Пожалуйста, введите положительное число.")
            return
    except ValueError:
        await message.answer("Пожалуйста, введите число.")
        return

    async with state.proxy() as data:
        event_id = db.add_event(
            data['title'],
            data['description'],
            data['date'],
            data['time'],
            data['location'],
            max_participants
        )

    await message.answer(f"✅ <b>Мероприятие успешно создано!</b>\n\n"
                         f"ID мероприятия: {event_id}\n"
                         f"Название: {data['title']}\n"
                         f"Дата: {data['date']}\n"
                         f"Время: {data['time']}\n"
                         f"Место: {data['location']}\n"
                         f"Макс. участников: {max_participants}",
                         parse_mode=types.ParseMode.HTML)
    await state.finish()


@dp.callback_query_handler(lambda c: c.data == "reports")
async def process_reports(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id

    if user_id not in ADMIN_IDS and db.get_user_role(user_id) != 'admin':
        await bot.answer_callback_query(callback_query.id, "У вас нет прав администратора", show_alert=True)
        return

    await bot.answer_callback_query(callback_query.id)

    events = db.get_all_events()

    if not events:
        await bot.send_message(user_id, "📭 Нет мероприятий для формирования отчетов.")
        return

    keyboard = InlineKeyboardMarkup(row_width=1)
    for event in events:
        keyboard.add(InlineKeyboardButton(
            f"📊 {event['title']} ({event['date']})",
            callback_data=f"report_{event['id']}"
        ))

    keyboard.add(InlineKeyboardButton("« Назад", callback_data="back_to_menu"))

    await bot.send_message(user_id,
                           "📊 <b>Выберите мероприятие для выгрузки списка участников:</b>",
                           reply_markup=keyboard,
                           parse_mode=types.ParseMode.HTML)


@dp.callback_query_handler(lambda c: c.data.startswith("report_"))
async def process_event_report(callback_query: CallbackQuery):
    await bot.answer_callback_query(callback_query.id)

    event_id = int(callback_query.data.split("_")[1])
    event = db.get_event(event_id)

    if not event:
        await bot.send_message(callback_query.from_user.id, "Мероприятие не найдено.")
        return

    participants = db.get_event_participants(event_id)

    if not participants:
        await bot.send_message(callback_query.from_user.id,
                               f"На мероприятие '{event['title']}' еще никто не записался.")
        return

    # Формируем отчет
    report = f"📊 <b>Отчет по мероприятию: {event['title']}</b>\n\n"
    report += f"📅 Дата: {event['date']}\n"
    report += f"⏰ Время: {event['time']}\n"
    report += f"📍 Место: {event['location']}\n"
    report += f"👥 Участников: {len(participants)}/{event['max_participants']}\n\n"
    report += "<b>Список участников:</b>\n"

    for i, participant in enumerate(participants, 1):
        full_name = f"{participant['first_name']} {participant['last_name']}".strip()
        if not full_name:
            full_name = f"@{participant['username']}" if participant['username'] else f"ID: {participant['user_id']}"

        report += f"{i}. {full_name}\n"

    # Сохраняем отчет в файл
    filename = f"report_event_{event_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(filename, 'w', encoding='utf-8') as f:
        # Убираем HTML теги для текстового файла
        clean_report = report.replace('<b>', '').replace('</b>', '')
        f.write(clean_report)

    # Отправляем файл
    with open(filename, 'rb') as f:
        await bot.send_document(
            callback_query.from_user.id,
            f,
            caption=f"📊 Отчет по мероприятию: {event['title']}"
        )

    # Удаляем временный файл
    os.remove(filename)


@dp.message_handler()
async def handle_unknown(message: types.Message):
    """Обработчик неизвестных команд"""
    await message.answer(
        "🤔 Извините, я не понимаю эту команду.\n"
        "Используйте /help для получения списка доступных команд."
    )


async def main():
    """Главная функция запуска бота"""
    logging.info("Бот запущен и готов к работе!")
    await dp.start_polling()


if __name__ == '__main__':
    asyncio.run(main())


def update_event_participants(self, event_id, change):
    """Обновление количества участников мероприятия"""
    events = self.get_all_events()
    logging.info(f"Обновление участников: событие {event_id}, изменение {change}")

    with open(self.events_file, 'w', encoding='utf-8') as f:
        f.write('event_id|title|description|date|time|location|max_participants|current_participants\n')
        for event in events:
            if event['id'] == event_id:
                old_count = event['current_participants']
                event['current_participants'] += change
                if event['current_participants'] < 0:
                    event['current_participants'] = 0
                logging.info(f"Событие {event_id}: было {old_count}, стало {event['current_participants']}")
            f.write(f"{event['id']}|{event['title']}|{event['description']}|{event['date']}|"
                    f"{event['time']}|{event['location']}|{event['max_participants']}|"
                    f"{event['current_participants']}\n")