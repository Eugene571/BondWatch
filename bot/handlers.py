from telegram import Update
from telegram.ext import CommandHandler, Application, ContextTypes, filters, MessageHandler, ConversationHandler
from bot.database import get_session, User
import re
from bot.database import TrackedBond

ISIN_PATTERN = re.compile(r'^[A-Z]{2}[A-Z0-9]{10}$')  # Пример: RU000A105TJ2
AWAITING_ISIN_TO_REMOVE = 1
AWAITING_ISIN_TO_ADD = 2


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    session = get_session()

    # Проверка: есть ли пользователь в БД
    db_user = session.query(User).get(user.id)
    if not db_user:
        # Если нет — добавляем
        new_user = User(tg_id=user.id, full_name=user.full_name)
        session.add(new_user)
        session.commit()
        context.bot_data.get("logger", print)(f"✅ Новый пользователь: {user.full_name} ({user.id})")

    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        "Я BondWatch — бот, который следит за купонами и погашениями твоих облигаций.\n\n"
        "📎 Отправь ISIN, чтобы я добавил бумагу и прислал напоминание о купонах и погашении.\n"
        "Ты можешь бесплатно отслеживать до 3 бумаг.\n\n"
        "🔔 Начнём!"
    )


async def list_tracked_bonds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_session()
    user = session.query(User).filter_by(tg_id=update.effective_user.id).first()

    if not user or not user.tracked_bonds:
        await update.message.reply_text("❗️Ты пока не отслеживаешь ни одной облигации.")
        return

    text = "📋 Вот список твоих отслеживаемых бумаг:\n\n"
    for bond in user.tracked_bonds:
        added = bond.added_at.strftime("%Y-%m-%d")
        text += f"• {bond.isin} (добавлена {added})\n"

    await update.message.reply_text(text)


async def process_add_isin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip().upper()

    if not ISIN_PATTERN.match(text):
        await update.message.reply_text("⚠️ Это не похоже на ISIN. Попробуй ещё раз.")
        return AWAITING_ISIN_TO_ADD

    session = get_session()
    user_id = user.id

    count = session.query(TrackedBond).filter_by(user_id=user_id).count()
    if count >= 3:
        await update.message.reply_text("❌ Ты уже отслеживаешь 3 бумаги. Удали одну, чтобы добавить новую.")
        return ConversationHandler.END

    exists = session.query(TrackedBond).filter_by(user_id=user_id, isin=text).first()
    if exists:
        await update.message.reply_text("✅ Ты уже отслеживаешь эту бумагу.")
        return ConversationHandler.END

    bond = TrackedBond(user_id=user_id, isin=text)
    session.add(bond)
    session.commit()

    await update.message.reply_text(f"📌 Бумага {text} добавлена!")
    return ConversationHandler.END


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("➕ Введи ISIN бумаги, которую хочешь добавить:")
    return AWAITING_ISIN_TO_ADD


async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🗑 Введи ISIN бумаги, которую хочешь удалить из отслеживания:")
    return AWAITING_ISIN_TO_REMOVE


async def process_remove_isin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_session()
    isin = update.message.text.strip().upper()
    user = session.query(User).filter_by(tg_id=update.effective_user.id).first()

    if not user:
        await update.message.reply_text("Ты пока не зарегистрирован. Напиши /start.")
        return ConversationHandler.END

    subscription = session.query(TrackedBond).filter_by(user_id=user.tg_id, isin=isin).first()

    if not subscription:
        await update.message.reply_text(f"❌ Ты не отслеживаешь бумагу с ISIN {isin}.")
    else:
        session.delete(subscription)
        session.commit()
        await update.message.reply_text(f"✅ Бумага {isin} успешно удалена из отслеживания.")

    return ConversationHandler.END


async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🗑 Введи ISIN бумаги, которую хочешь удалить из отслеживания:")
    return AWAITING_ISIN_TO_REMOVE


def register_handlers(app: Application):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_tracked_bonds))

    # /remove диалог
    remove_conv = ConversationHandler(
        entry_points=[CommandHandler("remove", remove_command)],
        states={
            AWAITING_ISIN_TO_REMOVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_remove_isin)],
        },
        fallbacks=[],
    )
    app.add_handler(remove_conv)

    # /add диалог
    add_conv = ConversationHandler(
        entry_points=[CommandHandler("add", add_command)],
        states={
            AWAITING_ISIN_TO_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_add_isin)],
        },
        fallbacks=[],
    )
    app.add_handler(add_conv)
