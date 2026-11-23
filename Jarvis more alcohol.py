import time
import pyautogui
import winsound
import pyperclip
import difflib
import os
import webbrowser
import requests
import ctypes
import json
import queue
import sounddevice as sd
import urllib.parse
from vosk import Model, KaldiRecognizer
from pycaw.pycaw import AudioUtilities
speakers = AudioUtilities.GetSpeakers()
volume = speakers.EndpointVolume
TG_TOKEN = os.getenv("TG_TOKEN", "9107792977:AAHXrtbFJB43iac5rw8otQVUm3Zbl8kDP5s")
TG_CHAT_ID =1350250884
SITES = {
    "ютуб": "https://youtube.com",
    "гугл": "https://google.com",
    "лайф бол": "https://liveball.sx",
    "википедия": "https://wikipedia.org",
    "яндекс": "https://yandex.ru",
    "тик ток": "https://www.tiktok.com",
    "твиттер": "https://twitter.com",
    "инстаграм": "https://www.instagram.com",
    "фейсбук": "https://www.facebook.com",
    "вконтакте": "https://vk.com",
    "гитхаб": "https://github.com",
    "рик и морти": "https://rick-i-morty.club",
    "платонус": "https://platonus.kazatu.kz",
}
APPS = {
    "блокнот": "notepad",
    "калькулятор": "calc",
    "тим": r"C:\Program Files (x86)\Steam\steam.exe",
    "телеграмм": r"C:\Users\sulta\AppData\Roaming\Telegram Desktop\Telegram.exe",
    "диск": r"C:\Users\sulta\AppData\Local\Discord\Discord.exe",
    "майн": r"C:\Users\sulta\AppData\Roaming\.minecraft\TLauncher.exe",
    "игра": r"C:\Riot Games\Riot Client\RiotClientServices.exe",
    "фейсит": r"C:\Program Files\Faceit\Faceit.exe",
    "ватсап": r"C:\Users\sulta\AppData\Roaming\WhatsApp\WhatsApp.exe",
}
UNITS = {"ноль": 0, "один": 1, "два": 2, "три": 3, "четыре": 4, "пять": 5,
         "шесть": 6, "семь": 7, "восемь": 8, "девять": 9, "десять": 10,
         "одиннадцать": 11, "двенадцать": 12, "тринадцать": 13,
         "четырнадцать": 14, "пятнадцать": 15, "шестнадцать": 16,
         "семнадцать": 17, "восемнадцать": 18, "девятнадцать": 19}
TENS = {"двадцать": 20, "тридцать": 30, "сорок": 40, "пятьдесят": 50,
        "шестьдесят": 60, "семьдесят": 70, "восемьдесят": 80,
        "девяносто": 90, "сто": 100}

pending_shutdown = False
mic_on = True
media_paused = False  
model = Model("vosk-model-small-ru-0.22")
rec = KaldiRecognizer(model, 16000)
audio_queue = queue.Queue()

def ask_ai(question):
    key = os.getenv("GROQ_API_KEY")
    if not key:
        return "Ключ ИИ не задан"
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": "qwen/qwen3.8-27b",
                "max_tokens": 300,
                "messages": [
                    {"role": "system", "content": "Отвечай по-русски, коротко, 1-3 предложения. Ты голосовой помощник."},
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": "Ответь на вопрос, как голосовой помощник Jarvis."}
                ],
            },
            timeout=20,
        )
        data = r.json()
        if "choices" not in data:
            return f"Ответ сервера: {data}"
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Ошибка: {e}"

def audio_callback(indata, frames, time, status):
    audio_queue.put(bytes(indata))

def change_volume(delta):
    current = volume.GetMasterVolumeLevelScalar()
    new = max(0.0, min(1.0, current + delta))
    volume.SetMasterVolumeLevelScalar(new, None)
    return round(new * 100)

def beep_on():
    winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS)

def beep_off():
    winsound.PlaySound("SystemHand", winsound.SND_ALIAS)

def media_play_pause():
    VK_MEDIA_PLAY_PAUSE = 0xB3
    ctypes.windll.user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, 0, 0)
    ctypes.windll.user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, 2, 0)

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        r = requests.post(url, data={"chat_id": TG_CHAT_ID, "text": text}, timeout=10)
        return "Сообщение отправлено" if r.ok else "Telegram не принял сообщение"
    except requests.RequestException:
        return "Нет связи с Telegram"

