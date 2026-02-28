import logging
from aiogram import Bot, Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.enums import ParseMode
from aiogram.filters import Command

logger = logging.getLogger(__name__)

admin_router = Router()


async def _safe_edit(message, text: str) -> None:
    """Edit message with Markdown, fallback to plain text."""
    try:
        await message.edit_text(text, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        await message.edit_text(text, parse_mode=None)

# Temporary storage for rules awaiting edit (admin_user_id -> rule_id)
_pending_edits: dict[int, int] = {}


async def notify_admin_new_rule(
    bot: Bot,
    admin_ids: set[int],
    rule: dict,
) -> None:
    """Send rule approval request to all admins."""
    rule_id = rule["id"]
    text = (
        f"\U0001f4dd *Новое правило из диалога:*\n\n"
        f"Вопрос: _{rule.get('source_question', '?')}_\n"
        f"Уточнение: _{rule.get('source_correction', '?')}_\n\n"
        f"Предложенное правило:\n"
        f"\u00ab{rule.get('rule_text', '?')}\u00bb\n\n"
        f"Категория: `{rule.get('category', '?')}`\n"
        f"Ключевые слова: {', '.join(rule.get('keywords', []))}"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="\u2705 Одобрить", callback_data=f"rule_approve:{rule_id}"),
            InlineKeyboardButton(text="\u270f\ufe0f Редактировать", callback_data=f"rule_edit:{rule_id}"),
            InlineKeyboardButton(text="\u274c Отклонить", callback_data=f"rule_reject:{rule_id}"),
        ]
    ])

    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.warning("Failed to notify admin %s: %s", admin_id, e)


async def notify_admin_new_alias(
    bot: Bot,
    admin_ids: set[int],
    alias_row: dict,
) -> None:
    """Send alias approval request to all admins."""
    alias_id = alias_row["id"]
    text = (
        f"\U0001f4dd *Новый алиас названия:*\n\n"
        f"Пользователь написал: _{alias_row.get('alias', '?')}_\n"
        f"Значение в базе: _{alias_row.get('canonical_name', '?')}_\n"
        f"Тип: `{alias_row.get('entity_type', '?')}`"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="\u2705 Одобрить", callback_data=f"alias_approve:{alias_id}"),
            InlineKeyboardButton(text="\u274c Отклонить", callback_data=f"alias_reject:{alias_id}"),
        ]
    ])

    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.warning("Failed to notify admin %s about alias: %s", admin_id, e)


@admin_router.callback_query(F.data.startswith("rule_approve:"))
async def handle_rule_approve(callback: CallbackQuery) -> None:
    from bot.telegram import is_admin
    if not is_admin(callback.from_user.id):
        await callback.answer("\u26d4 Только для админов", show_alert=True)
        return

    rule_id = int(callback.data.split(":")[1])
    from supabase_client import update_rule_status
    success = update_rule_status(rule_id, "approved", approved_by=callback.from_user.id)

    if success:
        await _safe_edit(callback.message, callback.message.text + "\n\n\u2705 Одобрено")
        from knowledge.store import refresh_store
        refresh_store()
    else:
        await callback.answer("\u274c Ошибка сохранения", show_alert=True)
    await callback.answer()


@admin_router.callback_query(F.data.startswith("rule_reject:"))
async def handle_rule_reject(callback: CallbackQuery) -> None:
    from bot.telegram import is_admin
    if not is_admin(callback.from_user.id):
        await callback.answer("\u26d4 Только для админов", show_alert=True)
        return

    rule_id = int(callback.data.split(":")[1])
    from supabase_client import update_rule_status
    success = update_rule_status(rule_id, "rejected")

    if success:
        await _safe_edit(callback.message, callback.message.text + "\n\n\u274c Отклонено")
    else:
        await callback.answer("\u274c Ошибка сохранения", show_alert=True)
    await callback.answer()


@admin_router.callback_query(F.data.startswith("rule_edit:"))
async def handle_rule_edit(callback: CallbackQuery) -> None:
    from bot.telegram import is_admin
    if not is_admin(callback.from_user.id):
        await callback.answer("\u26d4 Только для админов", show_alert=True)
        return

    rule_id = int(callback.data.split(":")[1])
    _pending_edits[callback.from_user.id] = rule_id
    await callback.message.edit_text(
        callback.message.text + "\n\n\u270f\ufe0f Отправьте новый текст правила:",
        parse_mode=ParseMode.MARKDOWN,
    )
    await callback.answer()


@admin_router.message(F.text & ~F.text.startswith("/"), lambda msg: msg.from_user.id in _pending_edits)
async def handle_rule_edit_text(message: Message) -> None:
    """Catch admin's edited rule text if they have a pending edit."""
    from bot.telegram import is_admin
    user_id = message.from_user.id
    if not is_admin(user_id):
        return

    rule_id = _pending_edits.pop(user_id)
    new_text = message.text.strip()

    from supabase_client import update_rule_text, update_rule_status
    update_rule_text(rule_id, new_text)
    update_rule_status(rule_id, "approved", approved_by=user_id)

    from knowledge.store import refresh_store
    refresh_store()

    await message.answer(f"\u2705 Правило #{rule_id} обновлено и одобрено:\n\u00ab{new_text}\u00bb")


@admin_router.callback_query(F.data.startswith("alias_approve:"))
async def handle_alias_approve(callback: CallbackQuery) -> None:
    from bot.telegram import is_admin
    if not is_admin(callback.from_user.id):
        await callback.answer("\u26d4 Только для админов", show_alert=True)
        return

    alias_id = int(callback.data.split(":")[1])
    from supabase_client import update_alias_status
    success = update_alias_status(alias_id, "approved")

    if success:
        await _safe_edit(callback.message, callback.message.text + "\n\n\u2705 Одобрено")
        from knowledge.store import refresh_store
        refresh_store()
    else:
        await callback.answer("\u274c Ошибка сохранения", show_alert=True)
    await callback.answer()


@admin_router.callback_query(F.data.startswith("alias_reject:"))
async def handle_alias_reject(callback: CallbackQuery) -> None:
    from bot.telegram import is_admin
    if not is_admin(callback.from_user.id):
        await callback.answer("\u26d4 Только для админов", show_alert=True)
        return

    alias_id = int(callback.data.split(":")[1])
    from supabase_client import update_alias_status
    success = update_alias_status(alias_id, "rejected")

    if success:
        await _safe_edit(callback.message, callback.message.text + "\n\n\u274c Отклонено")
    else:
        await callback.answer("\u274c Ошибка сохранения", show_alert=True)
    await callback.answer()
