import httpx

def send_push_notification(
    token: str,
    title: str,
    message: str,
    user_id: int = None,
    user_name: str = None,
    data: dict = None  # ← NOVÝ argument
):
    payload = {
        "to": token,
        "title": title,
        "body": message,
        "sound": "sound_post.caf",
        "data": {}
    }

    if user_id is not None and user_name is not None:
        # prioritne chat
        payload["data"] = {
            "type": "chat",
            "user_id": user_id,
            "user_name": user_name
        }
    elif data:
        # ak nie je chat, použi custom data (napr. zápas)
        payload["data"] = data

    try:
        response = httpx.post("https://exp.host/--/api/v2/push/send", json=payload)
        response.raise_for_status()
        return response
    except Exception as e:
        print("❌ Expo push chyba:", e)