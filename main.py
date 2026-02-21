# main.py
import asyncio
import logging
import os
import calendar
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

# Функция для создания клавиатуры с кнопкой меню
def get_back_to_menu_keyboard():
    """Возвращает клавиатуру с кнопкой возврата в меню"""
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("« Главное меню", callback_data="back_to_menu")
    )
    return keyboard

# Функция для создания клавиатуры с кнопкой меню и дополнительными кнопками
def get_keyboard_with_menu(buttons=None, row_width=2):
    """Создает клавиатуру с кнопками и кнопкой меню внизу"""
    keyboard = InlineKeyboardMarkup(row_width=row_width)
    
    if buttons:
        for button in buttons:
            if isinstance(button, list):
                keyboard.add(*button)
            else:
                keyboard.add(button)
    
    keyboard.add(InlineKeyboardButton("« Главное меню", callback_data="back_to_menu"))
    return keyboard

# Функции для проверки формата даты и времени
def validate_date(date_str):
    """Проверяет, что дата в формате ДД.ММ.ГГГГ и корректна"""
    try:
        # Проверяем формат
        if len(date_str) != 10:
            return False, "Дата должна быть в формате ДД.ММ.ГГГГ (10 символов)"
        
        # Разбиваем на части
        parts = date_str.split('.')
        if len(parts) != 3:
            return False, "Дата должна содержать день, месяц и год, разделенные точками"
        
        day, month, year = parts
        
        # Проверяем, что это числа
        if not day.isdigit() or not month.isdigit() or not year.isdigit():
            return False, "День, месяц и год должны быть числами"
        
        day = int(day)
        month = int(month)
        year = int(year)
        
        # Проверяем диапазоны
        if day < 1 or day > 31:
            return False, "День должен быть от 1 до 31"
        if month < 1 or month > 12:
            return False, "Месяц должен быть от 1 до 12"
        if year < 2024 or year > 2025:
            return False, "Год должен быть 2024 или 2025"
        
        # Проверяем корректность даты (учет дней в месяце)
        max_days = calendar.monthrange(year, month)[1]
        if day > max_days:
            months_ru = {
                1: "январе", 2: "феврале", 3: "марте", 4: "апреле",
                5: "мае", 6: "июне", 7: "июле", 8: "августе",
                9: "сентябре", 10: "октябре", 11: "ноябре", 12: "декабре"
            }
            return False, f"В {months_ru[month]} только {max_days} дней"
        
        return True, "Дата корректна"
    except Exception as e:
        return False, f"Ошибка в формате даты: {str(e)}"

