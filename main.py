import asyncio
import logging
import re
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message
import google.generativeai as genai

# --- НАСТРОЙКИ ---
TELEGRAM_TOKEN = "8543901936:AAGZnr0u1cN43abbBOsW3oa1PDZB9U0AFtE"
GEMINI_API_KEY = "AQ.Ab8RN6KRdgHq25VckveHZjdf-59eUpYCtkc4fksO5g6FrfKlnA"

# Инициализация Gemini старой стабильной библиотекой
genai.configure(api_key=GEMINI_API_KEY)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

CATEGORIES = {
    "football": "⚽ Футбол",
    "basketball": "🏀 Баскетбол",
    "hockey": "🏒 Хоккей",
    "cs2": "🎯 CS 2 (Киберспорт)",
    "dota2": "🛡 Dota 2 (Киберспорт)"
}

DATES = {
    "today": "Сегодня",
    "tomorrow": "Завтра",
    "after_tomorrow": "Послезавтра"
}

# Машина состояний (FSM)
class BetState(StatesGroup):
    choosing_type = State()
    choosing_category = State()
    choosing_express_count = State()
    building_multisport_express = State()
    choosing_date = State()

# --- КЛАВИАТУРЫ ---

def get_main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔮 Создать прогноз / экспресс с ИИ", callback_data="start_prediction")]
    ])

def get_bet_type_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Ординар (Лучший аналитический прогноз)", callback_data="type_single")],
        [InlineKeyboardButton(text="🟡 Мультиспорт-Экспресс (2-10 матчей)", callback_data="type_express")],
    ])

def get_categories_kb(is_express_mix=False):
    keyboard = []
    for cat_key, cat_name in CATEGORIES.items():
        keyboard.append([InlineKeyboardButton(text=cat_name, callback_data=f"cat_{cat_key}")])
    if is_express_mix:
        keyboard.append([InlineKeyboardButton(text="✅ Завершить сбор экспресса", callback_data="finish_express")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_express_count_kb():
    row1 = [InlineKeyboardButton(text=str(i), callback_data=f"exp_count_{i}") for i in range(2, 6)]
    row2 = [InlineKeyboardButton(text=str(i), callback_data=f"exp_count_{i}") for i in range(6, 11)]
    return InlineKeyboardMarkup(inline_keyboard=[row1, row2])

def get_dates_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Сегодня", callback_data="date_today")],
        [InlineKeyboardButton(text="📅 Завтра", callback_data="date_tomorrow")],
        [InlineKeyboardButton(text="📅 Послезавтра", callback_data="date_after_tomorrow")],
    ])


# --- ФУНКЦИЯ ГЕНЕРАЦИИ МАТЧА ЧЕРЕЗ GEMINI ---

async def fetch_gemini_prediction(sport_name: str, date_text: str):
    prompt = (
        f"Ты — профессиональный спортивный аналитик и каппер. Составь один качественный прогноз на реальный или актуальный матч "
        f"в категории '{sport_name}' на дату '{date_text}'.\n"
        f"Выдай ответ строго в таком формате без лишнего текста:\n"
        f"Матч: [Команда 1 vs Команда 2]\n"
        f"Прогноз: [Текст прогноза и краткое обоснование в 1-2 предложениях]\n"
        f"Кф: [Число с точкой, например 1.85]"
    )
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        # Запускаем в отдельном потоке, чтобы бот не зависал во время запроса
        response = await asyncio.to_thread(model.generate_content, prompt)
        text = response.text
        logger.info(f"Ответ от Gemini для {sport_name}: {text}")
        
        match_search = re.search(r"Матч:\s*(.*)", text)
        pred_search = re.search(r"Прогноз:\s*(.*)", text)
        odd_search = re.search(r"Кф:\s*([\d\.]+)", text)
        
        match_str = match_search.group(1).strip() if match_search else "Команда А vs Команда Б"
        pred_str = pred_search.group(1).strip() if pred_search else "Победа фаворита с учетом формы"
        odd_val = float(odd_search.group(1)) if odd_search else 1.85
            
        return match_str, pred_str, round(odd_val, 2)
        
    except Exception as e:
        logger.error(f"Ошибка запроса к Gemini API: {e}")
        return "Команда А vs Команда Б", "Аналитическое превосходство по статистике личных встреч", 1.80


# --- ХЕНДЛЕРЫ БОТА ---

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    logger.info(f"Получена команда /start от пользователя {message.from_user.id}")
    await state.clear()
    await message.answer(
        "👋 Привет! Я твой продвинутый бот-аналитик на базе **Google Gemini API**.\n\n"
        "Я могу:\n"
        "• Составлять точные **ординары** с аргументацией.\n"
        "• Генерировать **мультиспортивные экспрессы** (микс видов спорта) с расчетом общего коэффициента.\n\n"
        "Нажми кнопку ниже, чтобы начать:",
        reply_markup=get_main_menu_kb()
    )

