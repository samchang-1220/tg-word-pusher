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

# 下載必要資源
try:
    nltk.download('wordnet')
    nltk.download('averaged_perceptron_tagger')
    nltk.download('averaged_perceptron_tagger_eng')
    nltk.download('omw-1.4')
    nltk.download('punkt')
    nltk.download('punkt_tab')
except:
    pass

BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# 擴大基礎字黑名單 (過濾 6 字母以上但太簡單的字)
BASIC_WORDS = {
    'people', 'should', 'really', 'before', 'things', 'because', 'around', 'another',
    'through', 'between', 'against', 'country', 'without', 'program', 'problem',
    'system', 'during', 'number', 'public', 'states', 'government', 'president',
    'believe', 'present', 'million', 'billion', 'company', 'service', 'support',
    'information', 'technology', 'reported', 'morning', 'evening', 'together',
    'children', 'national', 'business', 'started', 'provide', 'however', 'whether',
    'general', 'possible', 'increase', 'actually', 'experience', 'political', 'economic'
}

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
        if tag.startswith('JJ'): return word # 保留 ed 形容詞
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
            phonetic = data[0].get('phonetic')
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
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        headlines = [h.get_text().strip() for h in soup.find_all(['span', 'h3'], class_='container__headline-text')]
    except:
        return []
    
    # 建立候選單字池
    word_pool = {} # 使用 dictionary 確保單字唯一，且能對應回原句
    
    for sentence in headlines:
        # 抓取 6 個字母以上的單字
        raw_words = re.findall(r'\b[a-z]{6,}\b', sentence.lower())
        
        for raw_word in raw_words:
            # 過濾基礎字
            if raw_word in BASIC_WORDS:
                continue
            
            word_base = lemmatize_word(raw_word)
            if word_base not in BASIC_WORDS and len(word_base) >= 6:
                if word_base not in word_pool:
                    word_pool[word_base] = sentence

    # 從池子裡隨機選出 10 個單字 (如果池子不夠大就全選)
    candidate_list = list(word_pool.keys())
    selected_keys = random.sample(candidate_list, min(len(candidate_list), target_count))

    results = []
    translator = GoogleTranslator(source='en', target='zh-TW')

    print(f"從 {len(candidate_list)} 個候選詞中隨機選出了 {len(selected_keys)} 個。")

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
            time.sleep(0.3) # 防止請求過快
        except:
            continue
            
    return results

def send_to_telegram(items):
    if not items: return
    message = "<b>今日 CNN 精選單字庫 (隨機挑選)</b> 🎲\n--------------------------------\n\n"
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
