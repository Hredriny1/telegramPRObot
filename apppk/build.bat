@echo off
chcp 65001 > nul
echo === Установка зависимостей ===
pip install customtkinter==5.2.2 requests pyinstaller

echo.
echo === Сборка .exe ===
pyinstaller --noconfirm --onefile --windowed --name RedSaveControl app.py

echo.
echo === Готово! Файл: dist\RedSaveControl.exe ===
pause
