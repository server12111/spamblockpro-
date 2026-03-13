import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import SUPER_ADMIN, ADMIN_USERNAME, TON_WALLET
from database import (db_add_user, db_get_owner_bot, db_add_bot,
                       db_get_all_users, db_get_bot_users, db_get_stats,
                       get_price, set_price)
from keyboards import (start_kb, back_to_start_kb, back_to_payment_kb, cancel_kb,
                       close_kb, reply_kb, payment_kb, cryptobot_kb,
                       broadcast_type_kb, admin_kb, super_admin_kb,
                       start_text, buy_text)
from payments import (cb_create_invoice, cb_check_invoice,
                      get_ton_amount, ton_payment_link, ton_check_transfer)
from purchased_bot import launch_bot

def register(bot: telebot.TeleBot):
    state            = {}
    pending_payments = {}

    def _safe_send(uid, text):
        try: bot.send_message(uid, text, parse_mode='HTML'); return True
        except: return False

    def _safe_photo(uid, photo, caption):
        try: bot.send_photo(uid, photo, caption=caption, parse_mode='HTML'); return True
        except: return False

    def _broadcast_users(user_id, scope):
        if scope == 'all':         return db_get_all_users()
        if user_id == SUPER_ADMIN: return db_get_bot_users(0)
        bot_id = db_get_owner_bot(user_id)
        return db_get_bot_users(bot_id) if bot_id else []

    # ── /start ───────────────────────────────────────────
    @bot.message_handler(commands=['start'])
    def cmd_start(m):
        db_add_user(0, m.from_user.id)
        bot.send_message(m.chat.id, start_text(ADMIN_USERNAME),
            parse_mode='HTML', reply_markup=start_kb())

    # ── /admin ───────────────────────────────────────────
    @bot.message_handler(commands=['admin'])
    def cmd_admin(m):
        if m.from_user.id == SUPER_ADMIN:
            bot.send_message(m.chat.id, "<b>⚙️ Панель супер-админа</b>",
                parse_mode='HTML', reply_markup=super_admin_kb())
        elif db_get_owner_bot(m.from_user.id):
            bot.send_message(m.chat.id, "<b>⚙️ Панель админа</b>",
                parse_mode='HTML', reply_markup=admin_kb())

    # ── Навигация назад ──────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data == 'back_to_start')
    def back_to_start_cb(cb):
        state.pop(cb.from_user.id, None)
        pending_payments.pop(cb.from_user.id, None)
        bot.edit_message_text(start_text(ADMIN_USERNAME),
            cb.message.chat.id, cb.message.message_id,
            parse_mode='HTML', reply_markup=start_kb())

    @bot.callback_query_handler(func=lambda c: c.data == 'back_to_payment')
    def back_to_payment_cb(cb):
        state.pop(cb.from_user.id, None)
        pending_payments.pop(cb.from_user.id, None)
        bot.edit_message_text(buy_text(),
            cb.message.chat.id, cb.message.message_id,
            parse_mode='HTML', reply_markup=payment_kb())

    # ── Отправить сообщение ──────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data == 'user_send')
    def user_send(cb):
        bot.edit_message_text("<b>💬 Введи своё сообщение:</b>",
            cb.message.chat.id, cb.message.message_id,
            parse_mode='HTML', reply_markup=back_to_start_kb())
        state[cb.from_user.id] = 'await_user_msg'

    @bot.callback_query_handler(func=lambda c: c.data.startswith('admin_reply_'))
    def admin_reply(cb):
        target = int(cb.data.split('_')[-1])
        bot.edit_message_text("<b>💬 Введи ответ:</b>",
            cb.message.chat.id, cb.message.message_id,
            parse_mode='HTML', reply_markup=cancel_kb())
        state[cb.from_user.id] = f'await_admin_msg_{target}'

    @bot.callback_query_handler(func=lambda c: c.data == 'cancel')
    def cancel_cb(cb):
        bot.delete_message(cb.message.chat.id, cb.message.message_id)
        state.pop(cb.from_user.id, None)
        pending_payments.pop(cb.from_user.id, None)

    @bot.callback_query_handler(func=lambda c: c.data == 'close')
    def close_cb(cb):
        bot.delete_message(cb.message.chat.id, cb.message.message_id)

    @bot.message_handler(func=lambda m: state.get(m.from_user.id) == 'await_user_msg')
    def user_text(m):
        username = f"@{m.from_user.username}" if m.from_user.username else "нет"
        text = (f"<b>📥 Сообщение от:</b>\n"
                f"👤 Имя: <b>{m.from_user.full_name}</b>\n"
                f"🔗 Username: {username}\n"
                f"🆔 ID: <code>{m.from_user.id}</code>\n\n"
                f"💬 {m.text}")
        bot.send_message(SUPER_ADMIN, text, parse_mode='HTML', reply_markup=reply_kb(m.from_user.id))
        bot.send_message(m.chat.id, "<b>✅ Сообщение отправлено</b>",
            parse_mode='HTML', reply_markup=close_kb())
        state.pop(m.from_user.id, None)

    @bot.message_handler(func=lambda m: isinstance(state.get(m.from_user.id), str)
                                        and state[m.from_user.id].startswith('await_admin_msg_'))
    def admin_text(m):
        target_id = int(state[m.from_user.id].split('_')[-1])
        bot.send_message(target_id, f"<b>📥 Сообщение от администратора\n\n💬 {m.text}</b>",
            parse_mode='HTML')
        bot.send_message(m.chat.id, "<b>✅ Ответ отправлен</b>",
            parse_mode='HTML', reply_markup=close_kb())
        state.pop(m.from_user.id, None)

    # ── Купить бота ──────────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data == 'buy_bot')
    def buy_bot_cb(cb):
        bot.edit_message_text(buy_text(),
            cb.message.chat.id, cb.message.message_id,
            parse_mode='HTML', reply_markup=payment_kb())

    @bot.callback_query_handler(func=lambda c: c.data == 'pay_cryptobot')
    def pay_cryptobot_cb(cb):
        invoice = cb_create_invoice(cb.from_user.id)
        if not invoice:
            bot.answer_callback_query(cb.id, "❌ Ошибка создания инвойса. Попробуй ещё раз.", show_alert=True)
            return
        pending_payments[cb.from_user.id] = invoice['invoice_id']
        bot.edit_message_text(
            f"<b>💳 Оплата через CryptoBot</b>\n\n"
            f"Сумма: <b>{get_price()} USDT</b>\n\n"
            f"Нажми кнопку ниже, оплати и вернись сюда — нажми «Проверить оплату».",
            cb.message.chat.id, cb.message.message_id,
            parse_mode='HTML', reply_markup=cryptobot_kb(invoice['pay_url'], invoice['invoice_id']))

    @bot.callback_query_handler(func=lambda c: c.data.startswith('check_payment_'))
    def check_payment_cb(cb):
        invoice_id = int(cb.data.split('_')[-1])
        invoice    = cb_check_invoice(invoice_id)
        if invoice and invoice.get('status') == 'paid':
            pending_payments.pop(cb.from_user.id, None)
            state[cb.from_user.id] = 'await_bot_token'
            bot.edit_message_text(
                "<b>✅ Оплата получена!\n\n"
                "🤖 Введи токен своего бота (получи в @BotFather):</b>",
                cb.message.chat.id, cb.message.message_id,
                parse_mode='HTML', reply_markup=cancel_kb())
        else:
            bot.answer_callback_query(cb.id, "❌ Оплата не найдена. Попробуй ещё раз.", show_alert=True)

    @bot.callback_query_handler(func=lambda c: c.data == 'pay_ton')
    def pay_ton_cb(cb):
        bot.answer_callback_query(cb.id, "⏳ Получаю курс TON...")
        ton_amount = get_ton_amount()
        if ton_amount <= 0:
            bot.answer_callback_query(cb.id, "❌ Не удалось получить курс TON.", show_alert=True)
            return
        payment_code = f"SPB{cb.from_user.id}"
        link = ton_payment_link(ton_amount, payment_code)
        state[cb.from_user.id] = {'step': 'ton_pending', 'ton': ton_amount, 'code': payment_code}
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton('💎 Открыть TON Keeper и оплатить', url=link))
        kb.add(InlineKeyboardButton('✅ Я оплатил — проверить',         callback_data='ton_check_auto'))
        kb.add(InlineKeyboardButton('🔙 Назад',                          callback_data='back_to_payment'))
        bot.edit_message_text(
            f"<b>💎 Оплата через TON Keeper</b>\n\n"
            f"Сумма: <b>{ton_amount} TON</b> (~${get_price()})\n\n"
            f"Нажми кнопку ниже — TON Keeper откроется с уже заполненной суммой, адресом и комментарием.\n\n"
            f"Адрес (вручную):\n<code>{TON_WALLET}</code>\n\n"
            f"⚠️ <b>ВАЖНО: при отправке обязательно укажи комментарий:</b>\n"
            f"<code>{payment_code}</code>\n"
            f"<i>(без комментария оплата не будет засчитана)</i>\n\n"
            f"После оплаты нажми «Я оплатил» — бот проверит автоматически.\n"
            f"Проверка работает в течение <b>2 часов</b>.",
            cb.message.chat.id, cb.message.message_id,
            parse_mode='HTML', reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data == 'ton_check_auto')
    def ton_check_auto_cb(cb):
        uid = cb.from_user.id
        s   = state.get(uid)
        if not isinstance(s, dict) or 'ton' not in s:
            bot.answer_callback_query(cb.id, "❌ Сессия истекла. Начни заново.", show_alert=True)
            return
        ton_amount   = s['ton']
        payment_code = s.get('code', f"SPB{uid}")
        bot.answer_callback_query(cb.id, "🔍 Проверяю блокчейн...")
        bot.edit_message_text("<b>🔍 Проверяю блокчейн TON...</b>",
            cb.message.chat.id, cb.message.message_id, parse_mode='HTML')
        found = ton_check_transfer(uid, ton_amount, payment_code)
        if found:
            state.pop(uid, None)
            state[uid] = 'await_bot_token'
            bot.edit_message_text(
                "<b>✅ Оплата найдена!\n\n"
                "🤖 Введи токен своего бота (получи в @BotFather):</b>",
                cb.message.chat.id, cb.message.message_id,
                parse_mode='HTML', reply_markup=cancel_kb())
        else:
            link = ton_payment_link(ton_amount, payment_code)
            kb   = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton('💎 Открыть TON Keeper', url=link))
            kb.add(InlineKeyboardButton('🔄 Проверить снова',    callback_data='ton_check_auto'))
            kb.add(InlineKeyboardButton('🔙 Назад',              callback_data='back_to_payment'))
            bot.edit_message_text(
                f"<b>❌ Оплата не найдена</b>\n\n"
                f"Убедись что:\n"
                f"• Отправил <b>{ton_amount} TON</b>\n"
                f"• Указал комментарий: <code>{payment_code}</code>\n"
                f"• Транзакция прошла подтверждение\n"
                f"• Оплата не старше 2 часов\n\n"
                f"Попробуй ещё раз через минуту или напиши {ADMIN_USERNAME}.",
                cb.message.chat.id, cb.message.message_id,
                parse_mode='HTML', reply_markup=kb)

    # ── Настройка бота после оплаты ──────────────────────
    @bot.message_handler(func=lambda m: state.get(m.from_user.id) == 'await_bot_token')
    def get_bot_token(m):
        token_val = m.text.strip()
        if ':' not in token_val or len(token_val) < 30:
            bot.send_message(m.chat.id, "<b>❌ Неверный формат токена. Попробуй ещё раз:</b>",
                parse_mode='HTML')
            return
        try:
            telebot.TeleBot(token_val).get_me()
        except:
            bot.send_message(m.chat.id, "<b>❌ Токен недействителен. Проверь и введи правильный:</b>",
                parse_mode='HTML')
            return
        state[m.from_user.id] = {'step': 'await_admin_id', 'token': token_val}
        bot.send_message(m.chat.id,
            "<b>👤 Теперь введи свой Telegram ID\n"
            "(сообщения от пользователей будут приходить именно тебе)\n\n"
            "Узнать свой ID: @userinfobot</b>",
            parse_mode='HTML', reply_markup=cancel_kb())

    @bot.message_handler(func=lambda m: isinstance(state.get(m.from_user.id), dict)
                                        and state[m.from_user.id].get('step') == 'await_admin_id')
    def get_admin_id(m):
        try:
            admin_id_val = int(m.text.strip())
        except ValueError:
            bot.send_message(m.chat.id, "<b>❌ ID должен быть числом. Попробуй ещё раз:</b>",
                parse_mode='HTML')
            return
        token_val = state.pop(m.from_user.id)['token']
        try:
            bot_db_id = db_add_bot(m.from_user.id, token_val, admin_id_val)
        except:
            bot.send_message(m.chat.id,
                "<b>❌ Этот токен уже зарегистрирован. Используй другой.</b>", parse_mode='HTML')
            return
        if launch_bot(bot_db_id, token_val, admin_id_val):
            bot.send_message(m.chat.id,
                "<b>🎉 Бот успешно запущен!\n\n"
                "Управляй рассылкой через /admin в своём боте.</b>",
                parse_mode='HTML', reply_markup=close_kb())
            bot.send_message(SUPER_ADMIN,
                f"<b>🆕 Новый бот подключён</b>\n"
                f"Owner: <code>{m.from_user.id}</code> | Admin: <code>{admin_id_val}</code>",
                parse_mode='HTML')
        else:
            bot.send_message(m.chat.id,
                f"<b>❌ Ошибка запуска. Свяжись с {ADMIN_USERNAME}.</b>", parse_mode='HTML')

    # ── Рассылка ─────────────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data == 'broadcast')
    def broadcast_start(cb):
        if cb.from_user.id != SUPER_ADMIN and not db_get_owner_bot(cb.from_user.id): return
        bot.edit_message_text("<b>📢 Выбери тип рассылки:</b>",
            cb.message.chat.id, cb.message.message_id,
            parse_mode='HTML', reply_markup=broadcast_type_kb('mine'))

    @bot.callback_query_handler(func=lambda c: c.data == 'broadcast_all')
    def broadcast_all_start(cb):
        if cb.from_user.id != SUPER_ADMIN: return
        bot.edit_message_text("<b>📡 Рассылка по всем ботам. Выбери тип:</b>",
            cb.message.chat.id, cb.message.message_id,
            parse_mode='HTML', reply_markup=broadcast_type_kb('all'))

    @bot.callback_query_handler(func=lambda c: c.data.startswith('bcast_') and not c.data.endswith('_p'))
    def broadcast_type(cb):
        parts = cb.data.split('_')
        btype, scope = parts[1], parts[2]
        if btype == 'text':
            bot.edit_message_text("<b>📝 Введи текст рассылки (HTML):</b>",
                cb.message.chat.id, cb.message.message_id, parse_mode='HTML')
            state[cb.from_user.id] = f'bcast_text_{scope}'
        else:
            bot.edit_message_text("<b>🖼 Отправь фото с подписью (или без):</b>",
                cb.message.chat.id, cb.message.message_id, parse_mode='HTML')
            state[cb.from_user.id] = f'bcast_photo_{scope}'

    @bot.message_handler(func=lambda m: isinstance(state.get(m.from_user.id), str)
                                        and state[m.from_user.id].startswith('bcast_text_'))
    def broadcast_text(m):
        scope = state.pop(m.from_user.id).split('_')[-1]
        users = _broadcast_users(m.from_user.id, scope)
        sent  = sum(1 for uid in users if _safe_send(uid, m.text))
        bot.send_message(m.chat.id, f"<b>✅ Рассылка завершена: {sent}/{len(users)}</b>",
            parse_mode='HTML', reply_markup=close_kb())

    @bot.message_handler(content_types=['photo'],
                         func=lambda m: isinstance(state.get(m.from_user.id), str)
                                        and state[m.from_user.id].startswith('bcast_photo_'))
    def broadcast_photo(m):
        scope   = state.pop(m.from_user.id).split('_')[-1]
        users   = _broadcast_users(m.from_user.id, scope)
        photo   = m.photo[-1].file_id
        caption = m.caption or ''
        sent    = sum(1 for uid in users if _safe_photo(uid, photo, caption))
        bot.send_message(m.chat.id, f"<b>✅ Рассылка завершена: {sent}/{len(users)}</b>",
            parse_mode='HTML', reply_markup=close_kb())

    # ── Статистика ───────────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data == 'stats')
    def stats_cb(cb):
        if cb.from_user.id != SUPER_ADMIN: return
        bots_count, main_users, total_users, breakdown = db_get_stats()
        revenue = round(bots_count * get_price(), 2)
        lines   = [f"  {i}. Owner <code>{o}</code> — {u} польз."
                   for i, (o, _, u) in enumerate(breakdown, 1)]
        text = (f"<b>📊 Статистика SpamBot</b>\n{'─'*28}\n"
                f"🤖 Подключённых ботов: <b>{bots_count}</b>\n"
                f"💰 Выручка за всё время: <b>~{revenue} USDT</b>\n"
                f"{'─'*28}\n"
                f"👥 Пользователей в главном боте: <b>{main_users}</b>\n"
                f"👥 Всего пользователей (все боты): <b>{total_users}</b>\n"
                f"{'─'*28}\n"
                f"📋 Боты по кол-ву пользователей:\n"
                f"{chr(10).join(lines) if lines else '  —'}")
        bot.edit_message_text(text, cb.message.chat.id, cb.message.message_id,
            parse_mode='HTML', reply_markup=close_kb())

    # ── Установить цену ──────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data == 'set_price')
    def set_price_cb(cb):
        if cb.from_user.id != SUPER_ADMIN: return
        bot.edit_message_text(
            f"<b>💰 Текущая цена: {get_price()} USDT</b>\n\n"
            f"Введи новую цену (например: 5 или 9.99):",
            cb.message.chat.id, cb.message.message_id,
            parse_mode='HTML', reply_markup=back_to_start_kb())
        state[cb.from_user.id] = 'await_new_price'

    @bot.message_handler(func=lambda m: state.get(m.from_user.id) == 'await_new_price')
    def handle_new_price(m):
        if m.from_user.id != SUPER_ADMIN: return
        try:
            new_price = float(m.text.strip().replace(',', '.'))
            if new_price <= 0: raise ValueError
        except ValueError:
            bot.send_message(m.chat.id, "<b>❌ Неверный формат. Введи число, например: 10</b>",
                parse_mode='HTML')
            return
        set_price(new_price)
        state.pop(m.from_user.id, None)
        bot.send_message(m.chat.id, f"<b>✅ Цена обновлена: {new_price} USDT</b>",
            parse_mode='HTML', reply_markup=close_kb())
