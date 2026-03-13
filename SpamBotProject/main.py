import telebot
from config import TOKEN
from database import init_db, db_get_all_bots
from purchased_bot import launch_bot, running_bots
import handlers

bot = telebot.TeleBot(TOKEN)
handlers.register(bot)

if __name__ == '__main__':
    init_db()
    for db_bot_id, token, admin_id, owner_id in db_get_all_bots():
        launch_bot(db_bot_id, token, admin_id)
    print(f'[INFO] Started. Loaded {len(running_bots)} purchased bot(s).')
    bot.infinity_polling()
