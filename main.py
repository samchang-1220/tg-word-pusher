import requests
from bs4 import BeautifulSoup
import re
from deep_translator import GoogleTranslator
import os
import nltk
import time
import random
from nltk.stem import WordNetLemmatizer
from nltk.corpus import wordnet
from nltk import ne_chunk, pos_tag, word_tokenize

# --- 環境初始化 ---
for pkg in ['wordnet', 'averaged_perceptron_tagger', 'averaged_perceptron_tagger_eng', 
            'omw-1.4', 'punkt', 'punkt_tab', 'maxent_ne_chunker', 'maxent_ne_chunker_tab', 'words']:
    nltk.download(pkg, quiet=True)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def get_common_words(limit=1000):
    try:
        url = "https://raw.githubusercontent.com/first20hours/google-10000-english/master/google-10000-english-no-swears.txt"
        res = requests.get(url, timeout=10)
        return set(res.text.lower().splitlines()[:limit])
    except: return set()

COMMON_FILTER = get_common_words(1000)

def lemmatize_word(word):
    try:
        lemmatizer = WordNetLemmatizer()
        tag = nltk.pos_tag([word])[0][1]
        tag_dict = {"J": wordnet.ADJ, "N": wordnet.NOUN, "V": wordnet.VERB, "R": wordnet.ADV}
        return lemmatizer.lemmatize(word, tag_dict.get(tag[0].upper(), wordnet.NOUN))
    except: return word

def get_news_data():
    # 改用 BBC News，對爬蟲更友善
    url = "https://www.bbc.com/news"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    print("--- 步驟 1: 抓取 BBC 新聞 ---")
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 抓取 BBC 所有的標題（常見標籤為 h2, h3）
        headlines = list(set([h.get_text().strip() for h in soup.find_all(['h2', 'h3']) if len(h.get_text().strip()) > 15]))
        print(f"成功抓取到 {len(headlines)} 則標題")
        
        if not headlines: return []

        word_pool = {}
        for sentence in headlines:
            raw_words = re.findall(r'\b[a-z]{7,}\b', sentence.lower()) # 門檻設為 7 字母
            for rw in raw_words:
                if rw not in COMMON_FILTER:
                    base = lemmatize_word(rw)
                    if base not in COMMON_FILTER:
                        word_pool[base] = sentence
        
        print(f"初步篩選後剩餘: {len(word_pool)} 個單字")
        
        # 如果太少，直接隨機補齊
        if len(word_pool) < 5:
            for sentence in headlines:
                for rw in re.findall(r'\b[a-z]{6,}\b', sentence.lower()):
                    word_pool[lemmatize_word(rw)] = sentence
                    if len(word_pool) >= 15: break

        candidate_keys = list(word_pool.keys())
        selected_keys = random.sample(candidate_keys, min(len(candidate_keys), 10))
        
        results = []
        translator = GoogleTranslator(source='en', target='zh-TW')
        for word in selected_keys:
            try:
                print(f"處理: {word}")
                results.append({
                    'word': word.capitalize(),
                    'translation': translator.translate(word),
                    'context_en': word_pool[word],
                    'context_cn': translator.translate(word_pool[word])
                })
                time.sleep(0.3)
            except: continue
        return results
    except Exception as e:
        print(f"發生錯誤: {e}")
        return []

def send_to_telegram(items):
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    if not items:
        # 診斷測試：如果沒抓到單字，發送一則報警訊息到 TG
        msg = "⚠️ 機器人回報：今日抓取單字失敗，請檢查網頁爬蟲邏輯。"
        requests.post(api_url, data={"chat_id": CHAT_ID, "text": msg})
        print("已發送診斷報警訊息。")
        return

    message = "<b>今日 BBC 精選單字</b> 📚\n" + "-"*20 + "\n\n"
    for i, item in enumerate(items, 1):
        message += f"{i}. <b>{item['word']}</b>\n   🔹 {item['translation']}\n   📝 <i>{item['context_en']}</i>\n   💡 {item['context_cn']}\n\n"

    res = requests.post(api_url, data={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"})
    print(f"TG 發送狀態: {res.status_code}")

if __name__ == "__main__":
    data = get_news_data()
    send_to_telegram(data)
