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

# --- 基礎環境準備 ---
try:
    nltk.download('wordnet')
    nltk.download('averaged_perceptron_tagger')
    nltk.download('averaged_perceptron_tagger_eng')
    nltk.download('omw-1.4')
    nltk.download('punkt')
    nltk.download('punkt_tab')
    nltk.download('maxent_ne_chunker')
    nltk.download('maxent_ne_chunker_tab')
    nltk.download('words')
except:
    pass

BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def get_common_words(limit=1000): # 改為 1000 讓篩選不要那麼嚴格
    try:
        url = "https://raw.githubusercontent.com/first20hours/google-10000-english/master/google-10000-english-no-swears.txt"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return set(response.text.lower().splitlines()[:limit])
    except:
        pass
    return set()

COMMON_WORDS_FILTER = get_common_words(1000) 

def lemmatize_word(word):
    try:
        lemmatizer = WordNetLemmatizer()
        tag = nltk.pos_tag([word])[0][1]
        if tag.startswith('JJ'): return word
        pos = nltk.pos_tag([word])[0][1][0].upper()
        tag_dict = {"J": wordnet.ADJ, "N": wordnet.NOUN, "V": wordnet.VERB, "R": wordnet.ADV}
        return lemmatizer.lemmatize(word, tag_dict.get(pos, wordnet.NOUN))
    except:
        return word

def get_phonetic(word):
    try:
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            return data[0].get('phonetic') or (data[0].get('phonetics', [{}])[0].get('text', ""))
    except:
        pass
    return ""

def get_cnn_data(target_count=10):
    url = "https://edition.cnn.com/"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        headlines = [h.get_text().strip() for h in soup.find_all(['span', 'h3'], class_='container__headline-text')]
    except:
        return []
    
    word_pool = {}
    for sentence in headlines:
        try:
            tokens = word_tokenize(sentence)
            tags = pos_tag(tokens)
            chunks = ne_chunk(tags)
            
            person_names = set()
            for chunk in chunks:
                if hasattr(chunk, 'label') and chunk.label() == 'PERSON':
                    for leaf in chunk: person_names.add(leaf[0].lower())

            raw_words = re.findall(r'\b[a-z]{6,}\b', sentence.lower())
            for raw_word in raw_words:
                # 過濾人名與常用字
                if raw_word in person_names or raw_word in COMMON_WORDS_FILTER:
                    continue
                
                word_base = lemmatize_word(raw_word)
                if word_base not in COMMON_WORDS_FILTER and len(word_base) >= 6:
                    if word_base not in word_pool:
                        word_pool[word_base] = sentence
        except:
            continue

    candidate_list = list(word_pool.keys())
    print(f"篩選後剩餘單字數: {len(candidate_list)}")

    # 【自動補位機制】如果候選字太少，就降低過濾標準再抓一次
    if len(candidate_list) < target_count:
        print("候選字不足，正在放寬標準...")
        for sentence in headlines:
            raw_words = re.findall(r'\b[a-z]{6,}\b', sentence.lower())
            for raw_word in raw_words:
                if len(word_pool) >= 20: break # 補到 20 個備選就夠了
                if raw_word not in word_pool:
                    word_pool[lemmatize_word(raw_word)] = sentence
        candidate_list = list(word_pool.keys())

    selected_keys = random.sample(candidate_list, min(len(candidate_list), target_count))
    results = []
    translator = GoogleTranslator(source='en', target='zh-TW')

    for word in selected_keys:
        try:
            word_cn = translator.translate(word)
            phonetic = get_phonetic(word)
            sentence = word_pool[word]
            context_cn = translator.translate(sentence)
            results.append({'word': word.capitalize(), 'phonetic': phonetic, 'translation': word_cn, 'context_en': sentence, 'context_cn': context_cn})
            time.sleep(0.3)
        except:
            continue
    return results

def send_to_telegram(items):
    if not items: return
    message = "<b>今日 CNN 挑戰單字庫</b> 🎓\n--------------------------------\n\n"
    for i, item in enumerate(items, 1):
        p_display = f" <code>{item['phonetic']}</code>" if item['phonetic'] else ""
        message += f"{i}. <b>{item['word']}</b>{p_display}\n   🔹 中文：{item['translation']}\n   📝 原句：<i>{item['context_en']}</i>\n   💡 翻譯：{item['context_cn']}\n\n"

    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(api_url, data={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"})

if __name__ == "__main__":
    data = get_cnn_data(10)
    send_to_telegram(data)
