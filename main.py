import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# === НАСТРОЙКИ ===
BOT_TOKEN = "8485358814:AAEWZtjxMwrTbkbe5iFvO4cigRyjnc9AuUc"
ADMIN_ID = 693353725  # ID админа (число, не @username)
PAYMENT_DETAILS = "Переведи 500₽ на СБП +79998887766 (Иван Иванов) и пришли сюда чек."

# === ДАННЫЕ О БИЛЕТАХ ===
available_tickets = {
    "TICKET-001": False,
    "TICKET-002": False,
    "TICKET-003": False,
    "TICKET-004": False,
}

# === ИНИЦИАЛИЗАЦИЯ ===
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()


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
    # Пересылаем админу чек
    caption = (
        f"💰 <b>Новый чек от @{message.from_user.username or message.from_user.id}</b>\n"
        f"ID пользователя: {message.from_user.id}\n\n"
        "✅ Админ, чтобы выдать билет, ответь на это сообщение командой:\n"
        "<code>/give TICKET-XXX</code>"
    )
    await message.forward(ADMIN_ID)
    await bot.send_message(ADMIN_ID, caption, parse_mode=ParseMode.HTML)
    await message.answer("📤 Чек отправлен админу на проверку. Ожидай подтверждения!")


# === ВЫДАЧА БИЛЕТА (только админ) ===
@dp.message(Command("give"))
async def give_ticket(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("🚫 Только админ может выдавать билеты.")

    args = message.text.strip().split()
    if len(args) != 2:
        return await message.answer("Используй формат: /give TICKET-001")

    ticket_code = args[1]
    if ticket_code not in available_tickets:
        return await message.answer("❌ Такого билета нет.")
    if available_tickets[ticket_code]:
        return await message.answer("⚠️ Этот билет уже выдан.")

    # Определяем кому отправлять (ответ на сообщение с пересланным чеком)
    if not message.reply_to_message or not message.reply_to_message.forward_origin:
        return await message.answer("⚠️ Команду нужно отправлять в ответ на пересланное сообщение от пользователя.")

    user_id = message.reply_to_message.forward_origin.sender_user.id
    available_tickets[ticket_code] = True

    await bot.send_message(user_id, f"🎟 Поздравляем! Твой билет:\n<code>{ticket_code}</code>")
    await message.answer(f"✅ Билет {ticket_code} выдан пользователю {user_id}")


# === ЗАПУСК ===
async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())