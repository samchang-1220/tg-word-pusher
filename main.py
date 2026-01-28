import requests
from bs4 import BeautifulSoup
import re
from deep_translator import GoogleTranslator
import os
import nltk
import time
from nltk.stem import WordNetLemmatizer
from nltk.corpus import wordnet

# 補齊所有必要的 NLTK 數據包
try:
    nltk.download('wordnet')
    nltk.download('averaged_perceptron_tagger')
    nltk.download('averaged_perceptron_tagger_eng') # 新版 nltk 可能需要這個
    nltk.download('omw-1.4')
    nltk.download('punkt')     # 這是最容易漏掉的！
    nltk.download('punkt_tab') # 針對新環境的補丁
except:
    pass

BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def get_wordnet_pos(word):
    """將詞性轉為 wordnet 可用的格式"""
    try:
        tag = nltk.pos_tag([word])[0][1][0].upper()
        tag_dict = {"J": wordnet.ADJ, "N": wordnet.NOUN, "V": wordnet.VERB, "R": wordnet.ADV}
        return tag_dict.get(tag, wordnet.NOUN)
    except:
        return wordnet.NOUN

def lemmatize_word(word):
    """還原單字形態"""
    try:
        lemmatizer = WordNetLemmatizer()
        tag = nltk.pos_tag([word])[0][1]
        if tag.startswith('JJ'): # 如果是形容詞則不變
            return word
        pos = get_wordnet_pos(word)
        return lemmatizer.lemmatize(word, pos)
    except:
        return word

def get_phonetic(word):
    """獲取音標"""
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

def get_cnn_data(limit=10):
    url = "https://edition.cnn.com/"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        headlines = [h.get_text().strip() for h in soup.find_all(['span', 'h3'], class_='container__headline-text')]
    except:
        return []
    
    results = []
    used_words = set()
    translator = GoogleTranslator(source='en', target='zh-TW')

    for sentence in headlines:
        raw_words = re.findall(r'\b[a-z]{9,}\b', sentence.lower())
        for raw_word in raw_words:
            # 詞形還原
            word = lemmatize_word(raw_word)
            
            if word not in used_words and len(results) < limit:
                try:
                    word_cn = translator.translate(word)
                    phonetic = get_phonetic(word)
                    context_cn = translator.translate(sentence)
                    
                    results.append({
                        'word': word.capitalize(),
                        'phonetic': phonetic,
                        'translation': word_cn,
                        'context_en': sentence,
                        'context_cn': context_cn
                    })
                    used_words.add(word)
                    print(f"Success: {word}")
                    time.sleep(0.5) # 稍微停頓，避免被 API 判定為攻擊
                except:
                    continue
        if len(results) >= limit: break
    return results

def send_to_telegram(items):
    if not items: return
    message = "<b>今日 CNN 時事單字推播</b> 📚\n--------------------------------\n\n"
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
