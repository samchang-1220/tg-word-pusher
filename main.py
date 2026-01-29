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
print("正在初始化環境與下載 NLTK 資源...")
for pkg in ['wordnet', 'averaged_perceptron_tagger', 'averaged_perceptron_tagger_eng', 
            'omw-1.4', 'punkt', 'punkt_tab', 'maxent_ne_chunker', 'maxent_ne_chunker_tab', 'words']:
    nltk.download(pkg, quiet=True)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def get_common_words(limit=4000):
    """調整為排除前 4000 常用字"""
    print(f"正在載入前 {limit} 個常用字排除表...")
    try:
        url = "https://raw.githubusercontent.com/first20hours/google-10000-english/master/google-10000-english-no-swears.txt"
        res = requests.get(url, timeout=10)
        return res.text.lower().splitlines()[:limit]
    except Exception as e:
        print(f"常用字載入失敗: {e}")
        return []

# 取得 4000 個常用字清單
ALL_COMMON = get_common_words(4000)
COMMON_SET = set(ALL_COMMON)

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
        print(f"--- 步驟 1: 成功抓取到 {len(headlines)} 則標題 ---")

        word_pool = {}
        person_names = set()

        # 預先掃描所有人名
        for sentence in headlines:
            tokens = word_tokenize(sentence)
            for chunk in ne_chunk(pos_tag(tokens)):
                if hasattr(chunk, 'label') and chunk.label() == 'PERSON':
                    for leaf in chunk: person_names.add(leaf[0].lower())

        # 開始篩選單字
        for sentence in headlines:
            tokens = word_tokenize(sentence)
            tagged = pos_tag(tokens)
            
            for word_token, tag in tagged:
                word_lower = word_token.lower()
                
                # 門檻調低：長度至少 4 個字母即可 (配合 stun)
                if len(word_lower) < 4: continue
                # 依然排除 herslef/themselves 等代名詞，這些真的不用背
                if tag in ['PRP', 'PRP$', 'WP', 'WP$']: continue 
                # 排除人名與 4000 常用字
                if word_lower in person_names or word_lower in COMMON_SET: continue
                
                # 詞形還原
                base = lemmatize_word(word_lower)
                
                # 直接加入 pool，不進行二次長度檢查
                if base not in COMMON_SET and base not in person_names:
                    if base not in word_pool:
                        word_pool[base] = sentence

        candidate_keys = list(word_pool.keys())
        print(f"篩選完成：符合 4000 字難度標準的單字數為 {len(candidate_keys)}")
        
        # 保底機制：若單字不足 10 個，從 2000 字標準補充，但依然堅持 4 字母門檻
        if len(candidate_keys) < 10:
            print("難詞不足，啟動保底補充機制...")
            backup_set = set(ALL_COMMON[:2000])
            for sentence in headlines:
                for rw in re.findall(r'\b[a-z]{4,}\b', sentence.lower()):
                    base = lemmatize_word(rw)
                    if base not in person_names and base not in backup_set and base not in word_pool:
                        word_pool[base] = sentence
                    if len(word_pool) >= 15: break
            candidate_keys = list(word_pool.keys())

        selected_keys = random.sample(candidate_keys, min(len(candidate_keys), 10))
        results = []
        translator = GoogleTranslator(source='en', target='zh-TW')
        
        print(f"--- 步驟 2: 開始翻譯與查詢音標 (目標 {len(selected_keys)} 個) ---")
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
        print(f"執行過程發生錯誤: {e}")
        return []

def send_to_telegram(items):
    if not items: 
        print("沒有單字可以發送。")
        return
    message = "<b>今日時事精選單字 (4000字難度版)</b> 🎓\n" + "-"*20 + "\n\n"
    for i, item in enumerate(items, 1):
        p = f" <code>{item['phonetic']}</code>" if item['phonetic'] else ""
        message += f"{i}. <b>{item['word']}</b>{p}\n   🔹 {item['translation']}\n   📝 <i>{item['context_en']}</i>\n   💡 {item['context_cn']}\n\n"

    res = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                        data={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"})
    print(f"Telegram 發送狀態: {res.status_code}")

if __name__ == "__main__":
    data = get_news_data()
    send_to_telegram(data)
