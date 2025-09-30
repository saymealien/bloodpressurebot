from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from datetime import datetime, time
from zoneinfo import ZoneInfo, available_timezones
import asyncio
import nest_asyncio
import sqlite3
import json
import pandas as pd
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import difflib

nest_asyncio.apply()

# =======================
# States
# =======================
BP, PULSE, COMMENT = range(3)
EXPORT_CHOOSE = range(1)
SET_TIMEZONE, SET_REMINDERS = range(2, 4)
DELETE_ENTRY = range(4, 5)

DB_FILE = "bp_diary.db"

# =======================
# Main menu keyboard
# =======================
MAIN_MENU = ReplyKeyboardMarkup(
    [["Add", "Show"], ["Export", "Delete"], ["Status", "Settings"]],
    resize_keyboard=True
)

EXPORT_MENU = ReplyKeyboardMarkup([
    ["CSV", "XLSX", "PDF"], ["Cancel"]
], resize_keyboard=True, one_time_keyboard=True)

SETTINGS_MENU = ReplyKeyboardMarkup([
    ["Set Timezone", "Set Reminders"],
    ["Back to Main"]
], resize_keyboard=True)

TIMEZONE_MENU = ReplyKeyboardMarkup([
    ["New York", "London", "Berlin", "Tokyo"],
    ["Moscow", "Sydney", "Los Angeles", "Other"],
    ["Cancel"]
], resize_keyboard=True)

REMINDER_MENU = ReplyKeyboardMarkup([
    ["07:00 19:00", "08:00 20:00", "09:00 21:00"],
    ["Custom Times", "Cancel"]
], resize_keyboard=True)

# =======================
# Database functions
# =======================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS bp_diary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            datetime TEXT,
            bp TEXT,
            pulse TEXT,
            comment TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            timezone TEXT DEFAULT 'UTC',
            reminders TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_entry_to_db(chat_id, bp, pulse, comment):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO bp_diary (chat_id, datetime, bp, pulse, comment) VALUES (?, ?, ?, ?, ?)",
              (chat_id, datetime.now().strftime("%Y-%m-%d %H:%M"), bp, pulse, comment))
    conn.commit()
    conn.close()

def get_entries_from_db(chat_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, datetime, bp, pulse, comment FROM bp_diary WHERE chat_id=? ORDER BY id DESC", (chat_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def delete_entry(entry_id, user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM bp_diary WHERE id=? AND chat_id=?", (entry_id, user_id))
    deleted = c.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def set_user_timezone(user_id, timezone):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO user_settings (user_id, timezone, reminders) VALUES (?, ?, COALESCE((SELECT reminders FROM user_settings WHERE user_id=?), '[]'))",
              (user_id, timezone, user_id))
    conn.commit()
    conn.close()

def get_user_timezone(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT timezone FROM user_settings WHERE user_id=?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else "UTC"

def set_user_reminders(user_id, reminders):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    reminders_json = json.dumps(reminders)
    c.execute("INSERT OR REPLACE INTO user_settings (user_id, timezone, reminders) VALUES (?, COALESCE((SELECT timezone FROM user_settings WHERE user_id=?), 'UTC'), ?)",
              (user_id, user_id, reminders_json))
    conn.commit()
    conn.close()

def get_user_reminders(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT reminders FROM user_settings WHERE user_id=?", (user_id,))
    result = c.fetchone()
    conn.close()
    if result and result[0]:
        try:
            return json.loads(result[0])
        except json.JSONDecodeError:
            return []
    return []

def get_all_users_with_reminders():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id, timezone, reminders FROM user_settings WHERE reminders IS NOT NULL AND reminders != '[]'")
    results = c.fetchall()
    conn.close()
    return results

# =======================
# Bot Handlers
# =======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hi! I'm your Blood Pressure Diary Bot.\nUse the buttons or commands to interact.",
        reply_markup=MAIN_MENU
    )

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ Blood Pressure Diary Bot\nTrack BP, pulse, notes, and reminders.\nAll data is private.",
        reply_markup=MAIN_MENU
    )

# -----------------------
# Settings Menu
# -----------------------
async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚙️ Settings Menu:\n• Set Timezone - Configure your timezone\n• Set Reminders - Set two daily reminders",
        reply_markup=SETTINGS_MENU
    )

# -----------------------
# Timezone Setup Conversation
# -----------------------
async def set_timezone_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌍 Choose your timezone or type 'Other' to enter a custom one:",
        reply_markup=TIMEZONE_MENU
    )
    return SET_TIMEZONE

