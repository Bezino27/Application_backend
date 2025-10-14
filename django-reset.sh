#!/bin/bash
echo "🧹 Resetujem Django backend..."

# 💾 Ak si v inom priečinku, uprav túto cestu
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$PROJECT_DIR"

# 🚮 1. Vymažeme staré virtuálne prostredie, ak existuje
if [ -d ".venv" ]; then
  echo "🗑️  Odstraňujem .venv..."
  rm -rf .venv
fi

# 🐍 2. Vytvoríme nové prostredie
echo "🐍 Vytváram nové virtuálne prostredie..."
python3 -m venv .venv
source .venv/bin/activate

# 📦 3. Aktualizujeme pip a nainštalujeme všetky knižnice
echo "📦 Inštalujem balíčky z requirements.txt..."
pip install --upgrade pip
pip install -r requirements.txt

# ⚙️ 4. Spustíme migrácie
echo "🧱 Spúšťam migrácie..."
python manage.py migrate

# 📂 5. (Voliteľne) vytvoríme superusera, ak ešte neexistuje
echo "👤 Skontrolujem superusera..."
python manage.py shell -c "from django.contrib.auth import get_user_model; User=get_user_model(); \
  print('✅ Superuser OK') if User.objects.filter(is_superuser=True).exists() else print('⚠️ Žiadny superuser, vytvor ho ručne.')"

# 🚀 6. (Voliteľne) spustíme server
read -p "Chceš spustiť Django server? (y/n): " start_server
if [[ "$start_server" == "y" || "$start_server" == "Y" ]]; then
  echo "🚀 Spúšťam Django server..."
  python manage.py runserver 0.0.0.0:8000
else
  echo "✅ Reset hotový! Aktivuj prostredie: source .venv/bin/activate"
fi
