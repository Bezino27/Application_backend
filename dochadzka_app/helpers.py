# helpers.py
import httpx

def send_push_notification(token: str, title: str, message: str, user_id: int = None, user_name: str = None):
    payload = {
        "to": token,
        "title": title,
        "body": message,
        "sound": "zvuk.caf",
        "data": {}
    }

    # Pridaj iba ak ide o chat
    if user_id is not None and user_name is not None:
        payload["data"] = {
            "type": "chat",
            "user_id": user_id,
            "user_name": user_name
        }

    try:
        response = httpx.post("https://exp.host/--/api/v2/push/send", json=payload)
        response.raise_for_status()
        return response
    except Exception as e:
        print("❌ Expo push chyba:", e)