async def timezone_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    user_id = update.message.from_user.id
    
    if user_input == "Cancel":
        await update.message.reply_text("❌ Timezone setup cancelled.", reply_markup=MAIN_MENU)
        return ConversationHandler.END
    
    # Map common city names to timezone names
    timezone_map = {
        "New York": "America/New_York",
        "London": "Europe/London",
        "Berlin": "Europe/Berlin",
        "Tokyo": "Asia/Tokyo",
        "Moscow": "Europe/Moscow",
        "Sydney": "Australia/Sydney",
        "Los Angeles": "America/Los_Angeles"
    }
    
    if user_input in timezone_map:
        timezone_name = timezone_map[user_input]
        set_user_timezone(user_id, timezone_name)
        await update.message.reply_text(
            f"✅ Timezone set to {user_input} ({timezone_name})",
            reply_markup=MAIN_MENU
        )
        return ConversationHandler.END
    
    elif user_input == "Other":
        await update.message.reply_text(
            "🌍 Please enter your timezone (e.g., Europe/Paris, Asia/Singapore):\n\nYou can find your timezone at: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones",
            reply_markup=ReplyKeyboardMarkup([["Cancel"]], resize_keyboard=True)
        )
        return SET_TIMEZONE
    
    else:
        # Check if it's a valid timezone
        if user_input in available_timezones():
            set_user_timezone(user_id, user_input)
            await update.message.reply_text(
                f"✅ Timezone set to {user_input}",
                reply_markup=MAIN_MENU
            )
            return ConversationHandler.END
        else:
            matches = difflib.get_close_matches(user_input, available_timezones(), n=5)
            if matches:
                await update.message.reply_text(
                    f"⚠️ Timezone not found. Did you mean?\n- " + "\n- ".join(matches),
                    reply_markup=TIMEZONE_MENU
                )
            else:
                await update.message.reply_text(
                    "⚠️ Timezone not recognized. Please choose from the menu or enter a valid timezone.",
                    reply_markup=TIMEZONE_MENU
                )
            return SET_TIMEZONE

# -----------------------
# Reminders Setup Conversation
# -----------------------
async def set_reminders_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⏰ Set two daily reminders for blood pressure measurement:\n\nChoose from common times or select 'Custom Times' to set your own:",
        reply_markup=REMINDER_MENU
    )
    return SET_REMINDERS

async def reminders_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    user_id = update.message.from_user.id
    
    if user_input == "Cancel":
        await update.message.reply_text("❌ Reminder setup cancelled.", reply_markup=MAIN_MENU)
        return ConversationHandler.END
    
    if user_input == "Custom Times":
        await update.message.reply_text(
            "⏰ Please enter two reminder times in 24-hour format (HH:MM), separated by space:\n\nExample: 08:00 20:00 for 8 AM and 8 PM",
            reply_markup=ReplyKeyboardMarkup([["Cancel"]], resize_keyboard=True)
        )
        return SET_REMINDERS
    
    # Handle predefined times
    if " " in user_input:
        times = user_input.split()
        if len(times) == 2:
            return await process_reminder_times(update, context, times)
    
    # If we get here, ask for proper input
    await update.message.reply_text(
        "⚠️ Please choose from the menu or enter two times in HH:MM format separated by space.",
        reply_markup=REMINDER_MENU
    )
    return SET_REMINDERS

async def process_reminder_times(update: Update, context: ContextTypes.DEFAULT_TYPE, times):
    user_id = update.message.from_user.id
    
    # Validate time format
    valid_times = []
    for t in times:
        try:
            # Validate HH:MM format
            if len(t) == 5 and t[2] == ':':
                hours, minutes = map(int, t.split(':'))
                if 0 <= hours <= 23 and 0 <= minutes <= 59:
                    valid_times.append(t)
                else:
                    await update.message.reply_text(
                        f"⚠️ Invalid time: {t}. Hours must be 0-23, minutes 0-59.",
                        reply_markup=REMINDER_MENU
                    )
                    return SET_REMINDERS
            else:
                await update.message.reply_text(
                    f"⚠️ Invalid format: {t}. Please use HH:MM format.",
                    reply_markup=REMINDER_MENU
                )
                return SET_REMINDERS
        except ValueError:
            await update.message.reply_text(
                f"⚠️ Invalid time: {t}. Please use numbers in HH:MM format.",
                reply_markup=REMINDER_MENU
            )
            return SET_REMINDERS
    
    if len(valid_times) == 2:
        set_user_reminders(user_id, valid_times)
        await update.message.reply_text(
            f"✅ Reminders set for {valid_times[0]} and {valid_times[1]} daily!",
            reply_markup=MAIN_MENU
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "⚠️ Please provide exactly two valid times.",
            reply_markup=REMINDER_MENU
        )
        return SET_REMINDERS

