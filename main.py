import asyncio
import json
import random
import string
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

def load_tickets():
    try:
        with open(TICKETS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        # при первом запуске создаем 10 случайных кодов
        tickets = [{"code": generate_ticket_code(), "used": False} for _ in range(10)]
        save_tickets(tickets)
        return tickets

def save_tickets(tickets):
    with open(TICKETS_FILE, "w") as f:
        json.dump(tickets, f, indent=2)

def generate_ticket_code():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

def get_next_free_ticket(tickets):
    for t in tickets:
        if not t["used"]:
            return t
    return None

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

    if not message.reply_to_message or not message.reply_to_message.forward_origin:
        return await message.answer("⚠️ Ответь этой командой на пересланное сообщение от пользователя.")

    user_id = message.reply_to_message.forward_origin.sender_user.id
    ticket = get_next_free_ticket(tickets)
    if not ticket:
        return await message.answer("❌ Билеты закончились!")

    ticket["used"] = True
    save_tickets(tickets)

    await bot.send_message(
        user_id,
        f"🎟 Поздравляем! Твой билет: <code>{ticket['code']}</code>"
    )
    await message.answer(f"✅ Билет {ticket['code']} выдан пользователю {user_id}")

# === ЗАПУСК ===
async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())