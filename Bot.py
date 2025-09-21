import re
import logging
from datetime import datetime, timedelta
from typing import Optional

import pytz
from aiogram import Bot, Dispatcher, types
from aiogram.filters import BaseFilter
from aiogram.types import Message

API_TOKEN = '7404093097:AAFe3lj23KTkXaR5MjwZbEu2s2Cr2WNWdto'
LOG_CHAT_ID = -1003057764655  # Замените на свой ID

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

PRINCIPAL_ADMIN_ID = 1180547624
bot_admins = {853569105, 6816400085, 328954709}

MSK = pytz.timezone('Europe/Moscow')

async def has_permission(message: Message) -> bool:
    return message.from_user.id == PRINCIPAL_ADMIN_ID or message.from_user.id in bot_admins

def parse_duration_to_timestamp(duration_str: str) -> Optional[int]:
    now = datetime.utcnow()
    try:
        duration_str = duration_str.strip().lower()
        if re.fullmatch(r"\d+", duration_str):
            duration_str += " минут"
        match = re.match(r"(\d+)\s*(минут|мин|час|часа|день|дня|недел|неделя|месяц|год|лет)?", duration_str)
        if not match:
            return None
        value, unit = match.groups()
        value = int(value)
        if unit is None or unit.startswith("мин"):
            delta = timedelta(minutes=value)
        elif unit.startswith("час"):
            delta = timedelta(hours=value)
        elif unit.startswith("день") or unit.startswith("дня"):
            delta = timedelta(days=value)
        elif unit.startswith("недел") or unit.startswith("неделя"):
            delta = timedelta(weeks=value)
        elif unit.startswith("месяц"):
            delta = timedelta(days=30 * value)
        elif unit.startswith("год") or unit.startswith("лет"):
            delta = timedelta(days=365 * value)
        else:
            delta = timedelta(minutes=value)
        until = now + delta
        timestamp = int(until.timestamp())
        if timestamp <= int(now.timestamp()):
            timestamp = int((now + timedelta(seconds=60)).timestamp())
        return timestamp
    except Exception:
        return None

def format_timestamp_msk(ts: int) -> str:
    dt = datetime.utcfromtimestamp(ts).replace(tzinfo=pytz.utc).astimezone(MSK)
    return dt.strftime('%Y-%m-%d %H:%M %Z')

async def log_action(action: str, message: Message, target_user: types.User, reason: str = None):
    text = (
        f"{action}:\n"
        f"Админ: <a href='tg://user?id={message.from_user.id}'>{message.from_user.full_name}</a> (ID: {message.from_user.id})\n"
        f"Пользователь: <a href='tg://user?id={target_user.id}'>{target_user.full_name}</a> (ID: {target_user.id})\n"
        f"Чат: {message.chat.title} (ID: {message.chat.id})"
    )
    if reason:
        text += f"\nПричина: {reason}"
    try:
        await bot.send_message(LOG_CHAT_ID, text, parse_mode="HTML")
    except Exception as e:
        print("Ошибка отправки логов:", e)

class TextCommandFilter(BaseFilter):
    def __init__(self, commands):
        self.commands = commands
    async def __call__(self, message: Message) -> bool:
        text = message.text.lower() if message.text else ""
        for cmd in self.commands:
            if text == cmd or text.startswith(cmd + " "):
                return True
        return False

mute_filter = TextCommandFilter(["мут"])
unmute_filter = TextCommandFilter(["размут"])
ban_filter = TextCommandFilter(["бан"])
unban_filter = TextCommandFilter(["разбан"])
dmute_filter = TextCommandFilter(["дмут"])
dban_filter = TextCommandFilter(["дбан"])
admin_add_filter = TextCommandFilter(["админка"])
admin_del_filter = TextCommandFilter(["админудал"])

async def get_target_user(message: Message) -> Optional[types.User]:
    if message.reply_to_message:
        return message.reply_to_message.from_user
    text = message.text or ""
    match_id = re.search(r"\b(\d{5,})\b", text)
    if match_id:
        user_id = int(match_id.group(1))
        try:
            cm = await bot.get_chat_member(message.chat.id, user_id)
            return cm.user
        except Exception:
            await message.reply(f"Пользователь с ID {user_id} не найден в чате.")
            return None
    match_un = re.search(r"@([a-zA-Z0-9_]{5,})", text)
    if match_un:
        username = match_un.group(1)
        try:
            cm = await bot.get_chat_member(message.chat.id, username)
            return cm.user
        except Exception:
            await message.reply(f"Пользователь @{username} не найден в чате.")
            return None
    await message.reply("Нужно ответить на сообщение пользователя или указать @username или user ID.")
    return None

def extract_time_reason(text: str, command: str):
    pattern = rf"{command}\s+((?:\d+\s*(?:минут|мин|час|часа|день|дня|недел|неделя|месяц|год|лет)?))?\s*(.*)"
    match = re.match(pattern, text.lower())
    if match:
        time_str = match.group(1)
        reason_str = match.group(2).strip()
        return time_str.strip() if time_str else None, reason_str if reason_str else "не указана"
    return None, "не указана"

@dp.message(admin_add_filter)
async def handler_add_admin(message: Message):
    if message.from_user.id != PRINCIPAL_ADMIN_ID:
        await message.reply("Только главный админ может выдавать права.")
        return
    if not message.reply_to_message:
        await message.reply("Ответьте на сообщение пользователя, которого хотите сделать админом бота.")
        return
    user = message.reply_to_message.from_user
    if user.id == PRINCIPAL_ADMIN_ID:
        await message.reply("Главный админ уже обладает правами.")
        return
    if user.id in bot_admins:
        await message.reply("Этот пользователь уже является админом бота.")
        return
    bot_admins.add(user.id)
    await message.reply(f"Пользователь <a href='tg://user?id={user.id}'>{user.full_name}</a> теперь админ бота.", parse_mode="HTML")

