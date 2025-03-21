@echo off
echo Creating GitHub repository setup...

echo # Telegram Chatbot with Gemini API > README.md
echo. >> README.md
echo A Telegram chatbot using Telethon and Google's Gemini API to provide AI-assisted responses. >> README.md
echo. >> README.md
echo ## Features >> README.md
echo - Per-chat memory management >> README.md
echo - Chat activation/deactivation >> README.md
echo - Gemini API integration >> README.md

git init
git add .
git commit -m "Initial commit: Telegram chatbot with Gemini integration"
git branch -M main
git remote add origin https://github.com/Antivirus3052/chatbot.git
git push -u origin main

echo.
echo GitHub repository setup completed successfully!
echo Repository URL: https://github.com/Antivirus3052/chatbot
pause