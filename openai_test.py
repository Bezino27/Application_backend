from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

try:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Si pomocník."},
            {"role": "user", "content": "Koľko je 5 + 7?"}
        ],
        temperature=0,
    )
    print("✅ Funguje! Výsledok:", response.choices[0].message.content.strip())
except Exception as e:
    print("❌ Chyba:", e)