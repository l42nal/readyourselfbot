import asyncio
import json
import random
import string
import os
import qrcode
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from pyzbar.pyzbar import decode
from PIL import Image

# === НАСТРОЙКИ ===
BOT_TOKEN = 
ADMIN_ID = 
CONTROLLER_ID = 
PAYMENT_DETAILS = 

YOO_MONEY_TOKEN = 

# === ФАЙЛЫ ХРАНЕНИЯ ===
TICKETS_FILE = "tickets.json"
PROMO_FILE = "promo.json"
QRCODE_DIR = "qrcodes"

os.makedirs(QRCODE_DIR, exist_ok=True)

# === УТИЛИТЫ ДЛЯ БИЛЕТОВ ===
def generate_ticket_code():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

def load_tickets():
    try:
        with open(TICKETS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        tickets = [{"code": generate_ticket_code(), "free": True, "used": False} for _ in range(25)]
        save_tickets(tickets)
        return tickets

def save_tickets(tickets):
    with open(TICKETS_FILE, "w") as f:
        json.dump(tickets, f, indent=2)

def get_next_free_ticket(tickets):
    for t in tickets:
        if t["free"]:
            return t
    return None

def generate_qr_image(ticket_code):
    img = qrcode.make(ticket_code)
    path = os.path.join(QRCODE_DIR, f"{ticket_code}.png")
    img.save(path)
    return path

# === УТИЛИТЫ ДЛЯ ПРОМОКОДОВ ===
def load_promos():
    try:
        with open(PROMO_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        promos = []
        save_promos(promos)
        return promos

def save_promos(promos):
    with open(PROMO_FILE, "w") as f:
        json.dump(promos, f, indent=2)

def generate_promo_code():
    # 6 символов, буквы и цифры
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

def create_promo(promos):
    # создаёт уникальный промокод и добавляет в список
    for _ in range(10):
        code = generate_promo_code()
        if not any(p["code"] == code for p in promos):
            promos.append({"code": code, "used": False})
            save_promos(promos)
            return code
    # в редком случае коллизий — возвращаем последний
    code = generate_promo_code()
    promos.append({"code": code, "used": False})
    save_promos(promos)
    return code

def find_promo(promos, code):
    return next((p for p in promos if p["code"].upper() == code.upper()), None)

# === ИНИЦИАЛИЗАЦИЯ ===
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
tickets = load_tickets()
promos = load_promos()

# Состояние ожидания ввода промокода
waiting_promo = {}

# === КОМАНДЫ ===
@dp.message(Command("start"))
async def start(message: types.Message):
    text = (
        "Привет! 👀\n"
        "Это Читай себя бот. Через меня можно узнать о нашей команде и купить билеты на наше мероприятие.\n\n"
        "Мои команды:\n"
        "/info - о нас\n"
        "/buy - купить билет\n"
        "/promo - применить промокод\n\n"
        "Возникли проблемы с оплатой? /buymanual\n"
    )

    qr_path = "payment_qr.jpg"  # оставил как раньше — ты заменишь картинку
    # Отправляем меню и QR для оплаты по реквизитам
    await message.answer(text)


@dp.message(Command("info"))
async def info(message: types.Message):
    await message.answer("Мы такие-то бла бла бла вот наша группа")


@dp.message(Command("buymanual"))
async def buy_manual(message: types.Message):
    text = (
        f"💳 Оплата по реквизитам:\n{PAYMENT_DETAILS}\n\n"
        "📸 Отправь скриншот в ответ на это сообщение.\n\n"
        "Если что-то не получается — пиши @Кате"
    )
    qr_path = "payment_qr.jpg"
    await message.answer_photo(photo=types.FSInputFile(qr_path), caption=text, parse_mode="HTML")


# === 🧾 Telegram-оплата (через YooMoney) ===
@dp.message(Command("buy"))
async def buy_ticket(message: types.Message):
    # Проверяем наличие свободных билетов
    ticket = get_next_free_ticket(tickets)
    if not ticket:
        await message.answer("❌ К сожалению, билеты закончились.")
        return

    prices = [types.LabeledPrice(label="Билет на мероприятие", amount=90000)]  # 900.00 руб

    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Билет на мероприятие",
        description="Вход на мероприятие. Оплата через YooMoney.",
        provider_token=YOO_MONEY_TOKEN,
        currency="rub",
        prices=prices,
        start_parameter="event_ticket",
        payload=f"user_{message.from_user.id}",
    )


@dp.pre_checkout_query()
async def pre_checkout_query(pre_checkout_q: types.PreCheckoutQuery):
    # Telegram перед оплатой еще раз проверяет ok
    ticket = get_next_free_ticket(tickets)
    if not ticket:
        # Если билет успели выкупить между /buy и оплатой
        await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=False, error_message="Билеты закончились :(")
    else:
        await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)