def fuzzy_lookup(command, dictionary, cutoff=0.7):
    keys = list(dictionary.keys())
    for key in keys:
        if key in command:
            return key
    words = command.split()
    for part in words:
        match = difflib.get_close_matches(part, keys, n=1, cutoff=cutoff)
        if match:
            return match[0]
    for i in range(len(words) - 1):
        joined = words[i] + " " + words[i + 1]
        match = difflib.get_close_matches(joined, keys, n=1, cutoff=cutoff)
        if match:
            return match[0]
    return None

def media_key(code):
    ctypes.windll.user32.keybd_event(code, 0, 0, 0)
    ctypes.windll.user32.keybd_event(code, 0, 2, 0)

def parse_number(words):
    total, found = 0, False
    for w in words:
        if w in UNITS:
            total += UNITS[w]; found = True
        elif w in TENS:
            total += TENS[w]; found = True
    return total if found else None

def set_volume(percent):
    percent = max(0, min(100, percent))
    volume.SetMasterVolumeLevelScalar(percent / 100, None)
    return percent

def handle(command):
    global pending_shutdown, mic_on
    command = command.lower().strip()
    command = command.replace("ё", "е")

    if "Громкость" in command:
        value = parse_number(command.split())
        if value is not None:
            return f"Громкость {set_volume(value)}%"
    
    if "микрофон" in command:
        if "выключ" in command:
            mic_on = False
            beep_off()
            return "Микрофон выключен"
        if "включ" in command:
            mic_on = True
            beep_on()
            return "Микрофон включён" 
    if not mic_on:
        return None

    if pending_shutdown:
        pending_shutdown = False
        if command == "да":
            os.system("shutdown /s /t 5")
            return "Выключаю компьютер через 5 секунд"
        return "Выключение отменено"

    if pending_shutdown:
        pending_shutdown = False
        if command == "да":
            os.system("shutdown /s /t 5")
            return "Выключаю компьютер через 5 секунд"
        return "Выключение отменено"

    if command.startswith("напиши "):
        text = command.replace("напиши ", "", 1)
        return send_telegram(text)

    if "громче" in command or "добавь" in command:
        return f"Громкость {change_volume(0.1)}%"

    if "тише" in command or "убавь" in command:
        return f"Громкость {change_volume(-0.1)}%"

    if "выключи" in command:
        pending_shutdown = True
        return "Выключить компьютер? Скажите да или любое другое слово для отмены"

    if "стоп" in command or "пауза" in command or "стой" in command:
        media_play_pause()
        media_paused = True
        return "Пауза"

    if "продолжай" in command or "дальше" in command:
        media_play_pause()
        media_paused = False
        return "Продолжаю"

    
    if "следующая" in command or "следующую" in command or "следующее" in command:
        media_key(0xB0)
        return "Следующая песня"

    if "прошлая" in command or "предыдущая" in command or "назад" in command:
        media_key(0xB1) 
        return "Предыдущая песня"

    if "блокировка" in command or "заблокируй" in command:
        os.system("rundll32.exe user32.dll,LockWorkStation")
        return "Блокирую компьютер"

    if "перезагрузи" in command:
        return "Перезагрузка пока отключена"

    if command.startswith("открой"):
        command = command.replace("открой", "", 1).strip()

    key = fuzzy_lookup(command, SITES)
    if key:
        webbrowser.open(SITES[key])
        return f"Открываю {key}"

    key = fuzzy_lookup(command, APPS)
    if key:
        try:
            os.startfile(APPS[key])
            return f"Открываю {key}"
        except OSError:
            return f"Не могу открыть {key}, нужен полный путь к программе"

    return ask_ai(command)

print("Я тута).")
with sd.RawInputStream(samplerate=16000, blocksize=8000,
                       dtype="int16", channels=1, callback=audio_callback):
    while True:
        data = audio_queue.get()
        if rec.AcceptWaveform(data):
            text = json.loads(rec.Result())["text"]
            if text:
                print("Вы сказали:", text)
                result = handle(text)
                if result:
                    print(result)