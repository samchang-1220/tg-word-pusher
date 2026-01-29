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

def get_common_words(limit=1000):
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
        tag_info = nltk.pos_tag([word])[0][1]
        if tag_info.startswith('JJ'): return word
        pos = tag_info[0].upper()
        tag_dict = {"J": wordnet.ADJ, "N": wordnet.NOUN, "V": wordnet.VERB, "R": wordnet.ADV}
        return lemmatizer.lemmatize(word, tag_dict.get(pos, wordnet.NOUN))
    except:
        return word

def get_cnn_data(target_count=10):
    url = "https://edition.cnn.com/"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        headlines = list(set([h.get_text().strip() for h in soup.find_all(['span', 'h3'], class_='container__headline-text')]))
        print(f"抓取到 {len(headlines)} 則不重複標題。")
    except:
        return []
    
    word_pool = {}
    skipped_by_common = set()
    skipped_by_person = set()

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
                if raw_word in person_names:
                    skipped_by_person.add(raw_word)
                    continue
                if raw_word in COMMON_WORDS_FILTER:
                    skipped_by_common.add(raw_word)
                    continue
                
                word_base = lemmatize_word(raw_word)
                if word_base not in COMMON_WORDS_FILTER and len(word_base) >= 6:
                    if word_base not in word_pool:
                        word_pool[word_base] = sentence
        except:
            continue

    print(f"因常用字跳過: {list(skipped_by_common)[:10]}...")
    print(f"因人名跳過: {list(skipped_by_person)[:10]}...")
    
    candidate_list = list(word_pool.keys())
    print(f"【初次篩選】剩餘難詞數: {len(candidate_list)}")

    # 強力保底機制
    if len(candidate_list) < target_count:
        print("候選字不足，啟動保底機制...")
        for sentence in headlines:
            raw_words = re.findall(r'\b[a-z]{6,}\b', sentence.lower())
            for raw_word in raw_words:
                base = lemmatize_word(raw_word)
                if base not in word_pool and base not in person_names:
                    word_pool[base] = sentence
                if len(word_pool) >= 20: break
        candidate_list = list(word_pool.keys())

    selected_keys = random.sample(candidate_list, min(len(candidate_list), target_count))
    # ... (後續翻譯與發送邏輯維持不變)