def validate_time(time_str):
    """Проверяет, что время в формате ЧЧ:ММ"""
    try:
        # Проверяем формат
        if len(time_str) != 5:
            return False, "Время должно быть в формате ЧЧ:ММ (5 символов, например 14:30)"
        
        # Разбиваем на части
        parts = time_str.split(':')
        if len(parts) != 2:
            return False, "Время должно содержать часы и минуты, разделенные двоеточием"
        
        hours, minutes = parts
        
        # Проверяем, что это числа
        if not hours.isdigit() or not minutes.isdigit():
            return False, "Часы и минуты должны быть числами"
        
        hours = int(hours)
        minutes = int(minutes)
        
        # Проверяем диапазоны
        if hours < 0 or hours > 23:
            return False, "Часы должны быть от 0 до 23"
        if minutes < 0 or minutes > 59:
            return False, "Минуты должны быть от 0 до 59"
        
        return True, "Время корректно"
    except Exception as e:
        return False, f"Ошибка в формате времени: {str(e)}"

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
        if self.user_exists(user_id):
            return
        
        with open(self.users_file, 'a', encoding='utf-8') as f:
            f.write(f"{user_id}|{username}|{first_name}|{last_name}|{datetime.now()}|user\n")
    
    def user_exists(self, user_id):
        """Проверка существования пользователя"""
        try:
            with open(self.users_file, 'r', encoding='utf-8') as f:
                next(f)
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
                next(f)
                for line in f:
                    data = line.strip().split('|')
                    if int(data[0]) == user_id:
                        return data[5]
            return 'user'
        except:
            return 'user'
    
    def add_event(self, title, description, date, time, location, max_participants):
        """Добавление нового мероприятия"""
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
                if len(lines) <= 1:
                    return events
                
                for line in lines[1:]:
                    line = line.strip()
                    if not line:
                        continue
                        
                    data = line.split('|')
                    if len(data) >= 8:
                        events.append({
                            'id': int(data[0]),
                            'title': data[1],
                            'description': data[2],
                            'date': data[3],
                            'time': data[4],
                            'location': data[5],
                            'max_participants': int(data[6]),
                            'current_participants': int(data[7])
                        })
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
        registrations = self.get_user_registrations(user_id)
        for reg in registrations:
            if reg['event_id'] == event_id:
                return False, "Вы уже зарегистрированы на это мероприятие"
        
        event = self.get_event(event_id)
        if not event:
            return False, "Мероприятие не найдено"
        
        if event['current_participants'] >= event['max_participants']:
            return False, "Нет свободных мест"
        
        reg_id = len(self.get_all_registrations()) + 1
        with open(self.registrations_file, 'a', encoding='utf-8') as f:
            f.write(f"{reg_id}|{user_id}|{event_id}|{datetime.now()}|pending\n")
        
        self.update_event_participants(event_id, 1)
        return True, "Регистрация успешна! Требуется согласие родителей."
    
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
        
        self.update_registration_status(user_id, event_id, 'confirmed' if consent == 'yes' else 'cancelled')
        
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
        
        users = {}
        try:
            with open(self.users_file, 'r', encoding='utf-8') as f:
                next(f)
                for line in f:
                    data = line.strip().split('|')
                    users[int(data[0])] = {
                        'username': data[1],
                        'first_name': data[2],
                        'last_name': data[3]
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
    
    def delete_event(self, event_id):
        """Удаление мероприятия"""
        events = self.get_all_events()
        
        participants = self.get_event_participants(event_id)
        if participants:
            return False, f"Нельзя удалить мероприятие, на которое записано {len(participants)} участников"
        
        with open(self.events_file, 'w', encoding='utf-8') as f:
            f.write('event_id|title|description|date|time|location|max_participants|current_participants\n')
            for event in events:
                if event['id'] != event_id:
                    f.write(f"{event['id']}|{event['title']}|{event['description']}|{event['date']}|"
                           f"{event['time']}|{event['location']}|{event['max_participants']}|"
                           f"{event['current_participants']}\n")
        
        return True, "Мероприятие успешно удалено"
    
    def cancel_registration(self, user_id, event_id):
        """Отмена регистрации на мероприятие"""
        registrations = self.get_all_registrations()
        registration_found = False
        
        with open(self.registrations_file, 'w', encoding='utf-8') as f:
            f.write('registration_id|user_id|event_id|registration_date|status\n')
            for reg in registrations:
                if reg['user_id'] == user_id and reg['event_id'] == event_id:
                    registration_found = True
                    continue
                f.write(f"{reg['id']}|{reg['user_id']}|{reg['event_id']}|{reg['date']}|{reg['status']}\n")
        
        if registration_found:
            self.update_event_participants(event_id, -1)
            self.delete_parent_consent(user_id, event_id)
            return True, "Регистрация успешно отменена"
        else:
            return False, "Регистрация не найдена"
    
    def delete_parent_consent(self, user_id, event_id):
        """Удаление согласия родителей"""
        consents = self.get_all_consents()
        with open(self.parent_consent_file, 'w', encoding='utf-8') as f:
            f.write('consent_id|user_id|event_id|consent|consent_date\n')
            for consent in consents:
                if not (consent['user_id'] == user_id and consent['event_id'] == event_id):
                    f.write(f"{consent['id']}|{consent['user_id']}|{consent['event_id']}|"
                           f"{consent['consent']}|{consent['date']}\n")

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
    
    keyboard.add(
        InlineKeyboardButton("📅 Список мероприятий", callback_data="events_list"),
        InlineKeyboardButton("📋 Мои регистрации", callback_data="my_registrations")
    )
    keyboard.add(
        InlineKeyboardButton("ℹ️ О боте", callback_data="about"),
        InlineKeyboardButton("❓ Помощь", callback_data="help")
    )
    
    if user_id in ADMIN_IDS or db.get_user_role(user_id) == 'admin':
        keyboard.add(
            InlineKeyboardButton("➕ Добавить мероприятие", callback_data="add_event"),
            InlineKeyboardButton("📊 Отчеты", callback_data="reports")
        )
        keyboard.add(
            InlineKeyboardButton("🔧 Управление", callback_data="admin_panel")
        )
    
    return keyboard

# Обработчики команд
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or ''
    first_name = message.from_user.first_name or ''
    last_name = message.from_user.last_name or ''
    
    db.add_user(user_id, username, first_name, last_name)
    
    greeting = f"👋 Здравствуйте, {first_name}!\n\n"
    greeting += "Я бот для выбора мероприятий и экскурсий для школьников.\n"
    greeting += "С моей помощью вы можете:\n"
    greeting += "• Просматривать доступные мероприятия\n"
    greeting += "• Регистрироваться на экскурсии\n"
    greeting += "• Давать согласие родителей\n"
    greeting += "• Отменять регистрацию\n\n"
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
    help_text += "3. Зарегистрируйтесь и подтвердите согласие родителей\n"
    help_text += "4. При необходимости можно отменить регистрацию\n\n"
    help_text += "Если у вас возникли проблемы, обратитесь к администратору."
    
    await message.answer(help_text, parse_mode=types.ParseMode.HTML)

@dp.message_handler(commands=['menu'])
async def cmd_menu(message: types.Message):
    await message.answer("Главное меню:", reply_markup=get_main_keyboard(message.from_user.id))

@dp.message_handler(commands=['events'])
async def cmd_events(message: types.Message):
    events = db.get_all_events()
    
    if not events:
        await message.answer("📭 На данный момент нет доступных мероприятий.", 
                           reply_markup=get_back_to_menu_keyboard())
        return
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    for event in events:
        status = "✅ Есть места" if event['current_participants'] < event['max_participants'] else "❌ Мест нет"
        button_text = f"{event['title']} ({event['date']}) - {status}"
        keyboard.add(InlineKeyboardButton(button_text, callback_data=f"event_{event['id']}"))
    
    keyboard.add(InlineKeyboardButton("« Главное меню", callback_data="back_to_menu"))
    await message.answer("📅 Доступные мероприятия:", reply_markup=keyboard)

@dp.message_handler(commands=['my_events'])
async def cmd_my_events(message: types.Message):
    registrations = db.get_user_registrations(message.from_user.id)
    
    if not registrations:
        await message.answer("📭 У вас нет активных регистраций.", 
                           reply_markup=get_back_to_menu_keyboard())
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
        InlineKeyboardButton("« Главное меню", callback_data="back_to_menu")
    )
    
    await message.answer(response, reply_markup=keyboard, parse_mode=types.ParseMode.HTML)

