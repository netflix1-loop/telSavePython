import asyncio
import os
import sys

from telethon import TelegramClient, events, errors
from telethon.sessions import StringSession
from dotenv import load_dotenv
import qrcode

# Try to import the attribute for animated media.
# Some versions name it "DocumentAttributeAnimation", while others may name it "DocumentAttributeAnimated".
try:
    from telethon.tl.types import DocumentAttributeAnimation, DocumentAttributeVideo
except ImportError:
    from telethon.tl.types import DocumentAttributeAnimated as DocumentAttributeAnimation, DocumentAttributeVideo

# Load credentials from the .env file
load_dotenv()
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')

if not api_id or not api_hash:
    print("Please ensure that API_ID and API_HASH are set in your .env file.")
    sys.exit(1)

# Define session file and load existing session if available
SESSION_FILE = "session.json"
session_str = None
if os.path.exists(SESSION_FILE):
    with open(SESSION_FILE, "r") as f:
        session_str = f.read().strip()

# Initialize the Telegram client with a StringSession
client = TelegramClient(StringSession(session_str), int(api_id), api_hash)

async def otp_login():
    """
    Performs login via OTP (phone number and code).
    """
    print("Starting OTP login...")
    await client.start()  # Prompts for phone number and OTP code.
    new_session = client.session.save()
    with open(SESSION_FILE, "w") as f:
        f.write(new_session)
    print("Logged in with OTP. Session saved to", SESSION_FILE)

async def qr_login():
    """
    Performs QR code login. Displays an ASCII QR code in terminal.
    If two-step verification is enabled, it prompts for a password.
    """
    if await client.is_user_authorized():
        print("Session is already authorized. No need for QR login.")
        return

    while True:
        print("Starting QR code login session...")
        try:
            qr = await client.qr_login()
        except Exception as e:
            print("Failed to initiate QR login:", e)
            return

        # Generate and display the ASCII QR code in the terminal.
        qr_url = qr.url
        qr_obj = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=1,
            border=1,
        )
        qr_obj.add_data(qr_url)
        qr_obj.make(fit=True)
        matrix = qr_obj.get_matrix()

        qr_ascii = ""
        for row in matrix:
            line = "".join("██" if col else "  " for col in row)
            qr_ascii += line + "\n"
        print(qr_ascii)
        print("Please scan the above QR code with your Telegram app.")
        
        try:
            await qr.wait()
            print("QR code login successful!")
            new_session = client.session.save()
            with open(SESSION_FILE, "w") as f:
                f.write(new_session)
            print("Session saved to", SESSION_FILE)
            break
            
        except Exception as e:
            error_message = str(e)
            print("QR code login attempt failed with error:", error_message)
            if "Two-steps verification" in error_message and "password is required" in error_message:
                print("Your account has two-step verification enabled. A password is required to complete login.")
                pw = input("Please enter your password: ")
                try:
                    await client.sign_in(password=pw)
                    print("Logged in successfully with two-step verification!")
                    new_session = client.session.save()
                    with open(SESSION_FILE, "w") as f:
                        f.write(new_session)
                    print("Session saved to", SESSION_FILE)
                    break
                except Exception as sign_e:
                    print("Failed to sign in with password:", sign_e)
                    break
            else:
                break

# Event handler to download incoming media with a custom file name.
@client.on(events.NewMessage)
async def new_media_handler(event):
    if event.message and event.message.media:
        # For messages in groups or private chats, use the sender's ID if available;
        # Otherwise, fallback to the chat ID (common with anonymous channel posts).
        sender_id = event.message.sender_id if event.message.sender_id else event.chat_id
        message_id = event.message.id

        # Determine media type (gif or video) if possible.
        media_type = None
        if event.message.document:
            for attr in event.message.document.attributes:
                if isinstance(attr, DocumentAttributeAnimation):
                    media_type = "gif"
                    break  # Prioritize GIF detection.
                elif isinstance(attr, DocumentAttributeVideo):
                    media_type = "video"
                    # Continue in case an animation attribute is present.

        # Build the base filename using the sender's (or chat's) ID and the message ID.
        base_name = f"{sender_id}-{message_id}"
        if media_type == "gif":
            file_name = base_name + "-gif"
        elif media_type == "video":
            file_name = base_name + "-video"
        else:
            file_name = base_name

        file_path = os.path.join("downloads", file_name)
        saved_file = await event.message.download_media(file=file_path)
        print(f"New media downloaded to: {saved_file}")

async def main():
    print("Choose login method:")
    print("1. OTP (via phone number and code)")
    print("2. QR code login")
    
    method = input("Enter your choice (1 or 2): ").strip()

    # Connect the client.
    await client.connect()
    
    if method == "1":
        await otp_login()
    elif method == "2":
        await qr_login()
    else:
        print("Invalid choice. Exiting.")
        await client.disconnect()
        sys.exit(1)
    
    os.makedirs("downloads", exist_ok=True)
    print("Login successful!")
    print("Media downloader is active. Listening for new incoming media...")
    
    # Keep the client running to listen for incoming events.
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
