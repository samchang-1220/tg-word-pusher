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

# 強制排除的疑問詞與代名詞
HARD_FORBIDDEN = {'why', 'how', 'when', 'where', 'which', 'who', 'whom', 'whose', 'what', 'that', 'this', 'these', 'those'}

def get_common_words(limit=4000):
    try:
        url = "https://raw.githubusercontent.com/first20hours/google-10000-english/master/google-10000-english-no-swears.txt"
        res = requests.get(url, timeout=10)
        return res.text.lower().splitlines()[:limit]
    except: return []

COMMON_SET = set(get_common_words(4000))

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
            return res.json()[0].get('phonetic', "")
    except: pass
    return ""

def get_news_data():
    url = "https://www.bbc.com/news"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        headlines = list(set([h.get_text().strip() for h in soup.find_all(['h2', 'h3']) if len(h.get_text().strip()) > 15]))
        print(f"--- 抓取到 {len(headlines)} 則標題 ---")

        word_pool = {}
        excluded_entities = set()

        # 1. 深度辨識實體 (人名、地名、組織)
        for sentence in headlines:
            tokens = word_tokenize(sentence)
            for chunk in ne_chunk(pos_tag(tokens)):
                if hasattr(chunk, 'label'):
                    # 排除 PERSON (人名), GPE (地名/國名), ORGANIZATION (組織), FAC (建築物)
                    if chunk.label() in ['PERSON', 'GPE', 'ORGANIZATION', 'FAC']:
                        for leaf in chunk: 
                            excluded_entities.add(leaf[0].lower())

        # 2. 開始篩選
        for sentence in headlines:
            # 修正後的正則：只抓純英文字母
            raw_tokens = re.findall(r'\b[a-zA-Z]+\b', sentence)
            
            for token in raw_tokens:
                word_clean = token.lower()
                
                # 排除邏輯
                if len(word_clean) < 4: continue
                if word_clean in HARD_FORBIDDEN: continue
                if word_clean in excluded_entities or word_clean in COMMON_SET: continue
                
                # 詞性過濾 (排除代名詞等)
                tag = pos_tag([word_clean])[0][1]
                if tag in ['PRP', 'PRP$', 'WP', 'WP$']: continue 
                
                base = lemmatize_word(word_clean)
                # 再次確認還原後的字
                if base not in COMMON_SET and base not in excluded_entities and base not in HARD_FORBIDDEN:
                    if base not in word_pool:
                        word_pool[base] = sentence

        candidate_keys = list(word_pool.keys())
        print(f"篩選完成：符合標準的難詞數 {len(candidate_keys)}")
        
        # 保底機制維持 2000 字
        if len(candidate_keys) < 10:
            backup_set = set(ALL_COMMON[:2000]) if 'ALL_COMMON' in globals() else set()
            # ... (保底邏輯同前，但加入 excluded_entities 排除)

        selected_keys = random.sample(candidate_keys, min(len(candidate_keys), 10))
        results = []
        translator = GoogleTranslator(source='en', target='zh-TW')
        
        for word in selected_keys:
            try:
                print(f"正在處理: {word}")
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
        print(f"Error: {e}"); return []

def send_to_telegram(items):
    if not items: return
    message = "<b>今日時事精選單字 (嚴選版)</b> 🎓\n" + "-"*20 + "\n\n"
    for i, item in enumerate(items, 1):
        p = f" <code>{item['phonetic']}</code>" if item['phonetic'] else ""
        message += f"{i}. <b>{item['word']}</b>{p}\n   🔹 {item['translation']}\n   📝 <i>{item['context_en']}</i>\n   💡 {item['context_cn']}\n\n"

    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                  data={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"})

if __name__ == "__main__":
    data = get_news_data()
    send_to_telegram(data)
