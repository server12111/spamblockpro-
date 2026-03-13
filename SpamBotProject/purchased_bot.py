import telebot
import threading
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import db_add_user, db_get_bot_users
from keyboards import broadcast_type_kb

running_bots = {}  # {token: TeleBot}

def _safe_send(b, uid, text):
    try: b.send_message(uid, text, parse_mode='HTML'); return True
    except: return False

def _safe_photo(b, uid, photo, caption):
    try: b.send_photo(uid, photo, caption=caption, parse_mode='HTML'); return True
    except: return False

def make_purchased_bot(db_bot_id: int, token: str, admin_id: int):
    pbot   = telebot.TeleBot(token)
    pstate = {}

    def pk_start():
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton('📤 Отправить сообщение', callback_data='p_send'))
        return kb

    def pk_back():
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton('🔙 Назад', callback_data='p_cancel'))
        return kb

    def pk_close():
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton('❌ Закрыть', callback_data='p_close'))
        return kb

    def pk_reply(uid):
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton('📤 Ответить', callback_data=f'p_reply_{uid}'))
        return kb

    def pk_admin():
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton('📢 Рассылка', callback_data='p_broadcast'))
        return kb

    START_TEXT = ("<b>🤖 Привет! Это бот обратной связи.\n\n"
                  "💬 Отправь своё сообщение и администратор обязательно его прочитает.</b>")

    @pbot.message_handler(commands=['start'])
    def pstart(m):
        db_add_user(db_bot_id, m.from_user.id)
        pbot.send_message(m.chat.id, START_TEXT, parse_mode='HTML', reply_markup=pk_start())

    @pbot.message_handler(commands=['admin'])
    def padmin_cmd(m):
        if m.from_user.id != admin_id: return
        pbot.send_message(m.chat.id, "<b>⚙️ Панель админа</b>",
            parse_mode='HTML', reply_markup=pk_admin())

    @pbot.callback_query_handler(func=lambda c: c.data == 'p_send')
    def p_user_send(cb):
        pbot.edit_message_text("<b>💬 Введи своё сообщение:</b>",
            cb.message.chat.id, cb.message.message_id,
            parse_mode='HTML', reply_markup=pk_back())
        pstate[cb.from_user.id] = 'await_msg'

    @pbot.callback_query_handler(func=lambda c: c.data.startswith('p_reply_'))
    def p_admin_reply(cb):
        if cb.from_user.id != admin_id: return
        target = int(cb.data.split('_')[-1])
        pbot.edit_message_text("<b>💬 Введи ответ:</b>",
            cb.message.chat.id, cb.message.message_id,
            parse_mode='HTML', reply_markup=pk_back())
        pstate[cb.from_user.id] = f'await_reply_{target}'

    @pbot.callback_query_handler(func=lambda c: c.data == 'p_cancel')
    def p_cancel(cb):
        pstate.pop(cb.from_user.id, None)
        pbot.edit_message_text(START_TEXT, cb.message.chat.id, cb.message.message_id,
            parse_mode='HTML', reply_markup=pk_start())

    @pbot.callback_query_handler(func=lambda c: c.data == 'p_close')
    def p_close(cb):
        pbot.delete_message(cb.message.chat.id, cb.message.message_id)

    @pbot.callback_query_handler(func=lambda c: c.data == 'cancel')
    def p_cancel_generic(cb):
        pbot.delete_message(cb.message.chat.id, cb.message.message_id)
        pstate.pop(cb.from_user.id, None)

    @pbot.callback_query_handler(func=lambda c: c.data == 'p_broadcast')
    def p_broadcast_start(cb):
        if cb.from_user.id != admin_id: return
        pbot.edit_message_text("<b>📢 Выбери тип рассылки:</b>",
            cb.message.chat.id, cb.message.message_id,
            parse_mode='HTML', reply_markup=broadcast_type_kb('p'))

    @pbot.callback_query_handler(func=lambda c: c.data.startswith('bcast_') and c.data.endswith('_p'))
    def p_broadcast_type(cb):
        if cb.from_user.id != admin_id: return
        if 'text' in cb.data:
            pbot.edit_message_text("<b>📝 Введи текст рассылки (HTML):</b>",
                cb.message.chat.id, cb.message.message_id, parse_mode='HTML')
            pstate[cb.from_user.id] = 'p_bcast_text'
        else:
            pbot.edit_message_text("<b>🖼 Отправь фото с подписью (или без):</b>",
                cb.message.chat.id, cb.message.message_id, parse_mode='HTML')
            pstate[cb.from_user.id] = 'p_bcast_photo'

    @pbot.message_handler(func=lambda m: pstate.get(m.from_user.id) == 'await_msg')
    def p_user_text(m):
        username = f"@{m.from_user.username}" if m.from_user.username else "нет"
        text = (f"<b>📥 Сообщение от:</b>\n"
                f"👤 Имя: <b>{m.from_user.full_name}</b>\n"
                f"🔗 Username: {username}\n"
                f"🆔 ID: <code>{m.from_user.id}</code>\n\n"
                f"💬 {m.text}")
        pbot.send_message(admin_id, text, parse_mode='HTML', reply_markup=pk_reply(m.from_user.id))
        pbot.send_message(m.chat.id, "<b>✅ Сообщение отправлено</b>",
            parse_mode='HTML', reply_markup=pk_close())
        pstate.pop(m.from_user.id, None)

    @pbot.message_handler(func=lambda m: isinstance(pstate.get(m.from_user.id), str)
                                         and pstate[m.from_user.id].startswith('await_reply_'))
    def p_admin_text(m):
        if m.from_user.id != admin_id: return
        target_id = int(pstate[m.from_user.id].split('_')[-1])
        pbot.send_message(target_id, f"<b>📥 Сообщение от администратора\n\n💬 {m.text}</b>",
            parse_mode='HTML')
        pbot.send_message(m.chat.id, "<b>✅ Ответ отправлен</b>",
            parse_mode='HTML', reply_markup=pk_close())
        pstate.pop(m.from_user.id, None)

    @pbot.message_handler(func=lambda m: pstate.get(m.from_user.id) == 'p_bcast_text')
    def p_bcast_text(m):
        if m.from_user.id != admin_id: return
        pstate.pop(m.from_user.id, None)
        users = db_get_bot_users(db_bot_id)
        sent  = sum(1 for uid in users if _safe_send(pbot, uid, m.text))
        pbot.send_message(m.chat.id, f"<b>✅ Рассылка завершена: {sent}/{len(users)}</b>",
            parse_mode='HTML', reply_markup=pk_close())

    @pbot.message_handler(content_types=['photo'],
                          func=lambda m: pstate.get(m.from_user.id) == 'p_bcast_photo')
    def p_bcast_photo(m):
        if m.from_user.id != admin_id: return
        pstate.pop(m.from_user.id, None)
        users   = db_get_bot_users(db_bot_id)
        photo   = m.photo[-1].file_id
        caption = m.caption or ''
        sent    = sum(1 for uid in users if _safe_photo(pbot, uid, photo, caption))
        pbot.send_message(m.chat.id, f"<b>✅ Рассылка завершена: {sent}/{len(users)}</b>",
            parse_mode='HTML', reply_markup=pk_close())

    return pbot


def launch_bot(db_bot_id: int, token: str, admin_id: int) -> bool:
    if token in running_bots: return True
    try:
        pbot = make_purchased_bot(db_bot_id, token, admin_id)
        pbot.get_me()
        running_bots[token] = pbot
        threading.Thread(target=pbot.infinity_polling, daemon=True).start()
        return True
    except Exception as e:
        print(f'[ERROR] Bot launch failed: {e}')
        return False
