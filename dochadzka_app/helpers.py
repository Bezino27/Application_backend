# helpers.py
import httpx

def send_push_notification(token: str, title: str, message: str):
    try:
        response = httpx.post("https://exp.host/--/api/v2/push/send", json={
            "to": token,
            "title": title,
            "body": message,
            "sound": "default",  # alebo "defaultCritical"
            "data": {"type": "chat"}
        })
        response.raise_for_status()
    except Exception as e:
        print("❌ Expo push chyba:", e)