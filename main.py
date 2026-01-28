import requests
from bs4 import BeautifulSoup
import re
from deep_translator import GoogleTranslator
import os

# 從 GitHub Secrets 讀取資訊
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def get_kk(word):
    """從 Yahoo 字典抓取 KK 音標"""
    try:
        url = f"https://tw.dictionary.search.yahoo.com/search?p={word}"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(res.text, 'html.parser')
        # 尋找 KK 音標所在的標籤
        kk_tag = soup.find('span', class_='compList d-ib')
        if kk_tag:
            return kk_tag.get_text().replace('KK', '').strip()
        return ""
    except:
        return ""

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
        # 篩選長度大於 7 的單字
        words_in_sentence = re.findall(r'\b[a-z]{7,}\b', sentence.lower())
        for word in words_in_sentence:
            if word not in used_words and len(results) < limit:
                # 1. 翻譯單字
                word_cn = translator.translate(word)
                # 2. 獲取 KK 音標
                kk = get_kk(word)
                # 3. 翻譯原句
                context_cn = translator.translate(sentence)
                
                results.append({
                    'word': word.capitalize(),
                    'kk': kk,
                    'translation': word_cn,
                    'context_en': sentence,
                    'context_cn': context_cn
                })
                used_words.add(word)
        if len(results) >= limit: break
    return results

def send_to_telegram(items):
    if not items: return
    message = "<b>今日 CNN 時事單字推播</b> 📚\n"
    message += "--------------------------------\n\n"
    
    for i, item in enumerate(items, 1):
        message += f"{i}. <b>{item['word']}</b> {f'[{item[kk]}]' if item['kk'] else ''}\n"
        message += f"   🔹 中文：{item['translation']}\n"
        message += f"   📝 原句：<i>{item['context_en']}</i>\n"
        message += f"   💡 翻譯：{item['context_cn']}\n\n"

    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(api_url, data={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"})

if __name__ == "__main__":
    data = get_cnn_data(10)
    send_to_telegram(data)
