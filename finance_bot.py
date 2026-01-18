import os
import sqlite3
import random
from datetime import datetime
from telegram import (
    Update, ReplyKeyboardMarkup,
  InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
  Application, CommandHandler, MessageHandler,
  CallbackQueryHandler, ConversationHandler,
  ContextTypes, filters
)
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
DB_NAME = "finance.db"

CATEGORIES = {
  "🏠 Обязательные расходы": 0.50,
  "🎯 Накопления": 0.20,
  "🎉 Личные расходы": 0.15,
  "📈 Инвестиции": 0.10,
  "🎁 Подарки": 0.05,
  "💼 Образование": 0.00,
  "🛡 Резерв": 0.00,
}

QUOTES = [
  "Не экономь то, что осталось после трат — трать то, что осталось после сбережений. — Уоррен Баффет",
  "Богатство — это не доход, а привычка. — Роберт Кийосаки",
  "Инвестиции — это отказ от потребления сегодня ради большего завтра.",
  "Если ты не найдёшь способ зарабатывать, пока спишь — будешь работать всю жизнь. — Баффет",
]

MAIN_MENU = [
  ["💰 Распределить доход", "✉️ Мои категории"],
  ["📊 Статистика", "💡 Цитаты и советы"],
]

INPUT_INCOME, MANUAL = range(2)

def db():
  return sqlite3.connect(DB_NAME)

def init_db():
  with db() as con:
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
      user_id INTEGER PRIMARY KEY,
      created_at TEXT
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories (
      user_id INTEGER,
      name TEXT,
      balance REAL
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
      user_id INTEGER,
      category TEXT,
      amount REAL,
      created_at TEXT
    )""")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  with db() as con:
    cur = con.cursor()
    cur.execute("INSERT OR IGNORE INTO users VALUES (?, ?)",
        (user_id, datetime.now().isoformat()))
    cur.execute("DELETE FROM categories WHERE user_id = ?", (user_id,))
    for name in CATEGORIES:
      cur.execute(
      "INSERT INTO categories VALUES (?, ?, ?)",
      (user_id, name, 0.0)
      )
  await update.message.reply_text(
    "👋 Финансовый бот готов к работе",
    reply_markup=ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)
  )

async def start_distribution(update: Update, context: ContextTypes.DEFAULT_TYPE):
  await update.message.reply_text("Введите сумму дохода:")
  return INPUT_INCOME

async def input_income(update: Update, context: ContextTypes.DEFAULT_TYPE):
  try:
    income = float(update.message.text.replace(",", "."))
    if income <= 0:
      raise ValueError
  except ValueError:
    await update.message.reply_text("Введите корректную сумму")
    return INPUT_INCOME

  context.user_data["income"] = income
  context.user_data["manual"] = {}
  context.user_data["index"] = 0

  name = list(CATEGORIES.keys())[0]
  await update.message.reply_text(
    f"Введите сумму для **{name}** (осталось: {income:,.2f} ₽):",
    parse_mode="Markdown"
  )
  return MANUAL

async def manual_distribution(update: Update, context: ContextTypes.DEFAULT_TYPE):
  income = context.user_data["income"]
  data = context.user_data["manual"]
  index = context.user_data["index"]
  name = list(CATEGORIES.keys())[index]

  try:
    value = float(update.message.text.replace(",", "."))
    if value < 0:
      raise ValueError
  except ValueError:
    await update.message.reply_text("Введите число")
    return MANUAL

  if sum(data.values()) + value > income:
    await update.message.reply_text("Превышает остаток")
    return MANUAL

  data[name] = value
  context.user_data["index"] += 1

  if context.user_data["index"] < len(CATEGORIES):
    remaining = income - sum(data.values())
    next_name = list(CATEGORIES.keys())[context.user_data["index"]]
    await update.message.reply_text(
      f"{next_name} (осталось: {remaining:,.2f} ₽):"
    )
    return MANUAL

  user_id = update.effective_user.id
  with db() as con:
    cur = con.cursor()
    for cat, amount in data.items():
      cur.execute(
      "UPDATE categories SET balance = balance + ? "
      "WHERE user_id = ? AND name = ?",
      (amount, user_id, cat)
      )
      cur.execute(
      "INSERT INTO transactions VALUES (?, ?, ?, ?)",
      (user_id, cat, amount, datetime.now().isoformat())
      )

  await update.message.reply_text("✅ Доход распределён")
  return ConversationHandler.END

async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  with db() as con:
    cur = con.cursor()
    cur.execute("SELECT name, balance FROM categories WHERE user_id = ?", (user_id,))
    rows = cur.fetchall()

  text = "✉️ **Категории:**\n\n"
  for name, bal in rows:
    text += f"{name}: {bal:,.2f} ₽\n"

  await update.message.reply_text(text, parse_mode="Markdown")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  with db() as con:
    cur = con.cursor()
    cur.execute("""
    SELECT category, SUM(amount)
    FROM transactions
    WHERE user_id = ?
    GROUP BY category
    """, (user_id,))
    rows = cur.fetchall()

  if not rows:
    await update.message.reply_text("Нет данных")
    return

  text = "📊 **Статистика:**\n\n"
  total = 0
  for cat, amt in rows:
    text += f"{cat}: {amt:,.2f} ₽\n"
    total += amt

  text += f"\n💰 Всего: {total:,.2f} ₽"
  await update.message.reply_text(text, parse_mode="Markdown")

async def quotes(update: Update, context: ContextTypes.DEFAULT_TYPE):
  await update.message.reply_text(
    f"💡 {random.choice(QUOTES)}"
  )

def main():
  init_db()
  app = Application.builder().token(BOT_TOKEN).build()

  app.add_handler(CommandHandler("start", start))
  app.add_handler(MessageHandler(filters.Regex("^💰 Распределить доход$"), start_distribution))
  app.add_handler(MessageHandler(filters.Regex("^✉️ Мои категории$"), show_categories))
  app.add_handler(MessageHandler(filters.Regex("^📊 Статистика$"), stats))
  app.add_handler(MessageHandler(filters.Regex("^💡 Цитаты и советы$"), quotes))

  app.add_handler(ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^💰 Распределить доход$"), start_distribution)],
    states={
      INPUT_INCOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_income)],
      MANUAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, manual_distribution)],
    },
    fallbacks=[CommandHandler("start", start)]
  ))

  app.run_polling()

if __name__ == "__main__":
  main()
