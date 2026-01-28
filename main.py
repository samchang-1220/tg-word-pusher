import requests
from bs4 import BeautifulSoup
import re
from deep_translator import GoogleTranslator
import os
import nltk
from nltk.stem import WordNetLemmatizer
from nltk.corpus import wordnet

# 下載還原單字所需的數據包
nltk.download('wordnet')
nltk.download('averaged_perceptron_tagger')
nltk.download('omw-1.4')

# 從 GitHub Secrets 讀取資訊
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def get_wordnet_pos(word):
    """將 nltk 的詞性標籤轉為 wordnet 可用的標籤"""
    tag = nltk.pos_tag([word])[0][1][0].upper()
    tag_dict = {"J": wordnet.ADJ, "N": wordnet.NOUN, "V": wordnet.VERB, "R": wordnet.ADV}
    return tag_dict.get(tag, wordnet.NOUN)

def lemmatize_word(word):
    """詞形還原：動詞變原型、名詞變單數，但保留 -ed 形容詞"""
    lemmatizer = WordNetLemmatizer()
    
    # 取得詞性
    tag = nltk.pos_tag([word])[0][1]
    
    # 如果已經是形容詞 (JJ)，則直接回傳不處理 (符合你提到的 ed 是形容詞沒關係)
    if tag.startswith('JJ'):
        return word
    
    # 否則根據詞性還原
    pos = get_wordnet_pos(word)
    return lemmatizer.lemmatize(word, pos)

def get_phonetic(word):
    """獲取音標 (IPA)"""
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
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    headlines = [h.get_text().strip() for h in soup.find_all(['span', 'h3'], class_='container__headline-text')]
    
    results = []
    used_words = set()
    translator = GoogleTranslator(source='en', target='zh-TW')

    for sentence in headlines:
        raw_words = re.findall(r'\b[a-z]{9,}\b', sentence.lower())
        for raw_word in raw_words:
            # 執行詞形還原 (名詞去s, 動詞回原型)
            word = lemmatize_word(raw_word)
            
            if word not in used_words and len(results) < limit:
                try:
                    word_cn = translator.translate(word)
                    phonetic = get_phonetic(word)
                    context_cn = translator.translate(sentence)
                    
                    results.append({
                        'word': word.capitalize(),
                        'raw_word': raw_word, # 保留原始出現的樣子
                        'phonetic': phonetic,
                        'translation': word_cn,
                        'context_en': sentence,
                        'context_cn': context_cn
                    })
                    used_words.add(word)
                except:
                    continue
        if len(results) >= limit: break
    return results

def send_to_telegram(items):
    if not items: return
    message = "<b>今日 CNN 時事單字推播</b> 📚\n--------------------------------\n\n"
    for i, item in enumerate(items, 1):
        phonetic_display = f" <code>{item['phonetic']}</code>" if item['phonetic'] else ""
        message += f"{i}. <b>{item['word']}</b>{phonetic_display}\n"
        message += f"   🔹 中文：{item['translation']}\n"
        message += f"   📝 原句：<i>{item['context_en']}</i>\n"
        message += f"   💡 翻譯：{item['context_cn']}\n\n"

    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(api_url, data={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"})

if __name__ == "__main__":
    data = get_cnn_data(10)
    send_to_telegram(data)