# Обработчики callback-запросов
@dp.callback_query_handler(lambda c: c.data == "events_list")
async def process_events_list(callback_query: CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    
    events = db.get_all_events()
    
    if not events:
        await bot.send_message(callback_query.from_user.id, 
                             "📭 На данный момент нет доступных мероприятий.",
                             reply_markup=get_back_to_menu_keyboard())
        return
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    for event in events:
        status = "✅ Есть места" if event['current_participants'] < event['max_participants'] else "❌ Мест нет"
        button_text = f"{event['title']} ({event['date']}) - {status}"
        keyboard.add(InlineKeyboardButton(button_text, callback_data=f"event_{event['id']}"))
    
    keyboard.add(InlineKeyboardButton("« Главное меню", callback_data="back_to_menu"))
    
    await bot.send_message(callback_query.from_user.id, 
                         "📅 Доступные мероприятия:", 
                         reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith("event_"))
async def process_event_detail(callback_query: CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    
    event_id = int(callback_query.data.split("_")[1])
    event = db.get_event(event_id)
    
    if not event:
        await bot.send_message(callback_query.from_user.id, 
                             "Мероприятие не найдено.",
                             reply_markup=get_back_to_menu_keyboard())
        return
    
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
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    user_registrations = db.get_user_registrations(callback_query.from_user.id)
    is_registered = any(reg['event_id'] == event_id for reg in user_registrations)
    
    if not is_registered and event['current_participants'] < event['max_participants']:
        keyboard.add(InlineKeyboardButton("📝 Записаться", callback_data=f"register_{event_id}"))
    elif is_registered:
        keyboard.add(InlineKeyboardButton("❌ Отменить запись", callback_data=f"cancel_my_reg_{event_id}"))
    
    user_id = callback_query.from_user.id
    if user_id in ADMIN_IDS or db.get_user_role(user_id) == 'admin':
        keyboard.add(InlineKeyboardButton("🔧 Управление", callback_data=f"admin_event_{event_id}"))
    
    keyboard.add(
        InlineKeyboardButton("« К списку", callback_data="events_list"),
        InlineKeyboardButton("« Главное меню", callback_data="back_to_menu")
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
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("✅ Да", callback_data=f"consent_yes_{event_id}"),
            InlineKeyboardButton("❌ Нет", callback_data=f"consent_no_{event_id}")
        )
        keyboard.add(InlineKeyboardButton("« Главное меню", callback_data="back_to_menu"))
        
        await bot.send_message(user_id, 
                             "👪 <b>Требуется согласие родителей</b>\n\n"
                             "Для участия в мероприятии необходимо согласие родителей.\n\n"
                             "Вы даете согласие?",
                             reply_markup=keyboard,
                             parse_mode=types.ParseMode.HTML)
    else:
        await bot.send_message(user_id, f"❌ {message}", 
                             reply_markup=get_back_to_menu_keyboard())

@dp.callback_query_handler(lambda c: c.data.startswith("consent_"))
async def process_parent_consent(callback_query: CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    
    parts = callback_query.data.split("_")
    consent = parts[1]
    event_id = int(parts[2])
    user_id = callback_query.from_user.id
    
    db.save_parent_consent(user_id, event_id, consent)
    
    # Создаем клавиатуру с кнопками
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📅 К мероприятиям", callback_data="events_list"),
        InlineKeyboardButton("📋 Мои регистрации", callback_data="my_registrations")
    )
    keyboard.add(InlineKeyboardButton("« Главное меню", callback_data="back_to_menu"))
    
    if consent == 'yes':
        await bot.send_message(callback_query.from_user.id,
                             "✅ <b>Спасибо!</b>\n\n"
                             "Согласие родителей получено.\n"
                             "Вы успешно зарегистрированы на мероприятие.",
                             reply_markup=keyboard,
                             parse_mode=types.ParseMode.HTML)
    else:
        await bot.send_message(callback_query.from_user.id,
                             "❌ <b>Регистрация отменена</b>\n\n"
                             "Для участия в мероприятии требуется согласие родителей.",
                             reply_markup=keyboard,
                             parse_mode=types.ParseMode.HTML)

@dp.callback_query_handler(lambda c: c.data.startswith("cancel_my_reg_"))
async def process_cancel_my_registration(callback_query: CallbackQuery):
    event_id = int(callback_query.data.split("_")[3])
    user_id = callback_query.from_user.id
    event = db.get_event(event_id)
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✅ Да, отменить", callback_data=f"confirm_my_cancel_{event_id}"),
        InlineKeyboardButton("❌ Нет", callback_data=f"event_{event_id}")
    )
    keyboard.add(InlineKeyboardButton("« Главное меню", callback_data="back_to_menu"))
    
    await bot.send_message(user_id,
                         f"❓ Вы уверены, что хотите отменить регистрацию?\n\n"
                         f"🎫 {event['title']}\n"
                         f"📅 {event['date']}",
                         reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith("confirm_my_cancel_"))
async def process_confirm_my_cancel(callback_query: CallbackQuery):
    event_id = int(callback_query.data.split("_")[3])
    user_id = callback_query.from_user.id
    
    success, message = db.cancel_registration(user_id, event_id)
    
    keyboard = get_back_to_menu_keyboard()
    
    if success:
        await bot.send_message(user_id, f"✅ {message}", reply_markup=keyboard)
        
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id,
                                     f"👤 Пользователь отменил регистрацию\n\n"
                                     f"Мероприятие ID: {event_id}\n"
                                     f"Пользователь ID: {user_id}")
            except:
                pass
    else:
        await bot.send_message(user_id, f"❌ {message}", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == "my_registrations")
