import requests
from bs4 import BeautifulSoup
import re
from deep_translator import GoogleTranslator
import os

# 從 GitHub Secrets 讀取資訊
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def get_cnn_data(limit=10):
    url = "https://edition.cnn.com/"
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    headlines = [h.get_text().strip() for h in soup.find_all(['span', 'h3'], class_='container__headline-text')]
    
    results = []
    used_words = set()
    translator = GoogleTranslator(source='en', target='zh-TW')

    for sentence in headlines:
        words_in_sentence = re.findall(r'\b[a-z]{9,}\b', sentence.lower())
        for word in words_in_sentence:
            if word not in used_words and len(results) < limit:
                translation = translator.translate(word)
                results.append({'word': word.capitalize(), 'translation': translation, 'context': sentence})
                used_words.add(word)
        if len(results) >= limit: break
    return results

def send_to_telegram(items):
    if not items: return
    message = "<b>今日 CNN 時事單字推播</b> 📚\n--------------------------------\n\n"
    for i, item in enumerate(items, 1):
        message += f"{i}. <b>{item['word']}</b>\n   🔹 中文：{item['translation']}\n   📝 原句：<i>{item['context']}</i>\n\n"

    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(api_url, data={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"})

if __name__ == "__main__":
    data = get_cnn_data(10)
    send_to_telegram(data)
