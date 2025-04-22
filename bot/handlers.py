# bot.handlers.py
from telegram import Update
from telegram.ext import CommandHandler, Application, ContextTypes, filters, MessageHandler, ConversationHandler
from bot.DB import get_session, User
import re
from bot.DB import TrackedBond
from database.bond_update import get_next_coupon
from database.events import fetch_bond_events
from database.figi_lookup import get_figi_by_ticker_and_classcode
from sqlalchemy.orm import selectinload
from database.moex_name_lookup import get_bond_name_from_moex
from database.bond_utils import update_bond_coupon_info
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
from datetime import datetime

import logging
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

ISIN_PATTERN = re.compile(r'^[A-Z]{2}[A-Z0-9]{10}$')  # Пример: RU000A105TJ2
AWAITING_ISIN_TO_REMOVE = 1
AWAITING_ISIN_TO_ADD = 2


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    session = get_session()

    # Проверка: есть ли пользователь в БД
    db_user = session.query(User).filter_by(tg_id=user.id).first()
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
    user = session.query(User) \
        .options(selectinload(User.tracked_bonds)) \
        .filter_by(tg_id=update.effective_user.id) \
        .first()

    if not user or not user.tracked_bonds:
        await update.message.reply_text("❗️Ты пока не отслеживаешь ни одной облигации.")
        session.close()
        return

    text = "📋 Вот список твоих отслеживаемых бумаг:\n\n"
    logging.info(f"Found user {user.id} with {len(user.tracked_bonds)} tracked bonds.")
    for bond in user.tracked_bonds:
        logging.info(f"Processing bond: {bond.isin}, Name: {bond.name}")
        added = bond.added_at.strftime("%Y-%m-%d")

        display_name = bond.name
        if not display_name:
            moex_name = await get_bond_name_from_moex(bond.isin)
            if moex_name:
                display_name = moex_name
                bond.name = moex_name
                session.commit()
                logging.info(f"Bond name updated to: {display_name}")

        if not display_name:
            display_name = bond.isin

        # читаем купон из модели
        next_coupon_text = ""
        if bond.next_coupon_date and bond.next_coupon_value:
            next_coupon_text = (
                f"\n👉 Следующий купон: {bond.next_coupon_date} на сумму {bond.next_coupon_value} руб."
            )

        text += f"• {display_name} ({bond.isin}, добавлена {added})\n"

    session.close()
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

    moex_name = await get_bond_name_from_moex(text)
    bond = TrackedBond(user_id=user_id, isin=text, name=moex_name)
    session.add(bond)
    session.commit()

    try:
        await get_figi_by_ticker_and_classcode(text)
    except Exception as e:
        context.bot_data.get("logger", print)(f"⚠️ Не удалось получить FIGI для {text}: {e}")

    bond = session.query(TrackedBond).filter_by(user_id=user_id, isin=text).first()

    if not bond.name and moex_name:
        bond.name = moex_name
        session.commit()

    logger = context.bot_data.get("logger", print)

    # Пробуем сначала get_next_coupon
    coupon_set = False
    try:
        next_coupon = await get_next_coupon(bond.isin, bond.figi, bond, session)
        if next_coupon:
            bond.next_coupon_date = next_coupon['date']
            bond.next_coupon_value = next_coupon['value']
            session.commit()
            coupon_set = True
    except Exception as e:
        logger(f"⚠️ Не удалось получить следующий купон для {text}: {e}")

    # Если купон не установлен — вызываем fallback
    if not coupon_set:
        await update_bond_coupon_info(bond, session, logger)

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


async def show_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_session()
    user = session.query(User) \
        .options(selectinload(User.tracked_bonds)) \
        .filter_by(tg_id=update.effective_user.id) \
        .first()

    if not user or not user.tracked_bonds:
        await update.message.reply_text("❗️ Ты пока не отслеживаешь ни одной облигации.")
        session.close()
        return

    text = "📊 Ближайшие события по твоим облигациям:\n\n"
    for bond in user.tracked_bonds:
        next_event = None
        if bond.next_coupon_date:
            next_event = f"{bond.next_coupon_date} — выплата купона {bond.next_coupon_value:.2f} руб."

        if next_event:
            text += f"• {bond.name or bond.isin}:\n  🏷️ {next_event}\n"
        else:
            text += f"• {bond.name or bond.isin}:\n  ✨ Нет ближайших событий\n"

    session.close()
    await update.message.reply_text(text)


async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_session()
    user = session.query(User) \
        .options(selectinload(User.tracked_bonds)) \
        .filter_by(tg_id=update.effective_user.id) \
        .first()

    if not user or not user.tracked_bonds:
        await update.message.reply_text("❗️ Ты пока не отслеживаешь ни одной облигации.")
        session.close()
        return

    keyboard_buttons = [[InlineKeyboardButton(bond.name or bond.isin, callback_data=bond.isin)] for bond in
                        user.tracked_bonds]
    reply_markup = InlineKeyboardMarkup(keyboard_buttons)

    await update.message.reply_text("Выберите облигацию:", reply_markup=reply_markup)
    session.close()


async def bond_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    isin = query.data
    events = await fetch_bond_events(isin)

    reply_text = f"📊 Информация по облигации {isin}:\n\n"

    current_date = datetime.now().date()  # Текущая дата

    # Купоны
    if events.get("coupons"):
        # Ближайший купон
        nearest_coupon = min((event for event in events["coupons"] if event.get('coupondate')),
                             key=lambda x: x.get('coupondate'),
                             default=None)
        if nearest_coupon:
            reply_text += "📝 Купон:\n"
            reply_text += f"- Дата: {nearest_coupon.get('coupondate')}; Размер купона: {nearest_coupon.get('value')} руб.\n"

    # Амортизации
    if events.get("amortizations"):
        # Самая близкая будущая амортизация
        nearest_amortization = min((event for event in events["amortizations"]
                                    if datetime.strptime(event.get('amortdate'), '%d.%m.%Y').date() > current_date),
                                  key=lambda x: datetime.strptime(x.get('amortdate'), '%d.%m.%Y').date(),
                                  default=None)
        if nearest_amortization:
            reply_text += "\n📝 Амортизация:\n"
            reply_text += f"- Дата: {nearest_amortization.get('amortdate')}; Сумма амортизации: {nearest_amortization.get('value')} руб.\n"
        else:
            reply_text += "\n📌 Амортизация отсутствует или прошла.\n"

    # Оферты (сообщение об отсутствии оферт)
    if events.get("offers") and events["offers"]:
        reply_text += "\n📝 Оферты:\n"
        for event in events["offers"]:
            offer_date = event.get('offerdate')
            price = event.get('price')
            if price is not None:
                reply_text += f"- Дата: {offer_date}; Цена оферты: {price} руб.\n"
    else:
        reply_text += "\n📌 Оферты отсутствуют.\n"

    # Если нет никаких событий
    if not any([events.get("coupons"), events.get("amortizations"), events.get("offers")]):
        reply_text += "\nНет событий для этой облигации."

    await query.edit_message_text(reply_text)


def register_handlers(app: Application):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_tracked_bonds))
    app.add_handler(CommandHandler("events", show_events))
    app.add_handler(CallbackQueryHandler(bond_info_callback))  # Добавляем обработчик callback-запросов
    app.add_handler(CommandHandler("info", info_command))

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
