import requests
from bs4 import BeautifulSoup
import re
from deep_translator import GoogleTranslator
import os

# 從 GitHub Secrets 讀取資訊
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def get_phonetic(word):
    """使用 Dictionary API 獲取標準音標 (IPA)"""
    try:
        # 使用免費的 Dictionary API
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            # 優先嘗試取得外層的 phonetic 欄位
            phonetic = data[0].get('phonetic')
            if phonetic:
                return phonetic
            # 如果沒有，從 phonetics 列表尋找包含 text 的項目
            phonetics = data[0].get('phonetics', [])
            for p in phonetics:
                if p.get('text'):
                    return p.get('text')
        return ""
    except:
        return ""

def get_cnn_data(limit=10):
    url = "https://edition.cnn.com/"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        # 抓取 CNN 標題
        headlines = [h.get_text().strip() for h in soup.find_all(['span', 'h3'], class_='container__headline-text')]
    except Exception as e:
        print(f"CNN 抓取失敗: {e}")
        return []
    
    results = []
    used_words = set()
    translator = GoogleTranslator(source='en', target='zh-TW')

    for sentence in headlines:
        # 篩選 9 個字母以上的單字
        words_in_sentence = re.findall(r'\b[a-z]{9,}\b', sentence.lower())
        for word in words_in_sentence:
            if word not in used_words and len(results) < limit:
                try:
                    # 翻譯單字
                    word_cn = translator.translate(word)
                    # 獲取音標 (IPA)
                    phonetic = get_phonetic(word)
                    # 翻譯原句
                    context_cn = translator.translate(sentence)
                    
                    results.append({
                        'word': word.capitalize(),
                        'phonetic': phonetic,
                        'translation': word_cn,
                        'context_en': sentence,
                        'context_cn': context_cn
                    })
                    used_words.add(word)
                    print(f"成功處理: {word} {phonetic}")
                except Exception as e:
                    print(f"處理單字 {word} 時出錯: {e}")
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
        # 組合音標顯示：如果有音標就顯示，沒有就空白
        phonetic_display = f" <code>{item['phonetic']}</code>" if item['phonetic'] else ""
        
        message += f"{i}. <b>{item['word']}</b>{phonetic_display}\n"
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
