"""
Telegram-бот: реакции на фразы в группе, ежедневный опрос и сводка по голосам.
"""
import os
import random
import time
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.utils import exceptions
from aiogram.utils import executor
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv


load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# HTTP(S)-прокси для запросов к api.telegram.org (при необходимости смените или уберите proxy= у Bot)
PROXY_URL = "http://proxy.server:3128"

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set. Put it into .env as BOT_TOKEN=...")

bot = Bot(token=BOT_TOKEN, proxy=PROXY_URL)
dp = Dispatcher(bot)

# Целевая супергруппа: опросы и итоги уходят сюда (задаётся в .env как GROUP_ID)
GROUP_ID = int(os.getenv("GROUP_ID", "-1000000000000"))
# Голоса за текущий опрос: user_id -> {mention (HTML), option_index}
poll_results = {}

# Cron-задачи в часовом поясе Москвы; start() вызывается из on_startup (нужен уже запущенный asyncio-цикл)
scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

NIGHT_POLL_QUESTION = "Кто сегодня дрочил сука"
NIGHT_POLL_OPTIONS = [
    "я сегодня был хорошим мальчиком и не дрочил :)",
    "я снова опозорился и подрочил, но с каким кайфом(",
]

# Случайный ответ на сообщения с подстрокой «не дрочу» в группе; {user} подставляется в шаблон
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
    """Справка по настройке бота (в т.ч. Group Privacy в BotFather)."""
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
    """Текст в группах: «бот, статус» (только админы) и триггер «не дрочу»."""
    text = (message.text or "").lower()

    # Запрос статуса — только группа/супергруппа и только админ/создатель
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

    # Похвала по фразе «не дрочу» — только группа, не личка
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
    """По расписанию (23:00): сброс голосов и новый неанонимный опрос в GROUP_ID."""
    poll_results.clear()
    await bot.send_poll(
        GROUP_ID,
        NIGHT_POLL_QUESTION,
        NIGHT_POLL_OPTIONS,
        is_anonymous=False,  # чтобы приходили poll_answer и был виден выбор в опросе
    )


async def summarize_poll() -> None:
    """По расписанию (00:00): итог по накопленным голосам, HTML-упоминания в GROUP_ID."""
    if not poll_results:
        return

    # Индексы совпадают с NIGHT_POLL_OPTIONS: 0 — «хороший», 1 — «позорник»
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
    # Только для неанонимных опросов; при смене голоса запись по user_id перезаписывается
    if not poll_answer.option_ids:
        return
    uid = poll_answer.user.id
    mention = poll_answer.user.get_mention(as_html=True)
    option_index = poll_answer.option_ids[0]
    poll_results[uid] = {
        "mention": mention,
        "option_index": option_index,
    }


# Время в timezone планировщика (Europe/Moscow)
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


async def _scheduler_startup(_dispatcher: Dispatcher) -> None:
    # AsyncIOScheduler требует уже работающий event loop — стартуем после входа в polling
    if not scheduler.running:
        scheduler.start()


if __name__ == "__main__":
    # Повтор при падении long polling (сеть, Telegram и т.д.)
    while True:
        try:
            executor.start_polling(
                dp,
                skip_updates=True,
                on_startup=_scheduler_startup,
            )
        except KeyboardInterrupt:
            raise
        except exceptions.NetworkError:
            logger.warning(
                "Прокси PythonAnywhere временно недоступен (503). Повтор через 60 секунд..."
            )
            time.sleep(60)
        except exceptions.RetryAfter as e:
            time.sleep(e.timeout)
        except Exception:
            logger.exception("Критическая ошибка. Перезапуск через 10 секунд...")
            time.sleep(10)
