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

# --- 環境初始化 (補齊 NER 必要組件) ---
for pkg in ['wordnet', 'averaged_perceptron_tagger', 'averaged_perceptron_tagger_eng', 
            'omw-1.4', 'punkt', 'punkt_tab', 'maxent_ne_chunker', 'maxent_ne_chunker_tab', 'words']:
    nltk.download(pkg, quiet=True)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def get_common_words(limit=1500): # 設定排除前 1500 個常用字
    try:
        url = "https://raw.githubusercontent.com/first20hours/google-10000-english/master/google-10000-english-no-swears.txt"
        res = requests.get(url, timeout=10)
        return set(res.text.lower().splitlines()[:limit])
    except: return set()

COMMON_FILTER = get_common_words(1500)

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
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        headlines = list(set([h.get_text().strip() for h in soup.find_all(['h2', 'h3']) if len(h.get_text().strip()) > 15]))
        
        word_pool = {}
        for sentence in headlines:
            # --- NER 人名過濾 ---
            tokens = word_tokenize(sentence)
            tags = pos_tag(tokens)
            chunks = ne_chunk(tags)
            person_names = set()
            for chunk in chunks:
                if hasattr(chunk, 'label') and chunk.label() == 'PERSON':
                    for leaf in chunk: person_names.add(leaf[0].lower())

            # 抓取 6 個字母以上的單字
            raw_words = re.findall(r'\b[a-z]{6,}\b', sentence.lower())
            for rw in raw_words:
                if rw not in person_names and rw not in COMMON_FILTER:
                    base = lemmatize_word(rw)
                    if base not in COMMON_FILTER:
                        word_pool[base] = sentence
        
        # 保底機制：若不夠 10 個，稍微降低難度
        if len(word_pool) < 10:
            for sentence in headlines:
                for rw in re.findall(r'\b[a-z]{6,}\b', sentence.lower()):
                    if len(word_pool) >= 20: break
                    word_pool[lemmatize_word(rw)] = sentence

        candidate_keys = list(word_pool.keys())
        selected_keys = random.sample(candidate_list, min(len(candidate_list), 10)) if (candidate_list := candidate_keys) else []
        
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
    except: return []

def send_to_telegram(items):
    if not items: return
    message = "<b>今日時事精選難詞 (BBC版)</b> 🎓\n" + "-"*20 + "\n\n"
    for i, item in enumerate(items, 1):
        p = f" <code>{item['phonetic']}</code>" if item['phonetic'] else ""
        message += f"{i}. <b>{item['word']}</b>{p}\n   🔹 {item['translation']}\n   📝 <i>{item['context_en']}</i>\n   💡 {item['context_cn']}\n\n"

    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                  data={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"})

if __name__ == "__main__":
    data = get_news_data()
    send_to_telegram(data)
