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
print("正在初始化環境與下載 NLTK 資源...")
for pkg in ['wordnet', 'averaged_perceptron_tagger', 'averaged_perceptron_tagger_eng', 
            'omw-1.4', 'punkt', 'punkt_tab', 'maxent_ne_chunker', 'maxent_ne_chunker_tab', 'words']:
    nltk.download(pkg, quiet=True)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def get_common_words(limit=2000):
    print(f"正在載入前 {limit} 個常用字排除表...")
    try:
        url = "https://raw.githubusercontent.com/first20hours/google-10000-english/master/google-10000-english-no-swears.txt"
        res = requests.get(url, timeout=10)
        return set(res.text.lower().splitlines()[:limit])
    except Exception as e:
        print(f"常用字載入失敗: {e}")
        return set()

# 改回 1000 確保成功率
COMMON_FILTER = get_common_words(2000)

def lemmatize_word(word):
    try:
        lemmatizer = WordNetLemmatizer()
        tag = nltk.pos_tag([word])[0][1]
        tag_dict = {"J": wordnet.ADJ, "N": wordnet.NOUN, "V": wordnet.VERB, "R": wordnet.ADV}
        return lemmatizer.lemmatize(word, tag_dict.get(tag[0].upper(), wordnet.NOUN))
    except: return word

def get_phonetic(word):
    try:
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            return data[0].get('phonetic') or (data[0].get('phonetics', [{}])[0].get('text', ""))
    except: pass
    return ""

def get_news_data():
    url = "https://www.bbc.com/news"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    print(f"--- 步驟 1: 抓取網頁 {url} ---")
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        headlines = list(set([h.get_text().strip() for h in soup.find_all(['h2', 'h3']) if len(h.get_text().strip()) > 15]))
        print(f"成功抓取到 {len(headlines)} 則標題。")
        
        word_pool = {}
        for sentence in headlines:
            # NER 人名排除
            tokens = word_tokenize(sentence)
            tags = pos_tag(tokens)
            chunks = ne_chunk(tags)
            person_names = set()
            for chunk in chunks:
                if hasattr(chunk, 'label') and chunk.label() == 'PERSON':
                    for leaf in chunk: person_names.add(leaf[0].lower())

            # 抓取 6 個字母以上 (放寬一點)
            raw_words = re.findall(r'\b[a-z]{6,}\b', sentence.lower())
            for rw in raw_words:
                if rw not in person_names and rw not in COMMON_FILTER:
                    base = lemmatize_word(rw)
                    if base not in COMMON_FILTER:
                        word_pool[base] = sentence
        
        print(f"初步篩選後剩餘難詞數: {len(word_pool)}")
        
        # 強力保底：如果不夠 10 個，就直接抓標題裡的長單字（只避開人名）
        if len(word_pool) < 10:
            print("單字不足，正在執行保底抓取...")
            for sentence in headlines:
                for rw in re.findall(r'\b[a-z]{7,}\b', sentence.lower()):
                    base = lemmatize_word(rw)
                    if base not in person_names and base not in word_pool:
                        word_pool[base] = sentence
                    if len(word_pool) >= 20: break
        
        candidate_keys = list(word_pool.keys())
        if not candidate_keys:
            print("致命錯誤: 即使保底也抓不到任何單字。")
            return []

        selected_keys = random.sample(candidate_keys, min(len(candidate_keys), 10))
        results = []
        translator = GoogleTranslator(source='en', target='zh-TW')
        
        print(f"--- 步驟 2: 開始翻譯與查詢音標 (共 {len(selected_keys)} 個) ---")
        for word in selected_keys:
            try:
                print(f"處理中: {word}")
                results.append({
                    'word': word.capitalize(),
                    'phonetic': get_phonetic(word),
                    'translation': translator.translate(word),
                    'context_en': word_pool[word],
                    'context_cn': translator.translate(word_pool[word])
                })
                time.sleep(0.3)
            except Exception as e:
                print(f"單字 {word} 處理失敗: {e}")
        return results
    except Exception as e:
        print(f"抓取過程發生全域錯誤: {e}")
        return []

def send_to_telegram(items):
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    if not items:
        print("沒有單字可發送，正在發送測試訊號到 Telegram...")
        requests.post(api_url, data={"chat_id": CHAT_ID, "text": "⚠️ 機器人警告：今日單字庫篩選後為空，請檢查新聞源。"})
        return

    message = "<b>今日 BBC 精選單字</b> 📚\n" + "-"*20 + "\n\n"
    for i, item in enumerate(items, 1):
        p = f" <code>{item['phonetic']}</code>" if item['phonetic'] else ""
        message += f"{i}. <b>{item['word']}</b>{p}\n   🔹 {item['translation']}\n   📝 <i>{item['context_en']}</i>\n   💡 {item['context_cn']}\n\n"

    res = requests.post(api_url, data={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"})
    print(f"Telegram 發送結果: {res.status_code}")

if __name__ == "__main__":
    data = get_news_data()
    send_to_telegram(data)