@dp.message(F.successful_payment)
async def successful_payment(message: types.Message):
    # Здесь мы точно уверены, что оплата прошла и билет есть
    ticket = get_next_free_ticket(tickets)
    if not ticket:
        # На случай форс-мажора (двойной платеж)
        await message.answer("❌ Ошибка: билеты закончились, но оплата прошла. Пожалуйста, напиши админу для возврата.")
        await bot.send_message(
            ADMIN_ID,
            f"⚠️ Ошибка: оплата без билета от @{message.from_user.username or message.from_user.id} "
            f"(ID {message.from_user.id}). Нужно вернуть деньги."
        )
        return

    ticket["free"] = False
    save_tickets(tickets)
    qr_path = generate_qr_image(ticket["code"])

    # Создаём промокод и сохраняем
    promo_code = create_promo(promos)

    await message.answer("✅ Оплата прошла успешно! Спасибо ❤️")
    await message.answer_photo(
        photo=types.FSInputFile(qr_path),
        caption=(f"🎟 Твой билет: <code>{ticket['code']}</code>\n"
                 f"Покажи этот QR-код на входе.\n\n"
                 f"🎁 Твой промокод: <code>{promo_code}</code>\n"
                 f"Поделись им с другом — он может использовать его один раз, чтобы получить билет."),
    )

    await bot.send_message(
        ADMIN_ID,
        f"💳 Новый платёж от @{message.from_user.username or message.from_user.id}\n"
        f"ID: <code>{message.from_user.id}</code>\nБилет: {ticket['code']}\nПромокод выдан: {promo_code}"
    )


# === Чеки и выдача билетов вручную (остальное без изменений) ===
@dp.message(F.photo, lambda msg: msg.from_user.id != CONTROLLER_ID)
async def handle_payment_proof(message: types.Message):
    if message.from_user.id == CONTROLLER_ID:
        return
    caption = (
        f"💰 <b>Новый чек от @{message.from_user.username or message.from_user.id}</b>\n"
        f"ID пользователя: <code>{message.from_user.id}</code>\n\n"
        "✅ Чтобы подтвердить оплату и выдать билет, ответь на это сообщение командой /confirm"
    )
    await message.forward(ADMIN_ID)
    await bot.send_message(ADMIN_ID, caption)
    await message.answer("📤 Чек отправлен админу. Жди подтверждения!")


