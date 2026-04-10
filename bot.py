import os
import random
import time

from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv


load_dotenv()

PROXY_URL = "http://proxy.server:3128"

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set. Put it into .env as BOT_TOKEN=...")

bot = Bot(token=BOT_TOKEN, proxy=PROXY_URL)
dp = Dispatcher(bot)

GROUP_ID = int(os.getenv("GROUP_ID", "-1000000000000"))
poll_results = {}

scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

NIGHT_POLL_QUESTION = "Кто сегодня дрочил сука"
NIGHT_POLL_OPTIONS = [
    "я сегодня был хорошим мальчиком и не дрочил :)",
    "я снова опозорился и подрочил, но с каким кайфом(",
]

DR0CH_RESPONSES = [
    "Ого, {user}!!! Да ты в ударе! 💪😄",
    "{user}, красавчик! Так держать! 🔥😎",
    "Вот это дисциплина, {user}! Респект! 🫡✨",
    "{user}, мощно! Продолжай в том же духе! 🚀😄",
    "Ничего себе, {user}!!! Уважение! 👏🔥",
    "{user}, ты сегодня на максималках! ⚡😄",
    "{user}, железная воля! 🧠💎",
    "Красава, {user}! Уровень: легенда 😄🏆",
    "{user}, вот это самообладание! 🔒🔥",
    "Респект, {user}! Ты реально держишься 🫡💪",
    "{user}, сегодня ты — машина! 🤖⚡",
    "Сильное заявление, {user}! 😎🔥",
    "{user}, так и надо — фокус на важном 🎯✨",
    "Опа, {user}! Непоколебим 😄🧱",
    "{user}, ты в режиме монаха 🧘‍♂️✨",
    "Вот это выдержка, {user}! ⏳💪",
    "{user}, браво! Порядок в голове — порядок в делах 🧠✅",
    "Ничего себе, {user}! Характер! 🐺🔥",
    "{user}, кайф! Продолжай держать планку 📈😄",
    "Так-так, {user}… Вижу силу духа 😎💥",
    "{user}, это победа над соблазном 🏅😄",
    "{user}, ты сегодня на стальном режиме 🦾🧊",
    "Легендарно, {user}! 👑🔥",
    "{user}, ты заряжен! 🔋⚡",
    "Ого, {user}! Взял и удержался 😄🛡️",
    "{user}, дисциплина как часы ⌚✅",
    "Уважение, {user}! Ты красавчик 😄👏",
    "{user}, вот это настрой! 🎵🔥",
    "{user}, мощнейший контроль 💪🧠",
    "Понял-принял, {user}! 😄🤝",
    "{user}, держишь удар как чемпион 🥊🏆",
    "Красиво, {user}! Чистая победа ✅✨",
    "{user}, ты на правильном пути 🧭😄",
    "{user}, сегодня без срывов — так держать 🚫🔥",
    "Супер, {user}! Продолжаем в том же темпе 🚀💪",
    "{user}, уровень самоконтроля: космос 🌌😎",
    "{user}, это уже стиль жизни 😄💼",
    "Ого-го, {user}! Ты реально в ударе 🔥⚡",
    "{user}, крепкий орешек! 🥜😄",
    "{user}, харизма + дисциплина = успех 😎✅",
    "{user}, так держать! Респект и уважуха 🤝🔥",
    "{user}, ты сегодня непобедим 🏆🛡️",
]


@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message) -> None:
    await message.answer(
        "Бот запущен и готов к работе в группах.\n\n"
        "Если в группе нет реакции на «не дрочу»: откройте @BotFather → ваш бот → "
        "Bot Settings → Group Privacy → Disable. Иначе Telegram не присылает боту "
        "обычные сообщения (только команды, ответы боту и упоминания @бота)."
    )


@dp.message_handler(
    content_types=types.ContentType.TEXT,
)
async def group_text_handler(message: types.Message) -> None:
    text = (message.text or "").lower()

    if "бот, статус" in text:
        if message.chat.type == types.ChatType.PRIVATE:
            await message.reply("Я работаю только в группах")
            return

        if message.chat.type not in (types.ChatType.GROUP, types.ChatType.SUPERGROUP):
            return

        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        if member.status in (
            types.ChatMemberStatus.ADMINISTRATOR,
            types.ChatMemberStatus.CREATOR,
        ):
            await message.reply("Дроч система работает в штатном режиме")
        else:
            await message.reply("У вас нет прав для проверки статуса")
        return

    if "не дрочу" not in text:
        return

    if message.chat.type == types.ChatType.PRIVATE:
        await message.reply("Я работаю только в группах")
        return

    if message.chat.type not in (types.ChatType.GROUP, types.ChatType.SUPERGROUP):
        return

    user_display = message.from_user.username or message.from_user.full_name
    print(f'phrase_trigger group_id={message.chat.id} user="{user_display}"')

    at_username = f"@{message.from_user.username}" if message.from_user.username else user_display
    phrase = random.choice(DR0CH_RESPONSES).format(user=at_username)
    await message.reply(phrase)


async def send_night_poll() -> None:
    poll_results.clear()
    await bot.send_poll(
        GROUP_ID,
        NIGHT_POLL_QUESTION,
        NIGHT_POLL_OPTIONS,
        is_anonymous=False,
    )


async def summarize_poll() -> None:
    if not poll_results:
        return

    good = [row["mention"] for row in poll_results.values() if row["option_index"] == 0]
    bad = [row["mention"] for row in poll_results.values() if row["option_index"] == 1]

    if not good and not bad:
        return

    parts = ["<b>Итог ночного опроса</b>\n"]

    if good:
        parts.append(
            "😇 <b>Хорошими мальчиками</b> сегодня были: "
            + ", ".join(good)
            + "\n\n"
            "Уважение: вы держите слово и не подводите. Так держать — вы настоящие 💪✨\n\n"
        )

    if bad:
        parts.append(
            "🤡 <b>Позорники</b> в списке: "
            + ", ".join(bad)
            + "\n\n"
            "Стыдно даже читать. Завтра без отговорок — включите режим сдержанности 🫵😤"
        )

    text = "".join(parts).rstrip()
    await bot.send_message(GROUP_ID, text, parse_mode="HTML")


@dp.poll_answer_handler()
async def poll_answer_handler(poll_answer: types.PollAnswer) -> None:
    if not poll_answer.option_ids:
        return
    uid = poll_answer.user.id
    mention = poll_answer.user.get_mention(as_html=True)
    option_index = poll_answer.option_ids[0]
    poll_results[uid] = {
        "mention": mention,
        "option_index": option_index,
    }


scheduler.add_job(
    send_night_poll,
    CronTrigger(hour=23, minute=0),
    id="send_night_poll",
    replace_existing=True,
)
scheduler.add_job(
    summarize_poll,
    CronTrigger(hour=0, minute=0),
    id="summarize_poll",
    replace_existing=True,
)


if __name__ == "__main__":
    scheduler.start()
    while True:
        try:
            executor.start_polling(dp, skip_updates=True)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"bot_crashed: {e!r}")
            time.sleep(3)
