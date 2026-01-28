import requests
from bs4 import BeautifulSoup
import re
from deep_translator import GoogleTranslator
import os

# 從 GitHub Secrets 讀取資訊
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def get_kk(word):
    """從 Yahoo 字典抓取 KK 音標 (強化版)"""
    try:
        url = f"https://tw.dictionary.search.yahoo.com/search?p={word}"
        # 模擬更真實的瀏覽器行為
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 尋找包含 KK 字樣的區塊
        comp_list = soup.find_all('span', class_='compList')
        for item in comp_list:
            text = item.get_text()
            if 'KK' in text:
                # 只留下音標部分，例如 [æ...]
                return text.replace('KK', '').strip()
        return ""
    except Exception as e:
        print(f"音標抓取錯誤 ({word}): {e}")
        return ""

def get_cnn_data(limit=10):
    url = "https://edition.cnn.com/"
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    # 抓取 CNN 標題
    headlines = [h.get_text().strip() for h in soup.find_all(['span', 'h3'], class_='container__headline-text')]
    
    results = []
    used_words = set()
    translator = GoogleTranslator(source='en', target='zh-TW')

    for sentence in headlines:
        # 抓取 9 個字母以上的單字
        words_in_sentence = re.findall(r'\b[a-z]{9,}\b', sentence.lower())
        for word in words_in_sentence:
            if word not in used_words and len(results) < limit:
                try:
                    word_cn = translator.translate(word)
                    kk = get_kk(word)
                    context_cn = translator.translate(sentence)
                    
                    results.append({
                        'word': word.capitalize(),
                        'kk': kk,
                        'translation': word_cn,
                        'context_en': sentence,
                        'context_cn': context_cn
                    })
                    used_words.add(word)
                    print(f"成功處理: {word}") # 這是為了讓你在 GitHub Action Log 裡看得到進度
                except:
                    continue
                    
        if len(results) >= limit: break
    return results

def send_to_telegram(items):
    if not items: 
        print("沒有抓取到資料")
        return
        
    message = "<b>今日 CNN 時事單字推播</b> 📚\n"
    message += "--------------------------------\n\n"
    
    for i, item in enumerate(items, 1):
        # 這裡修正了讀取音標的寫法
        kk_display = f" {item['kk']}" if item['kk'] else ""
        message += f"{i}. <b>{item['word']}</b>{kk_display}\n"
        message += f"   🔹 中文：{item['translation']}\n"
        message += f"   📝 原句：<i>{item['context_en']}</i>\n"
        message += f"   💡 翻譯：{item['context_cn']}\n\n"

    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    
    res = requests.post(api_url, data=payload)
    if res.status_code != 200:
        print(f"TG 發送失敗: {res.text}")

if __name__ == "__main__":
    data = get_cnn_data(10)
    send_to_telegram(data)