# -----------------------
# Delete Conversation
# -----------------------
async def delete_entry_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    entries = get_entries_from_db(user_id)
    
    if not entries:
        await update.message.reply_text("🔭 No entries to delete.", reply_markup=MAIN_MENU)
        return ConversationHandler.END
    
    # Store entries in context for later reference
    context.user_data['delete_entries'] = entries
    
    # Create a numbered list for selection
    delete_keyboard = []
    row = []
    for i, (eid, dt, bp, pulse, comment) in enumerate(entries, 1):
        row.append(str(i))
        if i % 5 == 0:  # 5 buttons per row
            delete_keyboard.append(row)
            row = []
    if row:  # Add remaining buttons
        delete_keyboard.append(row)
    delete_keyboard.append(["Cancel"])
    
    delete_menu = ReplyKeyboardMarkup(delete_keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    # Show entries with numbers
    msg = "🗑️ Select entry to delete:\n\n"
    for i, (eid, dt, bp, pulse, comment) in enumerate(entries, 1):
        msg += f"{i}. {dt} - BP: {bp} | Pulse: {pulse}\n"
    
    await update.message.reply_text(msg, reply_markup=delete_menu)
    return DELETE_ENTRY

async def delete_entry_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    user_id = update.message.from_user.id
    
    if user_input == "Cancel":
        await update.message.reply_text("❌ Delete cancelled.", reply_markup=MAIN_MENU)
        return ConversationHandler.END
    
    # Validate that input is a number
    if not user_input.isdigit():
        await update.message.reply_text("⚠️ Please select a number from the list.", reply_markup=MAIN_MENU)
        return ConversationHandler.END
    
    entry_number = int(user_input)
    entries = context.user_data.get('delete_entries', [])
    
    # Validate entry number range
    if entry_number < 1 or entry_number > len(entries):
        await update.message.reply_text(f"⚠️ Please select a number between 1 and {len(entries)}.", reply_markup=MAIN_MENU)
        return ConversationHandler.END
    
    # Get the actual entry ID from the stored entries
    selected_entry = entries[entry_number - 1]
    entry_id = selected_entry[0]  # First element is the ID
    
    # Delete the entry
    if delete_entry(entry_id, user_id):
        dt, bp, pulse, comment = selected_entry[1], selected_entry[2], selected_entry[3], selected_entry[4]
        await update.message.reply_text(
            f"✅ Entry deleted:\n{dt}\nBP: {bp} | Pulse: {pulse}\nNote: {comment}",
            reply_markup=MAIN_MENU
        )
    else:
        await update.message.reply_text("❌ Error deleting entry.", reply_markup=MAIN_MENU)
    
    return ConversationHandler.END

# -----------------------
# Add conversation
# -----------------------
async def add_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Please enter your blood pressure (e.g., 120/80):", reply_markup=MAIN_MENU)
    return BP

async def bp_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['bp'] = update.message.text
    await update.message.reply_text("Enter your pulse (e.g., 72):", reply_markup=MAIN_MENU)
    return PULSE

async def pulse_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['pulse'] = update.message.text
    await update.message.reply_text("Add a short comment:", reply_markup=MAIN_MENU)
    return COMMENT

async def comment_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    bp = context.user_data['bp']
    pulse = context.user_data['pulse']
    comment = update.message.text
    add_entry_to_db(user_id, bp, pulse, comment)
    await update.message.reply_text(f"✅ Entry saved:\nBP: {bp} | Pulse: {pulse}\nNote: {comment}", reply_markup=MAIN_MENU)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Action cancelled.", reply_markup=MAIN_MENU)
    return ConversationHandler.END

# -----------------------
# Show entries
# -----------------------
async def show_entries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    entries = get_entries_from_db(user_id)
    if not entries:
        await update.message.reply_text("🔭 No entries yet.", reply_markup=MAIN_MENU)
        return
    msg = "📖 Your diary:\n\n"
    for i, (eid, dt, bp, pulse, comment) in enumerate(entries, 1):
        msg += f"{i}. {dt}\nBP: {bp} | Pulse: {pulse}\nNote: {comment}\n\n"
    await update.message.reply_text(msg, reply_markup=MAIN_MENU)

# -----------------------
# Status
# -----------------------
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    tz = get_user_timezone(user_id)
    reminders = get_user_reminders(user_id)
    
    msg = f"🌍 Timezone: {tz}\n"
    if reminders:
        msg += f"⏰ Daily reminders: {reminders[0]} and {reminders[1]}"
    else:
        msg += "⏰ No reminders set. Use Settings to configure."
    
    # Add some stats
    entries = get_entries_from_db(user_id)
    if entries:
        msg += f"\n📊 Total entries: {len(entries)}"
        # Get today's entries
        today = datetime.now().strftime("%Y-%m-%d")
        today_entries = [e for e in entries if e[1].startswith(today)]
        msg += f"\n📅 Today's entries: {len(today_entries)}"
    
    await update.message.reply_text(msg, reply_markup=MAIN_MENU)

# -----------------------
# Reminders System
# -----------------------
async def send_reminder(user_id: int, app: Application):
    try:
        await app.bot.send_message(
            user_id, 
            "⏰ Time to measure your blood pressure! 💓\n\nUse the 'Add' button to record your measurement."
        )
    except Exception as e:
        print(f"Failed reminder to {user_id}: {e}")

last_sent = {}

async def schedule_reminders(app: Application):
    while True:
        users = get_all_users_with_reminders()
        current_utc = datetime.utcnow()
        
        for user_id, tz_str, reminders_json in users:
            try:
                tz = ZoneInfo(tz_str) if tz_str else ZoneInfo("UTC")
                user_time = current_utc.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
                
                if user_id not in last_sent:
                    last_sent[user_id] = {}
                
                reminders = json.loads(reminders_json)
                
                for reminder_time in reminders:
                    # Check if it's time to send reminder
                    h, m = map(int, reminder_time.split(':'))
                    target_time = user_time.replace(hour=h, minute=m, second=0, microsecond=0)
                    
                    # Check if current time is within 1 minute of target time
                    time_diff = (user_time - target_time).total_seconds()
                    if abs(time_diff) < 60:  # Within 1 minute
                        today_str = user_time.date().isoformat()
                        
                        if last_sent[user_id].get(reminder_time) != today_str:
                            await send_reminder(user_id, app)
                            last_sent[user_id][reminder_time] = today_str
                            print(f"Sent reminder to {user_id} at {reminder_time}")
                
            except Exception as e:
                print(f"Error processing reminders for user {user_id}: {e}")
        
        await asyncio.sleep(30)  # Check every 30 seconds

# -----------------------
# Export conversation
# -----------------------
async def export_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📤 Choose format to export:\n\n"
        "⚠️ Note: PDF export may not display non-English/Latin characters correctly "
        "(like Cyrillic, Arabic, Chinese, etc.). For these languages, please use CSV or XLSX format instead.",
        reply_markup=EXPORT_MENU
    )
    return EXPORT_CHOOSE

