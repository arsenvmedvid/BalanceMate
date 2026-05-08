import os
import logging
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    filters, ConversationHandler, ContextTypes
)
from groq import Groq
import logic

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
logging.basicConfig(level=logging.INFO)

GENDER, AGE, HEIGHT, WEIGHT, DIARY, SELECT_FOOD = range(6)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "👋 Привіт! Я BalanceMate.\nЯка твоя стать?", 
        reply_markup=ReplyKeyboardMarkup([["Чоловік", "Жінка"]], one_time_keyboard=True, resize_keyboard=True)
    )
    return GENDER

async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["gender"] = update.message.text
    await update.message.reply_text("Скільки тобі років?", reply_markup=ReplyKeyboardRemove())
    return AGE

async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["age"] = int(update.message.text)
    await update.message.reply_text("Який твій зріст (см)?")
    return HEIGHT

async def get_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["height"] = float(update.message.text)
    await update.message.reply_text("Яка твоя вага (кг)?")
    return WEIGHT

async def get_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = context.user_data
    user["weight"] = float(update.message.text)
    n = logic.calculate_norms(user["weight"], user["height"], user["age"], user["gender"])
    user["norms"] = n
    
    # ПОВЕРНУТО ДИЗАЙН ПЛАНУ
    await update.message.reply_text(
        f"📊 Твій план:\n"
        f"🔥 {n['cal']} ккал | 🥩 Б: {n['p']}г | 🥑 Ж: {n['f']}г | 🍞 В: {n['c']}г\n\n"
        "Пиши, що з'їв(ла):"
    )
    return DIARY

async def handle_diary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    context.user_data["pending_foods"] = logic.parse_user_input(user_input)
    context.user_data["final_report"] = []
    context.user_data["total_kbzhv"] = {"cal": 0, "p": 0, "f": 0, "c": 0}
    return await process_next_pending_food(update, context)

async def process_next_pending_food(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending = context.user_data.get("pending_foods", [])
    if not pending:
        return await send_final_report(update, context)
    
    current = pending.pop(0)
    context.user_data["current_weight"] = current["weight"]
    db = logic.load_food_db()
    matches = logic.find_food_matches(current["name"], db)
    
    if len(matches) == 1:
        add_to_totals(context, matches[0], current["weight"])
        return await process_next_pending_food(update, context)
    elif len(matches) > 1:
        buttons = [[m["name"]] for m in matches]
        await update.message.reply_text(
            f"🔍 Знайдено кілька варіантів для '{current['name']}'. Що саме ви мали на увазі?",
            reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True)
        )
        return SELECT_FOOD
    else:
        await update.message.reply_text(f"🌐 Шукаю в мережі: {current['name']}...")
        prompt = f"КБЖВ для {current['name']} {current['weight']}г. Тільки цифри українською."
        try:
            chat = client.chat.completions.create(messages=[{"role":"user","content":prompt}], model="llama3-8b-8192")
            context.user_data["final_report"].append(f"🌍 {current['name']} (ШІ):\n{chat.choices[0].message.content}")
        except:
            context.user_data["final_report"].append(f"❌ {current['name']} не знайдено")
        return await process_next_pending_food(update, context)

async def select_food_from_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    db = logic.load_food_db()
    food = next((f for f in db if f["name"] == choice), None)
    if food:
        add_to_totals(context, food, context.user_data["current_weight"])
    return await process_next_pending_food(update, context)

def add_to_totals(context, food, weight):
    r = weight / 100
    t = context.user_data["total_kbzhv"]
    t["cal"] += food["calories"] * r
    t["p"] += food["proteins"] * r
    t["f"] += food["fats"] * r
    t["c"] += food["carbs"] * r
    
    # ПОВЕРНУТО ДИЗАЙН ПІДТВЕРДЖЕННЯ СТРАВИ
    res = (f"✅ {food['name']} ({weight}г):\n"
           f"🔥 {round(food['calories']*r)} ккал | 🥩 Б: {round(food['proteins']*r)}г | "
           f"🥑 Ж: {round(food['fats']*r)}г | 🍞 В: {round(food['carbs']*r)}г")
    context.user_data["final_report"].append(res)

async def send_final_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rep = context.user_data["final_report"]
    t = context.user_data["total_kbzhv"]
    
    msg = "\n\n".join(rep)
    if t["cal"] > 0:
        # ПОВЕРНУТО ДИЗАЙН ПІДСУМКУ
        msg += f"\n\n**РАЗОМ:**\n🔥 {round(t['cal'])} ккал | 🥩 Б: {round(t['p'])}г | 🥑 Ж: {round(t['f'])}г | 🍞 В: {round(t['c'])}г"
    
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    return DIARY

if __name__ == "__main__":
    app = ApplicationBuilder().token(os.getenv("TELEGRAM_TOKEN")).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_gender)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
            HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_height)],
            WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_weight)],
            DIARY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_diary)],
            SELECT_FOOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_food_from_list)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    app.add_handler(conv)
    app.run_polling()