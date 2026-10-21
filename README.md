# Boyirov Buyurtma Bot — Railway

Telegram lead bot: sayt, Telegram bot, mobil ilova arizalarini qabul qiladi.

## Railway ga joylash (qadam-baqadam)

1. [railway.app](https://railway.app) ga kiring, **New Project** → **Deploy from local** yoki GitHub.
2. Shu zipni ochib, loyihani yuklang (`bot.py`, `Procfile`, `requirements.txt` bilan).
3. **Variables** bo‘limiga qo‘shing:
   - `TELEGRAM_BOT_TOKEN` = BotFather bergan token
4. Deploy bosing.
5. Logda `Bot ishga tushdi (polling).` ko‘rinsa — tayyor.
6. Telegramda `@BoyirovOrderBot` ni ochib **/start** bosing.
7. O‘z akkauntingiz `@Boyirov_dev` dan **/start** bosing — arizalar shu yerga keladi.

## Muhim

- Tokenni hech qachon kodga yozmang — faqat Railway Variables.
- SQLite fayl konteyner qayta ishga tushganda tozalanishi mumkin.
- Faqat bitta instance ishlasin (ikkita deploy birga polling qilsa xato beradi).

## Lokal ishga tushirish

```bash
export TELEGRAM_BOT_TOKEN="tokeningiz"
python bot.py
```

## Test

```bash
python bot.py --self-test
```