@dp.message(mute_filter)
async def handler_mute(message: Message):
    if not await has_permission(message):
        await message.reply("Нет прав.")
        return
    user = await get_target_user(message)
    if not user:
        return
    time_str, reason = extract_time_reason(message.text, "мут")
    until_date = parse_duration_to_timestamp(time_str) if time_str else None
    try:
        await bot.restrict_chat_member(message.chat.id, user.id,
                                      types.ChatPermissions(can_send_messages=False),
                                      until_date=until_date)
        time_text = "навсегда" if until_date is None else f"до {format_timestamp_msk(until_date)}"
        await message.reply(
            f"<a href='tg://user?id={user.id}'>{user.full_name}</a> замучен {time_text} "
            f"администратором <a href='tg://user?id={message.from_user.id}'>{message.from_user.full_name}</a>. "
            f"Причина: {reason}",
            parse_mode="HTML")
        await log_action("Мут", message, user, reason)
    except Exception as e:
        await message.reply(f"Ошибка: {e}")

@dp.message(dmute_filter)
async def handler_dmute(message: Message):
    if not await has_permission(message):
        await message.reply("Нет прав.")
        return
    if not message.reply_to_message:
        await message.reply("Используйте команду как ответ на сообщение пользователя.")
        return
    user = message.reply_to_message.from_user
    time_str, reason = extract_time_reason(message.text, "дмут")
    until_date = parse_duration_to_timestamp(time_str) if time_str else None
    try:
        await bot.restrict_chat_member(message.chat.id, user.id,
                                      types.ChatPermissions(can_send_messages=False),
                                      until_date=until_date)
        await bot.delete_message(message.chat.id, message.reply_to_message.message_id)
        time_text = "навсегда" if until_date is None else f"до {format_timestamp_msk(until_date)}"
        await message.reply(
            f"<a href='tg://user?id={user.id}'>{user.full_name}</a> замучен (сообщение удалено) {time_text}. Причина: {reason}",
            parse_mode="HTML")
        await log_action("Дмут", message, user, reason)
    except Exception as e:
        await message.reply(f"Ошибка: {e}")

@dp.message(ban_filter)
async def handler_ban(message: Message):
    if not await has_permission(message):
        await message.reply("Нет прав.")
        return
    user = await get_target_user(message)
    if not user:
        return
    time_str, reason = extract_time_reason(message.text, "бан")
    until_date = parse_duration_to_timestamp(time_str) if time_str else None
    try:
        await bot.ban_chat_member(message.chat.id, user.id, until_date=until_date)
        time_text = "навсегда" if until_date is None else f"до {format_timestamp_msk(until_date)}"
        await message.reply(
            f"<a href='tg://user?id={user.id}'>{user.full_name}</a> забанен {time_text} "
            f"администратором <a href='tg://user?id={message.from_user.id}'>{message.from_user.full_name}</a>. "
            f"Причина: {reason}",
            parse_mode="HTML"
        )
        await log_action("Бан", message, user, reason)
    except Exception as e:
        await message.reply(f"Ошибка: {e}")

@dp.message(dban_filter)
async def handler_dban(message: Message):
    if not await has_permission(message):
        await message.reply("Нет прав.")
        return
    if not message.reply_to_message:
        await message.reply("Используйте команду как ответ на сообщение пользователя.")
        return
    user = message.reply_to_message.from_user
    time_str, reason = extract_time_reason(message.text, "дбан")
    until_date = parse_duration_to_timestamp(time_str) if time_str else None
    try:
        await bot.ban_chat_member(message.chat.id, user.id, until_date=until_date)
        await bot.delete_message(message.chat.id, message.reply_to_message.message_id)
        time_text = "навсегда" if until_date is None else f"до {format_timestamp_msk(until_date)}"
        await message.reply(
            f"<a href='tg://user?id={user.id}'>{user.full_name}</a> забанен (сообщение удалено) {time_text}. Причина: {reason}",
            parse_mode="HTML"
        )
        await log_action("Дбан", message, user, reason)
    except Exception as e:
        await message.reply(f"Ошибка: {e}")

@dp.message(unban_filter)
async def handler_unban(message: Message):
    if not await has_permission(message):
        await message.reply("Нет прав.")
        return
    user = await get_target_user(message)
    if not user:
        return
    try:
        await bot.unban_chat_member(message.chat.id, user.id)
        await message.reply(
            f"<a href='tg://user?id={user.id}'>{user.full_name}</a> разбанен администратором "
            f"<a href='tg://user?id={message.from_user.id}'>{message.from_user.full_name}</a>.",
            parse_mode="HTML"
        )
        await log_action("Разбан", message, user)
    except Exception as e:
        await message.reply(f"Ошибка: {e}")

@dp.message(unmute_filter)
async def handler_unmute(message: Message):
    if not await has_permission(message):
        await message.reply("Нет прав.")
        return
    user = await get_target_user(message)
    if not user:
        return
    try:
        await bot.restrict_chat_member(
            message.chat.id, user.id,
            types.ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
            ),
            until_date=None
        )
        await message.reply(
            f"<a href='tg://user?id={user.id}'>{user.full_name}</a> размучен администратором "
            f"<a href='tg://user?id={message.from_user.id}'>{message.from_user.full_name}</a>.",
            parse_mode="HTML"
        )
        await log_action("Размут", message, user)
    except Exception as e:
        await message.reply(f"Ошибка: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import asyncio
    asyncio.run(dp.start_polling(bot))
