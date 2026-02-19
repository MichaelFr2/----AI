#!/usr/bin/env python3
"""Проверка подключения к Google Таблице. Запуск из корня проекта: python scripts/check_google_sheets.py"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

def main():
    print("GOOGLE_SHEET_ID:", getattr(config, "GOOGLE_SHEET_ID", ""))
    print("GOOGLE_CREDENTIALS_PATH:", getattr(config, "GOOGLE_CREDENTIALS_PATH", ""))
    path = os.path.abspath(config.GOOGLE_CREDENTIALS_PATH)
    print("Файл ключа существует:", os.path.exists(path))
    if not os.path.exists(path):
        print("→ Создайте ключ в Google Cloud Console и положите JSON в проект или укажите GOOGLE_CREDENTIALS_PATH в .env")
        return 1
    try:
        import gspread
        gc = gspread.service_account(filename=path)
        sh = gc.open_by_key(config.GOOGLE_SHEET_ID)
        print("Таблица открыта:", sh.title)
        # Показать email, с которым нужно открыть доступ к таблице
        with open(path) as f:
            import json
            data = json.load(f)
            email = data.get("client_email", "?")
        print("Таблицу нужно открыть на доступ для email (Редактор):", email)
        # Попробовать добавить лист и строку
        ws = sh.worksheet("Judge") if "Judge" in [s.title for s in sh.worksheets()] else sh.add_worksheet("Judge", rows=100, cols=10)
        ws.append_row(["Проверка", "OK", "скрипт check_google_sheets"], value_input_option="USER_ENTERED")
        print("Запись в лист Judge: OK")
        return 0
    except Exception as e:
        print("Ошибка:", e)
        if "403" in str(e) or "Permission" in str(e).lower() or "Access" in str(e):
            print("→ Откройте таблицу в браузере → Настроить доступ → добавьте email из JSON с правом Редактор")
        return 1

if __name__ == "__main__":
    sys.exit(main())