async def process_my_registrations(callback_query: CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    
    registrations = db.get_user_registrations(callback_query.from_user.id)
    
    if not registrations:
        await bot.send_message(callback_query.from_user.id, 
                             "📭 У вас нет активных регистраций.",
                             reply_markup=get_back_to_menu_keyboard())
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
        InlineKeyboardButton("« Главное меню", callback_data="back_to_menu")
    )
    
    await bot.send_message(callback_query.from_user.id, 
                         response, 
                         reply_markup=keyboard,
                         parse_mode=types.ParseMode.HTML)

@dp.callback_query_handler(lambda c: c.data == "about")
async def process_about(callback_query: CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    
    about_text = "ℹ️ <b>О боте</b>\n\n"
    about_text += "Бот для организации мероприятий и экскурсий для школьников.\n\n"
    about_text += "<b>Возможности:</b>\n"
    about_text += "• Просмотр доступных мероприятий (/events)\n"
    about_text += "• Регистрация на экскурсии\n"
    about_text += "• Сбор согласий родителей\n"
    about_text += "• Отмена регистрации\n"
    about_text += "• Просмотр своих регистраций (/my_events)\n"
    about_text += "• Управление мероприятиями (для администраторов)\n\n"
    about_text += "<b>Команды:</b>\n"
    about_text += "• /start - Начать работу\n"
    about_text += "• /help - Справка\n"
    about_text += "• /menu - Главное меню\n"
    about_text += "• /events - Список мероприятий\n"
    about_text += "• /my_events - Мои регистрации\n\n"
    about_text += "Версия: 2.0"
    
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("« Главное меню", callback_data="back_to_menu")
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
@dp.callback_query_handler(lambda c: c.data == "admin_panel")
async def process_admin_panel(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    if user_id not in ADMIN_IDS and db.get_user_role(user_id) != 'admin':
        await bot.answer_callback_query(callback_query.id, "У вас нет прав администратора", show_alert=True)
        return
    
    text = "🔧 <b>Панель администратора</b>\n\nВыберите действие:"
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📅 Все мероприятия", callback_data="events_list"),
        InlineKeyboardButton("📊 Отчеты", callback_data="reports")
    )
    keyboard.add(
        InlineKeyboardButton("➕ Добавить мероприятие", callback_data="add_event"),
        InlineKeyboardButton("📋 Статистика", callback_data="stats")
    )
    keyboard.add(
        InlineKeyboardButton("« Главное меню", callback_data="back_to_menu")
    )
    
    await bot.send_message(user_id, text, reply_markup=keyboard, parse_mode=types.ParseMode.HTML)

@dp.callback_query_handler(lambda c: c.data == "stats")
async def process_stats(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    events = db.get_all_events()
    users_count = 0
    try:
        with open(db.users_file, 'r', encoding='utf-8') as f:
            users_count = len(f.readlines()) - 1
    except:
        pass
    
    total_registrations = len(db.get_all_registrations())
    confirmed_registrations = sum(1 for r in db.get_all_registrations() if r['status'] == 'confirmed')
    
    text = "📊 <b>Статистика бота</b>\n\n"
    text += f"👥 Пользователей: {users_count}\n"
    text += f"📅 Мероприятий: {len(events)}\n"
    text += f"📝 Всего регистраций: {total_registrations}\n"
    text += f"✅ Подтвержденных: {confirmed_registrations}\n"
    
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("« Назад", callback_data="admin_panel"),
        InlineKeyboardButton("« Главное меню", callback_data="back_to_menu")
    )
    
    await bot.send_message(user_id, text, reply_markup=keyboard, parse_mode=types.ParseMode.HTML)

@dp.callback_query_handler(lambda c: c.data == "add_event")
async def process_add_event(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    if user_id not in ADMIN_IDS and db.get_user_role(user_id) != 'admin':
        await bot.answer_callback_query(callback_query.id, "У вас нет прав администратора", show_alert=True)
        return
    
    await bot.answer_callback_query(callback_query.id)
    
    # Отправляем информационное сообщение с примерами
    info_text = "➕ <b>Добавление нового мероприятия</b>\n\n"
    info_text += "<b>Форматы ввода:</b>\n"
    info_text += "• 📅 Дата: <code>ДД.ММ.ГГГГ</code> (например: 25.12.2024)\n"
    info_text += "• ⏰ Время: <code>ЧЧ:ММ</code> (например: 14:30)\n"
    info_text += "• 👥 Количество участников: целое число\n\n"
    info_text += "Сейчас введите <b>название мероприятия</b>:"
    
    await bot.send_message(user_id, 
                         info_text,
                         reply_markup=get_back_to_menu_keyboard(),
                         parse_mode=types.ParseMode.HTML)
    await EventStates.waiting_for_title.set()

@dp.message_handler(state=EventStates.waiting_for_title)
async def process_event_title(message: types.Message, state: FSMContext):
    if not message.text or len(message.text.strip()) < 3:
        await message.answer("❌ Название должно содержать хотя бы 3 символа.\n"
                           "Пожалуйста, введите название еще раз:",
                           reply_markup=get_back_to_menu_keyboard())
        return
    
    async with state.proxy() as data:
        data['title'] = message.text.strip()
    
    await message.answer("✅ Название принято!\n\n"
                        "Введите описание мероприятия:",
                        reply_markup=get_back_to_menu_keyboard())
    await EventStates.waiting_for_description.set()

@dp.message_handler(state=EventStates.waiting_for_description)
async def process_event_description(message: types.Message, state: FSMContext):
    if not message.text or len(message.text.strip()) < 5:
        await message.answer("❌ Описание должно содержать хотя бы 5 символов.\n"
                           "Пожалуйста, введите описание еще раз:",
                           reply_markup=get_back_to_menu_keyboard())
        return
    
    async with state.proxy() as data:
        data['description'] = message.text.strip()
    
    examples = "✅ <b>Примеры правильных дат:</b>\n"
    examples += "• 25.12.2024\n"
    examples += "• 01.02.2024\n"
    examples += "• 15.05.2025\n\n"
    
    await message.answer("✅ Описание принято!\n\n"
                        f"{examples}"
                        "Введите дату мероприятия в формате ДД.ММ.ГГГГ:",
                        reply_markup=get_back_to_menu_keyboard(),
                        parse_mode=types.ParseMode.HTML)
    await EventStates.waiting_for_date.set()

@dp.message_handler(state=EventStates.waiting_for_date)
async def process_event_date(message: types.Message, state: FSMContext):
    date_str = message.text.strip()
    
    # Проверяем формат даты
    is_valid, error_message = validate_date(date_str)
    
    if not is_valid:
        # Показываем примеры правильных дат
        examples = "✅ <b>Примеры правильных дат:</b>\n"
        examples += "• 25.12.2024\n"
        examples += "• 01.02.2024\n"
        examples += "• 15.05.2025\n\n"
        
        await message.answer(f"❌ {error_message}\n\n"
                           f"{examples}"
                           "Пожалуйста, введите дату еще раз:",
                           reply_markup=get_back_to_menu_keyboard(),
                           parse_mode=types.ParseMode.HTML)
        return
    
    async with state.proxy() as data:
        data['date'] = date_str
    
    # Показываем примеры правильного времени
    time_examples = "✅ <b>Примеры правильного времени:</b>\n"
    time_examples += "• 09:00\n"
    time_examples += "• 14:30\n"
    time_examples += "• 18:45\n\n"
    
    await message.answer("✅ Дата принята!\n\n"
                        f"{time_examples}"
                        "Введите время мероприятия в формате ЧЧ:ММ:",
                        reply_markup=get_back_to_menu_keyboard(),
                        parse_mode=types.ParseMode.HTML)
    await EventStates.waiting_for_time.set()

@dp.message_handler(state=EventStates.waiting_for_time)
async def process_event_time(message: types.Message, state: FSMContext):
    time_str = message.text.strip()
    
    # Проверяем формат времени
    is_valid, error_message = validate_time(time_str)
    
    if not is_valid:
        examples = "✅ <b>Примеры правильного времени:</b>\n"
        examples += "• 09:00\n"
        examples += "• 14:30\n"
        examples += "• 18:45\n\n"
        
        await message.answer(f"❌ {error_message}\n\n"
                           f"{examples}"
                           "Пожалуйста, введите время еще раз:",
                           reply_markup=get_back_to_menu_keyboard(),
                           parse_mode=types.ParseMode.HTML)
        return
    
    async with state.proxy() as data:
        data['time'] = time_str
    
    await message.answer("✅ Время принято!\n\n"
                        "Введите место проведения:",
                        reply_markup=get_back_to_menu_keyboard())
    await EventStates.waiting_for_location.set()

@dp.message_handler(state=EventStates.waiting_for_location)
async def process_event_location(message: types.Message, state: FSMContext):
    if not message.text or len(message.text.strip()) < 3:
        await message.answer("❌ Место проведения должно содержать хотя бы 3 символа.\n"
                           "Пожалуйста, введите место еще раз:",
                           reply_markup=get_back_to_menu_keyboard())
        return
    
    async with state.proxy() as data:
        data['location'] = message.text.strip()
    
    await message.answer("✅ Место принято!\n\n"
                        "Введите максимальное количество участников (число от 1 до 100):\n"
                        "Например: 20",
                        reply_markup=get_back_to_menu_keyboard())
    await EventStates.waiting_for_max_participants.set()

@dp.message_handler(state=EventStates.waiting_for_max_participants)
async def process_event_max_participants(message: types.Message, state: FSMContext):
    try:
        max_participants = int(message.text.strip())
        if max_participants <= 0:
            await message.answer("❌ Количество участников должно быть положительным числом.\n"
                               "Пожалуйста, введите число еще раз:",
                               reply_markup=get_back_to_menu_keyboard())
            return
        if max_participants > 100:
            await message.answer("❌ Максимальное количество участников не может превышать 100.\n"
                               "Пожалуйста, введите число от 1 до 100:",
                               reply_markup=get_back_to_menu_keyboard())
            return
    except ValueError:
        await message.answer("❌ Пожалуйста, введите целое число.\n"
                           "Например: 20",
                           reply_markup=get_back_to_menu_keyboard())
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
    
    # Создаем клавиатуру с кнопками действий
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📅 К списку мероприятий", callback_data="events_list"),
        InlineKeyboardButton("➕ Добавить еще", callback_data="add_event")
    )
    keyboard.add(InlineKeyboardButton("« Главное меню", callback_data="back_to_menu"))
    
    await message.answer(f"✅ <b>Мероприятие успешно создано!</b>\n\n"
                         f"ID мероприятия: {event_id}\n"
                         f"Название: {data['title']}\n"
                         f"Дата: {data['date']}\n"
                         f"Время: {data['time']}\n"
                         f"Место: {data['location']}\n"
                         f"Макс. участников: {max_participants}",
                         reply_markup=keyboard,
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
        await bot.send_message(user_id, "📭 Нет мероприятий для формирования отчетов.",
                             reply_markup=get_back_to_menu_keyboard())
        return
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    for event in events:
        participants = db.get_event_participants(event['id'])
        count = len(participants)
        button_text = f"{event['title']} ({event['date']}) - {count} уч."
        keyboard.add(InlineKeyboardButton(button_text, callback_data=f"report_{event['id']}"))
    
    keyboard.add(InlineKeyboardButton("« Главное меню", callback_data="back_to_menu"))
    
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
        await bot.send_message(callback_query.from_user.id, 
                             "Мероприятие не найдено.",
                             reply_markup=get_back_to_menu_keyboard())
        return
    
    participants = db.get_event_participants(event_id)
    
    if not participants:
        await bot.send_message(callback_query.from_user.id,
                             f"На мероприятие '{event['title']}' еще никто не записался.",
                             reply_markup=get_back_to_menu_keyboard())
        return
    
    report = f"📊 ОТЧЕТ ПО МЕРОПРИЯТИЮ\n"
    report += "=" * 50 + "\n\n"
    report += f"📌 Название: {event['title']}\n"
    report += f"📝 Описание: {event['description']}\n"
    report += f"📅 Дата: {event['date']}\n"
    report += f"⏰ Время: {event['time']}\n"
    report += f"📍 Место: {event['location']}\n"
    report += f"👥 Всего мест: {event['max_participants']}\n"
    report += f"✅ Занято мест: {len(participants)}\n"
    report += f"❌ Свободно мест: {event['max_participants'] - len(participants)}\n\n"
    report += "СПИСОК УЧАСТНИКОВ:\n"
    report += "-" * 50 + "\n"
    
    for i, participant in enumerate(participants, 1):
        full_name = f"{participant['first_name']} {participant['last_name']}".strip()
        if not full_name:
            full_name = f"@{participant['username']}" if participant['username'] else f"ID: {participant['user_id']}"
        
        report += f"{i}. {full_name}\n"
        if participant['username']:
            report += f"   Telegram: @{participant['username']}\n"
    
    report += "\n" + "=" * 50 + "\n"
    report += f"Дата формирования: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    
    filename = f"otchet_{event['title']}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    filename = "".join(c for c in filename if c.isalnum() or c in ('._-', ' ')).strip()
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report)
    
    with open(filename, 'rb') as f:
        await bot.send_document(
            callback_query.from_user.id, 
            f, 
            caption=f"📊 Отчет: {event['title']} ({len(participants)} участников)"
        )
    
    os.remove(filename)
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📊 Другой отчет", callback_data="reports"),
        InlineKeyboardButton("« Главное меню", callback_data="back_to_menu")
    )
    
    await bot.send_message(callback_query.from_user.id,
                         "Что делаем дальше?",
                         reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith("admin_event_"))