async def export_format_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    fmt = update.message.text.strip().lower()
    
    # Handle cancel
    if fmt == "cancel":
        await update.message.reply_text("❌ Export cancelled.", reply_markup=MAIN_MENU)
        return ConversationHandler.END
        
    if fmt not in ["csv", "xlsx", "pdf"]:
        await update.message.reply_text("❌ Invalid option. Export cancelled.", reply_markup=MAIN_MENU)
        return ConversationHandler.END

    chat_id = update.message.chat_id
    entries = get_entries_from_db(chat_id)
    if not entries:
        await update.message.reply_text("📭 No entries to export.", reply_markup=MAIN_MENU)
        return ConversationHandler.END

    try:
        # Fix: Create DataFrame with correct columns (skip the ID column)
        df = pd.DataFrame(entries, columns=["ID", "DateTime", "Blood Pressure", "Pulse", "Comment"])
        # Remove the ID column for export
        df = df.drop(columns=["ID"])
        
        buffer = BytesIO()
        if fmt == "xlsx":
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='BP Diary')
            buffer.seek(0)
            filename = "blood_pressure_diary.xlsx"
            caption = "📊 Excel format"
        elif fmt == "pdf":
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            elements = [Paragraph("Blood Pressure Diary", styles["Heading1"])]
            
            # Prepare data for PDF table
            data = [df.columns.tolist()] + df.values.tolist()
            table = Table(data, repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.lightblue),
                ('TEXTCOLOR',(0,0),(-1,0),colors.black),
                ('ALIGN',(0,0),(-1,-1),'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,0), 12),
                ('FONTSIZE', (0,1), (-1,-1), 10),
                ('BOTTOMPADDING', (0,0), (-1,0), 12),
                ('BACKGROUND', (0,1), (-1,-1), colors.beige),
                ('GRID', (0,0), (-1,-1), 1, colors.black),
            ]))
            elements.append(table)
            doc.build(elements)
            buffer.seek(0)
            filename = "blood_pressure_diary.pdf"
            caption = "📄 PDF format"
        else:  # CSV
            df.to_csv(buffer, index=False, encoding='utf-8')
            buffer.seek(0)
            filename = "blood_pressure_diary.csv"
            caption = "📊 CSV format"

        await update.message.reply_document(
            document=buffer, 
            filename=filename, 
            caption=caption, 
            reply_markup=MAIN_MENU
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error during export: {str(e)}", reply_markup=MAIN_MENU)
        print(f"Export error: {e}")
    
    return ConversationHandler.END

async def export_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Export cancelled.", reply_markup=MAIN_MENU)
    return ConversationHandler.END

# -----------------------
# Main menu button handler
# -----------------------
async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "Add":
        # Start the add conversation
        context.user_data.clear()
        await update.message.reply_text("Please enter your blood pressure (e.g., 120/80):", reply_markup=MAIN_MENU)
        return BP
    elif text == "Show":
        await show_entries(update, context)
    elif text == "Export":
        await export_start(update, context)
        return EXPORT_CHOOSE
    elif text == "Delete":
        await delete_entry_start(update, context)
        return DELETE_ENTRY
    elif text == "Status":
        await status(update, context)
    elif text == "Settings":
        await settings_menu(update, context)
    elif text == "Back to Main":
        await update.message.reply_text("↩️ Back to main menu", reply_markup=MAIN_MENU)
    
    return ConversationHandler.END

# =======================
# Main
# =======================
if __name__ == "__main__":
    init_db()
    # REPLACE THIS WITH YOUR ACTUAL BOT TOKEN FROM BOTFATHER
    TOKEN = "myau"  # Replace with your actual token
    app = Application.builder().token(TOKEN).build()

    # /add conversation
    add_conv = ConversationHandler(
        entry_points=[
            CommandHandler("add", add_entry),
            MessageHandler(filters.Regex("^(Add)$"), add_entry)
        ],
        states={
            BP: [MessageHandler(filters.TEXT & ~filters.COMMAND, bp_received)],
            PULSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, pulse_received)],
            COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, comment_received)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )
    app.add_handler(add_conv)

    # Timezone setup conversation
    timezone_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^(Set Timezone)$"), set_timezone_start)
        ],
        states={
            SET_TIMEZONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, timezone_received)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )
    app.add_handler(timezone_conv)

    # Reminders setup conversation
    reminders_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^(Set Reminders)$"), set_reminders_start)
        ],
        states={
            SET_REMINDERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, reminders_received)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )
    app.add_handler(reminders_conv)

    # Delete conversation
    delete_conv = ConversationHandler(
        entry_points=[
            CommandHandler("delete", delete_entry_start),
            MessageHandler(filters.Regex("^(Delete)$"), delete_entry_start)
        ],
        states={
            DELETE_ENTRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_entry_selected)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )
    app.add_handler(delete_conv)

    # /export conversation
    export_conv = ConversationHandler(
        entry_points=[
            CommandHandler("export", export_start),
            MessageHandler(filters.Regex("^(Export)$"), export_start)
        ],
        states={
            EXPORT_CHOOSE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, export_format_chosen)
            ]
        },
        fallbacks=[
            MessageHandler(filters.Regex("^(Cancel|cancel)$"), export_cancel),
            CommandHandler("cancel", export_cancel)
        ],
        allow_reentry=True
    )
    app.add_handler(export_conv)

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("about", about))
    app.add_handler(CommandHandler("show", show_entries))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("timezone", set_timezone_start))
    app.add_handler(CommandHandler("remind", set_reminders_start))

    # Main menu buttons
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu_handler))

    # Start reminders
    asyncio.get_event_loop().create_task(schedule_reminders(app))

    # Run bot
    print("Bot is starting...")
    app.run_polling()