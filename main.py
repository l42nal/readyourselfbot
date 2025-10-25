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

# === НАСТРОЙКИ ===
BOT_TOKEN = "8485358814:AAEWZtjxMwrTbkbe5iFvO4cigRyjnc9AuUc"
ADMIN_ID = 693353725  # замените на свой числовой ID
PAYMENT_DETAILS = "Переведи 500₽ на СБП +79998887766 (Иван Иванов) и пришли сюда чек."

# === ХРАНЕНИЕ БИЛЕТОВ ===
TICKETS_FILE = "tickets.json"
QRCODE_DIR = "qrcodes"

os.makedirs(QRCODE_DIR, exist_ok=True)

def generate_ticket_code():
    """Создает случайный 6-значный код."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

def load_tickets():
    try:
        with open(TICKETS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        tickets = [{"code": generate_ticket_code(), "used": False} for _ in range(10)]
        save_tickets(tickets)
        return tickets

def save_tickets(tickets):
    with open(TICKETS_FILE, "w") as f:
        json.dump(tickets, f, indent=2)

def get_next_free_ticket(tickets):
    for t in tickets:
        if not t["used"]:
            return t
    return None

def generate_qr_image(ticket_code):
    """Создает изображение QR-кода и сохраняет в файл."""
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
        "🎟 Привет! Чтобы купить билет:\n\n"
        f"{PAYMENT_DETAILS}\n\n"
        "После оплаты отправь сюда <b>скриншот</b> или фото подтверждения перевода."
    )
    await message.answer(text)

# === ПОЛУЧЕНИЕ ЧЕКА ===
@dp.message(F.photo)
async def handle_payment_proof(message: types.Message):
    caption = (
        f"💰 <b>Новый чек от @{message.from_user.username or message.from_user.id}</b>\n"
        f"ID пользователя: <code>{message.from_user.id}</code>\n\n"
        "✅ Чтобы подтвердить оплату и выдать билет, ответь на это сообщение командой /confirm"
    )
    await message.forward(ADMIN_ID)
    await bot.send_message(ADMIN_ID, caption)
    await message.answer("📤 Чек отправлен админу на проверку. Ожидай подтверждения!")

# === ПОДТВЕРЖДЕНИЕ ОПЛАТЫ ===
@dp.message(Command("confirm"))
async def confirm_payment(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("🚫 Только админ может подтверждать оплаты.")

    if not message.reply_to_message:
        await message.reply("❌ Ответь командой /confirm на сообщение с id пользователя.")
        return

    # Ищем строку вида "ID пользователя: 693353725"
    text = message.reply_to_message.text
    match = re.search(r"ID пользователя:\s*(\d+)", text)
    if not match:
        await message.reply("❌ Не удалось найти ID пользователя в сообщении.")
        return

    user_id = int(match.group(1))
    ticket = get_next_free_ticket(tickets)
    if not ticket:
        return await message.answer("❌ Билеты закончились!")

    # помечаем как использованный
    ticket["used"] = True
    save_tickets(tickets)

    # создаем QR-код
    qr_path = generate_qr_image(ticket["code"])

    # отправляем пользователю QR с подписью
    await bot.send_photo(
        user_id,
        photo=types.FSInputFile(qr_path),
        caption=f"🎟 Твой билет: <code>{ticket['code']}</code>\nПокажи этот QR-код на входе."
    )

    await message.answer(f"✅ Билет {ticket['code']} выдан пользователю {user_id}")

# === ЗАПУСК ===
async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())