async def process_admin_event(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    if user_id not in ADMIN_IDS and db.get_user_role(user_id) != 'admin':
        await bot.answer_callback_query(callback_query.id, "У вас нет прав администратора", show_alert=True)
        return
    
    event_id = int(callback_query.data.split("_")[2])
    event = db.get_event(event_id)
    
    if not event:
        await bot.send_message(user_id, "Мероприятие не найдено", 
                             reply_markup=get_back_to_menu_keyboard())
        return
    
    participants = db.get_event_participants(event_id)
    
    text = f"🔧 <b>Управление мероприятием</b>\n\n"
    text += f"🎫 <b>{event['title']}</b>\n"
    text += f"📅 {event['date']} в {event['time']}\n"
    text += f"👥 Участников: {len(participants)}/{event['max_participants']}\n\n"
    text += "Выберите действие:"
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📋 Список участников", callback_data=f"view_participants_{event_id}"),
        InlineKeyboardButton("❌ Удалить мероприятие", callback_data=f"delete_event_{event_id}")
    )
    keyboard.add(
        InlineKeyboardButton("« К списку", callback_data="events_list"),
        InlineKeyboardButton("« Главное меню", callback_data="back_to_menu")
    )
    
    await bot.send_message(user_id, text, reply_markup=keyboard, parse_mode=types.ParseMode.HTML)

