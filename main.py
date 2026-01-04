import io
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from supabase import create_client

# --- 1. SETUP YOUR KEYS ---
SUPABASE_URL = "YOUR_SUPABASE_URL"
SUPABASE_KEY = "YOUR_SERVICE_ROLE_KEY" # Use the secret 'service_role' key
TELEGRAM_TOKEN = "YOUR_BOT_TOKEN_FROM_BOTFATHER"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

async def handle_everything(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id

    # --- SCENARIO A: LINKING THE SHOP ---
    if update.message.text:
        input_text = update.message.text.upper().strip()
        
        # Check if the code exists in our 'shops' table
        check = supabase.table("shops").update({"chat_id": chat_id}).eq("link_code", input_text).execute()
        
        if check.data:
            shop_name = check.data[0]['name']
            await update.message.reply_text(f"✅ Welcome, {shop_name}! Your bot is now linked. Start sending me product photos!")
        else:
            await update.message.reply_text("❌ Code not found. Please send a valid Link Code (e.g., RAJU1).")
        return

    # --- SCENARIO B: UPLOADING PHOTOS ---
    if update.message.photo:
        # Find which shop this person belongs to
        shop_query = supabase.table("shops").select("*").eq("chat_id", chat_id).execute()
        
        if not shop_query.data:
            await update.message.reply_text("⚠️ Please link your shop first by sending your Code.")
            return

        shop = shop_query.data[0]
        
        # Get the highest quality photo (Telegram sends multiple sizes)
        photo_file = await update.message.photo[-1].get_file()
        
        # 10MB Limit Check
        if photo_file.file_size > 10 * 1024 * 1024:
            await update.message.reply_text("📁 File too big! Please keep it under 10MB.")
            return

        msg = await update.message.reply_text("🎨 Applying watermark and uploading...")

        # Download photo into memory
        photo_bytes = await photo_file.download_as_bytearray()
        image = Image.open(io.BytesIO(photo_bytes))

        # Watermarking Logic (Simple version)
        draw = ImageDraw.Draw(image)
        watermark = f"{shop['name']} | {datetime.now().strftime('%d %b %Y')}"
        # Draw text at bottom right (approximate)
        draw.text((20, image.height - 60), watermark, fill=(255, 255, 255))

        # Compress to JPEG (keeps quality high but file size low)
        output = io.BytesIO()
        image.convert("RGB").save(output, format="JPEG", quality=75)
        output.seek(0)

        # Upload to Supabase Storage
        file_path = f"{shop['slug']}/{datetime.now().timestamp()}.jpg"
        supabase.storage.from_("shop-images").upload(file_path, output.read(), {"content-type": "image/jpeg"})

        # Get Public URL and Save to 'products' table
        image_url = supabase.storage.from_("shop-images").get_public_url(file_path)
        supabase.table("products").insert({"shop_id": shop['id'], "image_url": image_url}).execute()

        await msg.edit_text(f"🚀 Photo is LIVE on your website!")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, handle_everything))
    print("Bot is running... Go to Telegram and type RAJU1")
    app.run_polling()
