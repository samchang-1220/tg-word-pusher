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

# --- 修正處：補齊所有可能的 NLTK 數據包 ---
try:
    nltk.download('wordnet')
    nltk.download('averaged_perceptron_tagger')
    nltk.download('averaged_perceptron_tagger_eng')
    nltk.download('omw-1.4')
    nltk.download('punkt')
    nltk.download('punkt_tab')
    nltk.download('maxent_ne_chunker')
    nltk.download('maxent_ne_chunker_tab') # 補上這行解決報錯
    nltk.download('words')
except:
    pass

BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def get_common_words(limit=2000):
    try:
        url = "https://raw.githubusercontent.com/first20hours/google-10000-english/master/google-10000-english-no-swears.txt"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            all_words = response.text.lower().splitlines()
            return set(all_words[:limit])
        return set()
    except:
        return set()

COMMON_WORDS_2000 = get_common_words(2000)
MANUAL_BLACKLIST = {'people', 'should', 'without', 'government', 'president'}

def get_wordnet_pos(word):
    try:
        tag = nltk.pos_tag([word])[0][1][0].upper()
        tag_dict = {"J": wordnet.ADJ, "N": wordnet.NOUN, "V": wordnet.VERB, "R": wordnet.ADV}
        return tag_dict.get(tag, wordnet.NOUN)
    except:
        return wordnet.NOUN

def lemmatize_word(word):
    try:
        lemmatizer = WordNetLemmatizer()
        tag = nltk.pos_tag([word])[0][1]
        if tag.startswith('JJ'): return word
        pos = get_wordnet_pos(word)
        return lemmatizer.lemmatize(word, pos)
    except:
        return word

def get_phonetic(word):
    try:
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            phonetic = data[0].get('phonetic') or ""
            if not phonetic:
                phonetics = data[0].get('phonetics', [])
                for p in phonetics:
                    if p.get('text'): return p.get('text')
            return phonetic
        return ""
    except:
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
                    for leaf in chunk:
                        person_names.add(leaf[0].lower())

            raw_words = re.findall(r'\b[a-z]{6,}\b', sentence.lower())
            for raw_word in raw_words:
                if raw_word in person_names or raw_word in COMMON_WORDS_2000 or raw_word in MANUAL_BLACKLIST:
                    continue
                
                word_base = lemmatize_word(raw_word)
                if word_base not in COMMON_WORDS_2000 and len(word_base) >= 6:
                    if word_base not in word_pool:
                        word_pool[word_base] = sentence
        except:
            continue

    candidate_list = list(word_pool.keys())
    if not candidate_list: return []
    
    selected_keys = random.sample(candidate_list, min(len(candidate_list), target_count))
    results = []
    translator = GoogleTranslator(source='en', target='zh-TW')

    for word in selected_keys:
        try:
            word_cn = translator.translate(word)
            phonetic = get_phonetic(word)
            sentence = word_pool[word]
            context_cn = translator.translate(sentence)
            
            results.append({
                'word': word.capitalize(),
                'phonetic': phonetic,
                'translation': word_cn,
                'context_en': sentence,
                'context_cn': context_cn
            })
            time.sleep(0.3)
        except:
            continue
            
    return results

def send_to_telegram(items):
    if not items: return
    message = "<b>今日 CNN 挑戰單字庫 (精準過濾版)</b> 🎓\n--------------------------------\n\n"
    for i, item in enumerate(items, 1):
        p_display = f" <code>{item['phonetic']}</code>" if item['phonetic'] else ""
        message += f"{i}. <b>{item['word']}</b>{p_display}\n"
        message += f"   🔹 中文：{item['translation']}\n"
        message += f"   📝 原句：<i>{item['context_en']}</i>\n"
        message += f"   💡 翻譯：{item['context_cn']}\n\n"

    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(api_url, data={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"})

if __name__ == "__main__":
    data = get_cnn_data(10)
    send_to_telegram(data)