@dp.callback_query(F.data == "start_prediction")
async def process_start_prediction(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🎯 Выберите формат ставки:", reply_markup=get_bet_type_kb())
    await state.set_state(BetState.choosing_type)
    await callback.answer()

@dp.callback_query(BetState.choosing_type, F.data.startswith("type_"))
async def process_bet_type(callback: CallbackQuery, state: FSMContext):
    bet_type = callback.data.split("_")[1]
    await state.update_data(bet_type=bet_type)

    if bet_type == "single":
        await callback.message.edit_text("📂 Выберите категорию спорта для ординара:", reply_markup=get_categories_kb(is_express_mix=False))
        await state.set_state(BetState.choosing_category)
    else:
        await callback.message.edit_text("🔢 Выберите количество матчей для экспресса (от 2 до 10):", reply_markup=get_express_count_kb())
        await state.set_state(BetState.choosing_express_count)
    await callback.answer()

@dp.callback_query(BetState.choosing_express_count, F.data.startswith("exp_count_"))
async def process_express_count(callback: CallbackQuery, state: FSMContext):
    count = int(callback.data.split("_")[2])
    await state.update_data(express_count=count, express_items=[])
    await callback.message.edit_text(
        f"🎯 Экспресс на {count} матча(ей).\nВыберите категорию для **1-го** матча (можно миксовать виды спорта):",
        reply_markup=get_categories_kb(is_express_mix=True)
    )
    await state.set_state(BetState.building_multisport_express)
    await callback.answer()

@dp.callback_query(BetState.building_multisport_express, F.data.startswith("cat_"))
async def process_express_category_choice(callback: CallbackQuery, state: FSMContext):
    cat_key = callback.data.split("_")[1]
    data = await state.get_data()
    express_items = data.get("express_items", [])
    express_count = data.get("express_count")

    await callback.message.edit_text("⏳ *Gemini анализирует матч и подбирает коэффициент...*")

    match_str, pred_str, odd = await fetch_gemini_prediction(CATEGORIES[cat_key], "Сегодня")
    express_items.append({"category": CATEGORIES[cat_key], "match": match_str, "prediction": pred_str, "odd": odd})
    await state.update_data(express_items=express_items)

    if len(express_items) < express_count:
        next_num = len(express_items) + 1
        await callback.message.edit_text(
            f"✅ Матч {len(express_items)}/{express_count} добавлен!\n"
            f"▫️ {CATEGORIES[cat_key]}: {match_str} (Кф: {odd})\n\n"
            f"Выберите категорию для **{next_num}-го** матча:",
            reply_markup=get_categories_kb(is_express_mix=True)
        )
    else:
        await callback.message.edit_text(
            f"✅ Все {express_count} матча(ей) собраны в купон!\n📅 Выберите целевую дату экспресса:",
            reply_markup=get_dates_kb()
        )
        await state.set_state(BetState.choosing_date)
    await callback.answer()

@dp.callback_query(BetState.building_multisport_express, F.data == "finish_express")
async def finish_express_early(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    express_items = data.get("express_items", [])
    if not express_items:
        await callback.answer("Вы еще не добавили ни одного матча!", show_alert=True)
        return
    await callback.message.edit_text(f"✅ Собрано матчей: {len(express_items)}.\n📅 Выберите дату экспресса:", reply_markup=get_dates_kb())
    await state.set_state(BetState.choosing_date)
    await callback.answer()

@dp.callback_query(BetState.choosing_category, F.data.startswith("cat_"))
async def process_single_category(callback: CallbackQuery, state: FSMContext):
    cat_key = callback.data.split("_")[1]
    await state.update_data(single_category=cat_key)
    await callback.message.edit_text("📅 Выберите дату для ординара:", reply_markup=get_dates_kb())
    await state.set_state(BetState.choosing_date)
    await callback.answer()

@dp.callback_query(BetState.choosing_date, F.data.startswith("date_"))
async def process_date_and_show_prediction(callback: CallbackQuery, state: FSMContext):
    date_code = callback.data.split("_")[1]
    date_text = DATES.get(date_code, "Сегодня")
    data = await state.get_data()
    bet_type = data.get("bet_type")

    await callback.message.edit_text("🤖 *ИИ Gemini рассчитывает вероятности и формирует прогноз...*")

    if bet_type == "single":
        cat_key = data.get("single_category")
        match_str, pred_str, odd = await fetch_gemini_prediction(CATEGORIES[cat_key], date_text)
        response_text = (
            f"🏆 **ЛУЧШИЙ ОРДИНАР** ({date_text})\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📌 **Дисциплина:** {CATEGORIES[cat_key]}\n"
            f"🏟 **Матч:** {match_str}\n"
            f"📊 **Анализ:** {pred_str}\n"
            f"📈 **Коэффициент:** `{odd}`\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 *Прогноз сгенерирован Google Gemini AI*"
        )
    else:
        items = data.get("express_items", [])
        total_odd = 1.0
        express_lines = ""
        for idx, item in enumerate(items, 1):
            total_odd *= item["odd"]
            express_lines += f"{idx}. **{item['category']}**\n   🏟 {item['match']}\n   💡 {item['prediction']} (Кф: `{item['odd']}`)\n\n"
        total_odd = round(total_odd, 2)
        response_text = (
            f"🔥 **МУЛЬТИСПОРТИВНЫЙ ЭКСПРЕСС** ({date_text})\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"{express_lines}"
            f"🎯 **Всего событий:** {len(items)}\n"
            f"💰 **ОБЩИЙ КОЭФФИЦИЕНТ:** `{total_odd}`\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 *Купон сформирован и просчитан нейросетью Gemini*"
        )

    await callback.message.edit_text(response_text, reply_markup=get_main_menu_kb())
    await state.clear()
    await callback.answer()

async def main():
    logger.info("Запуск бота...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
