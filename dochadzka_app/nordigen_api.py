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
            json={"secret_id": self.secret_id, "secret_key": self.secret_key}
        )
        return res.json()["access"]

    def create_requisition(self, club_name, redirect_url):
        headers = {"Authorization": f"Bearer {self.token}"}
        res = requests.post(
            f"{self.BASE}/requisitions/",
            headers=headers,
            json={
                "redirect": redirect_url,
                "institution_id": "SK_TATRSKBX",  # alebo frontend nech si vyberie banku
                "reference": club_name[:35],  # max 36 znakov
            }
        )
        return res.json()

    def get_requisition_accounts(self, requisition_id):
        headers = {"Authorization": f"Bearer {self.token}"}
        res = requests.get(
            f"{self.BASE}/requisitions/{requisition_id}/",
            headers=headers
        )
        data = res.json()
        return data.get("accounts", [])