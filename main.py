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

# --- 基礎環境下載 ---
for pkg in ['wordnet', 'averaged_perceptron_tagger', 'averaged_perceptron_tagger_eng', 
            'omw-1.4', 'punkt', 'punkt_tab', 'maxent_ne_chunker', 'maxent_ne_chunker_tab', 'words']:
    nltk.download(pkg, quiet=True)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def get_common_words(limit=1000):
    try:
        url = "https://raw.githubusercontent.com/first20hours/google-10000-english/master/google-10000-english-no-swears.txt"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            return set(res.text.lower().splitlines()[:limit])
    except: pass
    return set()

COMMON_FILTER = get_common_words(1000)

def lemmatize_word(word):
    try:
        lemmatizer = WordNetLemmatizer()
        tag = nltk.pos_tag([word])[0][1]
        pos = tag[0].upper()
        tag_dict = {"J": wordnet.ADJ, "N": wordnet.NOUN, "V": wordnet.VERB, "R": wordnet.ADV}
        return lemmatizer.lemmatize(word, tag_dict.get(pos, wordnet.NOUN))
    except: return word

def get_cnn_data():
    url = "https://edition.cnn.com/"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    
    print("--- 步驟 1: 抓取網頁 ---")
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 強化版選擇器：抓取所有可能的標題類別
        selectors = [
            'span.container__headline-text', 
            'h3.container__headline-text',
            '.cd__headline-text',
            '.c-headline-text'
        ]
        headlines = []
        for s in selectors:
            headlines.extend([h.get_text().strip() for h in soup.select(s)])
        
        headlines = list(set(headlines)) # 去重
        print(f"成功抓取到 {len(headlines)} 則標題")
        
        if not headlines:
            # 最後手段：抓取所有 h2, h3 標籤
            headlines = [h.get_text().strip() for h in soup.find_all(['h2', 'h3']) if len(h.get_text().strip()) > 10]
            print(f"備用方案抓取到 {len(headlines)} 則標題")

    except Exception as e:
        print(f"抓取失敗: {e}")
        return []

    print("--- 步驟 2: 篩選單字 ---")
    word_pool = {}
    person_names = set()

    for sentence in headlines:
        try:
            tokens = word_tokenize(sentence)
            chunks = ne_chunk(pos_tag(tokens))
            for chunk in chunks:
                if hasattr(chunk, 'label') and chunk.label() == 'PERSON':
                    for leaf in chunk: person_names.add(leaf[0].lower())

            raw_words = re.findall(r'\b[a-z]{6,}\b', sentence.lower())
            for rw in raw_words:
                if rw not in person_names and rw not in COMMON_FILTER:
                    base = lemmatize_word(rw)
                    if base not in COMMON_FILTER:
                        word_pool[base] = sentence
        except: continue

    print(f"初步篩選後剩餘: {len(word_pool)} 個單字")

    # 如果還是 0，強制抓取標題中的長單字（無視常用字過濾，但避開人名）
    if not word_pool:
        print("警告: 篩選後為 0，啟動緊急保底...")
        for sentence in headlines:
            raw_words = re.findall(r'\b[a-z]{7,}\b', sentence.lower())
            for rw in raw_words:
                if rw not in person_names:
                    word_pool[lemmatize_word(rw)] = sentence
                if len(word_pool) >= 15: break

    candidate_keys = list(word_pool.keys())
    if not candidate_keys:
        print("致命錯誤: 即使保底也抓不到單字")
        return []

    print("--- 步驟 3: 翻譯與 API 查詢 ---")
