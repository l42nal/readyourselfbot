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
BOT_TOKEN = "8485358814:AAEWZtjxMwrTbkbe5iFvO4cigRyjnc9AuUc"
ADMIN_ID = 1363368733
CONTROLLER_ID = 1257512735  # замените на ID контролёра
PAYMENT_DETAILS = "<a href='https://vtb.paymo.ru/collect-money/qr/?transaction=301ac782-e8c6-4274-8567-3376f36e983a'>Оплатить</a>"

# === ХРАНЕНИЕ БИЛЕТОВ ===
TICKETS_FILE = "tickets.json"
QRCODE_DIR = "qrcodes"

os.makedirs(QRCODE_DIR, exist_ok=True)

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

# === ИНИЦИАЛИЗАЦИЯ ===
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
tickets = load_tickets()

# === КОМАНДЫ ===
@dp.message(Command("start"))
async def start(message: types.Message):
    text = (
        "Привет 🫂 Я очень рада, что ты решил(-а) присоединиться к нашей семье, где царит любовь и искренность!\n\n"
        "Чтобы завершить регистрацию на мероприятие, переходи по ссылке для оплаты билета:\n"
        f"{PAYMENT_DETAILS}\n\n"
        "Или оплати по прикрепленному QR-коду\n\n"
        "Жду тебя! ❤️\n\n"
        "❗️ После оплаты отправь сюда <b>скриншот</b> или фото подтверждения перевода.\n\n"
        "⚖️ Оплачивая билет, вы принимаете условия "
        "<a href='https://telegra.ph/Publichnaya-oferta-10-27-8'>публичной оферты</a>."
    )

    # путь к уже готовому QR-коду
    qr_path = "payment_qr.jpg"  # или qr.jpg — смотри по названию файла

    await message.answer_photo(
        photo=types.FSInputFile(qr_path),
        caption=text,
        parse_mode="HTML"
    )

# === ПОЛУЧЕНИЕ ЧЕКА ===
@dp.message(F.photo, lambda msg: msg.from_user.id != CONTROLLER_ID)
async def handle_payment_proof(message: types.Message):
    # Если это контролёр, пропускаем этот хэндлер
    if message.from_user.id == CONTROLLER_ID:
        return
    caption = (
        f"💰 <b>Новый чек от @{message.from_user.username or message.from_user.id}</b>\n"
        f"ID пользователя: <code>{message.from_user.id}</code>\n\n"
        "✅ Чтобы подтвердить оплату и выдать билет, ответь на это сообщение командой /confirm"
    )
    await message.forward(ADMIN_ID)
    await bot.send_message(ADMIN_ID, caption)
    await message.answer("📤 Чек отправлен админу на проверку. Ожидай подтверждения!")

# === ПОДТВЕРЖДЕНИЕ ОПЛАТЫ АДМИНОМ ===
@dp.message(Command("confirm"))
async def confirm_payment(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("🚫 Только админ может подтверждать оплаты.")

    if not message.reply_to_message:
        await message.reply("❌ Ответь командой /confirm на сообщение с id пользователя.")
        return

    text = message.reply_to_message.text
    match = re.search(r"ID пользователя:\s*(\d+)", text)
    if not match:
        await message.reply("❌ Не удалось найти ID пользователя в сообщении.")
        return

    user_id = int(match.group(1))
    ticket = get_next_free_ticket(tickets)
    if not ticket:
        return await message.answer("❌ Билеты закончились!")

    ticket["free"] = False
    save_tickets(tickets)
    qr_path = generate_qr_image(ticket["code"])

    await bot.send_photo(
        user_id,
        photo=types.FSInputFile(qr_path),
        caption=f"🎟 Твой билет: <code>{ticket['code']}</code>\nПокажи этот QR-код на входе."
    )
    await message.answer(f"✅ Билет {ticket['code']} выдан пользователю {user_id}")

# === РЕЖИМ ПРОВЕРКИ БИЛЕТОВ ДЛЯ КОНТРОЛЁРА ===
controller_state = {}  # {user_id: True/False для режима проверки}

@dp.message(Command("check"))
async def start_check_mode(message: types.Message):
    if message.from_user.id != CONTROLLER_ID:
        return await message.answer("🚫 Только контролёр может проверять билеты.")
    controller_state[message.from_user.id] = True
    await message.answer("📸 Отправь фото QR-кода или введи код билета вручную.")

@dp.message(F.photo | F.text, lambda msg: msg.from_user.id == CONTROLLER_ID)
async def check_ticket(message: types.Message):
    if message.from_user.id != CONTROLLER_ID:
        return

    if not controller_state.get(message.from_user.id):
        return  # Контролёр не в режиме проверки

    # Определяем код билета
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

    # Проверяем билет
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

    # После проверки выходим из режима
    controller_state[message.from_user.id] = False

# === ЗАПУСК ===
async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())