import requests
import os

class NordigenAPI:
    BASE = "https://ob.nordigen.com/api/v2"

    def __init__(self):
        self.secret_id = os.getenv("NORDIGEN_SECRET_ID")
        self.secret_key = os.getenv("NORDIGEN_SECRET_KEY")
        self.token = self._get_token()

    def _get_token(self):
        res = requests.post(
            f"{self.BASE}/token/new/",
            json={
                "secret_id": self.secret_id,
                "secret_key": self.secret_key
            }
        )
        try:
            res.raise_for_status()
            return res.json()["access"]
        except Exception as e:
            print("❌ Chyba pri získavaní Nordigen tokenu:")
            print("Status:", res.status_code)
            print("Odpoveď:", res.text)
            raise e

    def create_requisition(self, club_name, redirect_url):
        headers = {"Authorization": f"Bearer {self.token}"}
        res = requests.post(
            f"{self.BASE}/requisitions/",
            headers=headers,
            json={
                "redirect": redirect_url,
                "institution_id": "SK_TATRSKBX",  # neskôr nastaviteľné
                "reference": club_name[:35],  # max 36 znakov
            }
        )
        try:
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print("❌ Chyba pri vytváraní requisition:")
            print("Status:", res.status_code)
            print("Odpoveď:", res.text)
            raise e

    def get_requisition_accounts(self, requisition_id):
        headers = {"Authorization": f"Bearer {self.token}"}
        res = requests.get(
            f"{self.BASE}/requisitions/{requisition_id}/",
            headers=headers
        )
        try:
            res.raise_for_status()
            data = res.json()
            return data.get("accounts", [])
        except Exception as e:
            print("❌ Chyba pri získavaní účtov:")
            print("Status:", res.status_code)
            print("Odpoveď:", res.text)
            raise e