@dp.message(Command("confirm"))
async def confirm_payment(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("🚫 Только админ может подтверждать оплаты.")

    if not message.reply_to_message:
        await message.reply("❌ Ответь командой /confirm на сообщение с id пользователя.")
        return

    text = message.reply_to_message.text or message.reply_to_message.caption or ""
    match = re.search(r"ID пользователя:\s*(\d+)", text)
    if not match:
        await message.reply("❌ Не удалось найти ID пользователя.")
        return

    user_id = int(match.group(1))
    ticket = get_next_free_ticket(tickets)
    if not ticket:
        return await message.answer("❌ Билеты закончились!")

    ticket["free"] = False
    save_tickets(tickets)
    qr_path = generate_qr_image(ticket["code"])

    # Создаём промокод и сохраняем
    promo_code = create_promo(promos)

    await bot.send_photo(
        user_id,
        photo=types.FSInputFile(qr_path),
        caption=(f"🎟 Твой билет: <code>{ticket['code']}</code>\n"
                 f"Покажи этот QR-код на входе.\n\n"
                 f"🎁 Твой промокод: <code>{promo_code}</code>\n"
                 f"Поделись им с другом — он может использовать его один раз, чтобы получить билет."),
    )
    await message.answer(f"✅ Билет {ticket['code']} выдан пользователю {user_id}\nПромокод: {promo_code}")

    # Логируем админу
    await bot.send_message(
        ADMIN_ID,
        f"✅ Админ выдал билет {ticket['code']} пользователю {user_id}. Промокод: {promo_code}"
    )


# === Проверка билетов ===
controller_state = {}

@dp.message(Command("check"))
async def start_check_mode(message: types.Message):
    if message.from_user.id != CONTROLLER_ID:
        return await message.answer("🚫 Только контролёр может проверять билеты.")
    controller_state[message.from_user.id] = True
    await message.answer("📸 Отправь фото QR-кода или введи код вручную.")

# === ПРОМОКОДЫ: команда и приём кода от пользователя ===
@dp.message(Command("promo"))
async def promo_command(message: types.Message):
    waiting_promo[message.from_user.id] = True
    await message.answer("Введи промокод")


@dp.message()
async def handle_general_messages(message: types.Message):
    # Обработка ожидания промокода
    if waiting_promo.get(message.from_user.id):
        code = message.text.strip()
        promo = find_promo(promos, code)
        if not promo:
            await message.answer("Такого промокода нет")
            waiting_promo[message.from_user.id] = False
            return
        if promo.get("used"):
            await message.answer("Этот промокод уже был использован!")
            waiting_promo[message.from_user.id] = False
            return
        # Есть валидный промокод — выдаём билет
        ticket = get_next_free_ticket(tickets)
        if not ticket:
            await message.answer("❌ К сожалению, билеты закончились.")
            waiting_promo[message.from_user.id] = False
            return

        ticket["free"] = False
        save_tickets(tickets)

        # Помечаем промокод использованным
        promo["used"] = True
        save_promos(promos)

        qr_path = generate_qr_image(ticket["code"])
        await bot.send_photo(
            message.from_user.id,
            photo=types.FSInputFile(qr_path),
            caption=(f"🎟 Твой билет: <code>{ticket['code']}</code>\n"
                     f"Покажи этот QR-код на входе.")
        )

        await message.answer(f"Супер вот твой билет.\nПромокод {promo['code']} использован.")

        # Логируем админу
        await bot.send_message(
            ADMIN_ID,
            f"🎟 Промокод {promo['code']} использован пользователем @{message.from_user.username or message.from_user.id} (ID {message.from_user.id}). Выдан билет {ticket['code']}"
        )

        waiting_promo[message.from_user.id] = False
        return

    # --- ниже можно оставить другой обычный обработчик сообщений или ничего ---


@dp.message(F.photo | F.text, lambda msg: msg.from_user.id == CONTROLLER_ID)
async def check_ticket(message: types.Message):
    if message.from_user.id != CONTROLLER_ID:
        return

    if not controller_state.get(message.from_user.id):
        return

    code = None
    if message.photo:
        file_path = f"temp_{message.from_user.id}.jpg"
        photo = message.photo[-1]
        await bot.download(photo.file_id, destination=file_path)
        img = Image.open(file_path)
        decoded = decode(img)
        os.remove(file_path)
        if decoded:
            code = decoded[0].data.decode()
        else:
            await message.answer("❌ QR-код не распознан.")
            return
    else:
        code = message.text.strip()

    ticket = next((t for t in tickets if t["code"] == code), None)
    if not ticket:
        await message.answer("❌ Билет не найден.")
        return

    if ticket["used"]:
        await message.answer("⚠️ Этот билет уже был использован!")
    else:
        ticket["used"] = True
        save_tickets(tickets)
        await message.answer(f"✅ Билет {code} действителен. Пропускаем!")

    controller_state[message.from_user.id] = False

# === ЗАПУСК ===
async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