@dp.callback_query_handler(lambda c: c.data.startswith("view_participants_"))
async def process_view_participants(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    if user_id not in ADMIN_IDS and db.get_user_role(user_id) != 'admin':
        await bot.answer_callback_query(callback_query.id, "У вас нет прав администратора", show_alert=True)
        return
    
    event_id = int(callback_query.data.split("_")[2])
    event = db.get_event(event_id)
    participants = db.get_event_participants(event_id)
    
    if not participants:
        await bot.send_message(user_id, 
                             f"На мероприятие '{event['title']}' никто не записался",
                             reply_markup=get_back_to_menu_keyboard())
        return
    
    text = f"📋 <b>Участники мероприятия: {event['title']}</b>\n\n"
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    for i, participant in enumerate(participants, 1):
        full_name = f"{participant['first_name']} {participant['last_name']}".strip()
        if not full_name:
            full_name = f"@{participant['username']}" if participant['username'] else f"ID: {participant['user_id']}"
        
        text += f"{i}. {full_name}\n"
        if participant['username']:
            text += f"   📱 @{participant['username']}\n"
        
        keyboard.add(InlineKeyboardButton(
            f"❌ Отменить: {full_name[:20]}", 
            callback_data=f"admin_cancel_{event_id}_{participant['user_id']}"
        ))
    
    keyboard.add(InlineKeyboardButton("« Назад", callback_data=f"admin_event_{event_id}"))
    keyboard.add(InlineKeyboardButton("« Главное меню", callback_data="back_to_menu"))
    
    await bot.send_message(user_id, text, reply_markup=keyboard, parse_mode=types.ParseMode.HTML)

@dp.callback_query_handler(lambda c: c.data.startswith("admin_cancel_"))
async def process_admin_cancel_registration(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    if user_id not in ADMIN_IDS and db.get_user_role(user_id) != 'admin':
        await bot.answer_callback_query(callback_query.id, "У вас нет прав администратора", show_alert=True)
        return
    
    parts = callback_query.data.split("_")
    event_id = int(parts[2])
    participant_id = int(parts[3])
    
    event = db.get_event(event_id)
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✅ Да, отменить", callback_data=f"confirm_admin_cancel_{event_id}_{participant_id}"),
        InlineKeyboardButton("❌ Нет", callback_data=f"view_participants_{event_id}")
    )
    keyboard.add(InlineKeyboardButton("« Главное меню", callback_data="back_to_menu"))
    
    await bot.send_message(user_id,
                         f"❓ Вы уверены, что хотите отменить регистрацию участника?\n\n"
                         f"Мероприятие: {event['title']}",
                         reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith("confirm_admin_cancel_"))
async def process_confirm_admin_cancel(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    parts = callback_query.data.split("_")
    event_id = int(parts[3])
    participant_id = int(parts[4])
    
    success, message = db.cancel_registration(participant_id, event_id)
    
    if success:
        try:
            await bot.send_message(participant_id,
                                 f"⚠️ <b>Внимание!</b>\n\n"
                                 f"Ваша регистрация на мероприятие была отменена администратором.",
                                 reply_markup=get_back_to_menu_keyboard(),
                                 parse_mode=types.ParseMode.HTML)
        except:
            pass
        
        await bot.send_message(user_id, f"✅ {message}")
        await process_view_participants(callback_query)
    else:
        await bot.send_message(user_id, f"❌ {message}", 
                             reply_markup=get_back_to_menu_keyboard())

@dp.callback_query_handler(lambda c: c.data.startswith("delete_event_"))
async def process_delete_event(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    if user_id not in ADMIN_IDS and db.get_user_role(user_id) != 'admin':
        await bot.answer_callback_query(callback_query.id, "У вас нет прав администратора", show_alert=True)
        return
    
    event_id = int(callback_query.data.split("_")[2])
    event = db.get_event(event_id)
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✅ Да, удалить", callback_data=f"confirm_delete_{event_id}"),
        InlineKeyboardButton("❌ Нет", callback_data=f"admin_event_{event_id}")
    )
    keyboard.add(InlineKeyboardButton("« Главное меню", callback_data="back_to_menu"))
    
    await bot.send_message(user_id,
                         f"❓ <b>Вы уверены, что хотите удалить мероприятие?</b>\n\n"
                         f"🎫 {event['title']}\n"
                         f"📅 {event['date']}\n\n"
                         f"<b>Внимание!</b> Удалить можно только мероприятие без участников.",
                         reply_markup=keyboard,
                         parse_mode=types.ParseMode.HTML)

@dp.callback_query_handler(lambda c: c.data.startswith("confirm_delete_"))
async def process_confirm_delete(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    event_id = int(callback_query.data.split("_")[2])
    
    success, message = db.delete_event(event_id)
    
    keyboard = get_back_to_menu_keyboard()
    
    if success:
        await bot.send_message(user_id, "✅ " + message, reply_markup=keyboard)
        await process_events_list(callback_query)
    else:
        await bot.send_message(user_id, "❌ " + message, reply_markup=keyboard)

@dp.message_handler()
async def handle_unknown(message: types.Message):
    await message.answer(
        "🤔 Извините, я не понимаю эту команду.\n"
        "Используйте /help для получения списка доступных команд.",
        reply_markup=get_back_to_menu_keyboard()
    )

async def main():
    logging.info("Бот запущен и готов к работе!")
    await dp.start_polling()

if __name__ == '__main__':
    asyncio.run(main())
