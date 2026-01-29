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

def get_common_words(limit=4000): # 下載多一點備用
    try:
        url = "https://raw.githubusercontent.com/first20hours/google-10000-english/master/google-10000-english-no-swears.txt"
        res = requests.get(url, timeout=10)
        return res.text.lower().splitlines()[:limit]
    except: return []

# 取得 4000 個常用字清單
ALL_COMMON = get_common_words(4000)

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
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        headlines = list(set([h.get_text().strip() for h in soup.find_all(['h2', 'h3']) if len(h.get_text().strip()) > 15]))
        
        # 準備不同嚴格程度的過濾器
        filter_hard = set(ALL_COMMON[:3000])   # 排除前 3000 (難)
        filter_mid = set(ALL_COMMON[:1500])    # 排除前 1500 (中)
        filter_easy = set(ALL_COMMON[:600])     # 排除前 600 (極基礎)

        word_pool = {}
        person_names = set()

        # 先掃描所有人名
        for sentence in headlines:
            tokens = word_tokenize(sentence)
            for chunk in ne_chunk(pos_tag(tokens)):
                if hasattr(chunk, 'label') and chunk.label() == 'PERSON':
                    for leaf in chunk: person_names.add(leaf[0].lower())

        # --- 策略 1：嘗試高難度篩選 ---
        for sentence in headlines:
            for rw in re.findall(r'\b[a-z]{7,}\b', sentence.lower()):
                base = lemmatize_word(rw)
                if base not in person_names and base not in filter_hard:
                    word_pool[base] = sentence

        # --- 策略 2：如果單字太少，補充中等難度 ---
        if len(word_pool) < 10:
            print("高難度詞彙不足，補充中等難度詞彙...")
            for sentence in headlines:
                for rw in re.findall(r'\b[a-z]{6,}\b', sentence.lower()):
                    base = lemmatize_word(rw)
                    if base not in person_names and base not in filter_mid and base not in word_pool:
                        word_pool[base] = sentence
                    if len(word_pool) >= 15: break

        # --- 策略 3：最後保底，至少排除極基礎詞 ---
        if len(word_pool) < 10:
            print("單字仍不足，執行最終保底...")
            for sentence in headlines:
                for rw in re.findall(r'\b[a-z]{6,}\b', sentence.lower()):
                    base = lemmatize_word(rw)
                    if base not in person_names and base not in filter_easy and base not in word_pool:
                        word_pool[base] = sentence

        candidate_keys = list(word_pool.keys())
        selected_keys = random.sample(candidate_keys, min(len(candidate_keys), 10))
        
        results = []
        translator = GoogleTranslator(source='en', target='zh-TW')
        for word in selected_keys:
            try:
                results.append({
                    'word': word.capitalize(),
                    'phonetic': get_phonetic(word),
                    'translation': translator.translate(word),
                    'context_en': word_pool[word],
                    'context_cn': translator.translate(word_pool[word])
                })
                time.sleep(0.3)
            except: continue
        return results
    except Exception as e:
        print(f"Error: {e}")
        return []

def send_to_telegram(items):
    if not items: return
    message = "<b>今日時事難詞 (挑戰版)</b> 🎓\n" + "-"*20 + "\n\n"
    for i, item in enumerate(items, 1):
        p = f" <code>{item['phonetic']}</code>" if item['phonetic'] else ""
        message += f"{i}. <b>{item['word']}</b>{p}\n   🔹 {item['translation']}\n   📝 <i>{item['context_en']}</i>\n   💡 {item['context_cn']}\n\n"

    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                  data={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"})

if __name__ == "__main__":
    data = get_news_data()
    send_to_telegram(data)
