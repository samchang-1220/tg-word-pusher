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

# 新增：新聞常見但「太簡單」或「沒意義」的單字黑名單
NEWS_JUNK_WORDS = {
    'mayor', 'police', 'official', 'officials', 'sends', 'gather', 'gathers', 
    'roof', 'offs', 'behind', 'across', 'against', 'around', 'without', 
    'people', 'should', 'would', 'could', 'years', 'months', 'weeks', 
    'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
    'report', 'reports', 'breaking', 'latest', 'news', 'actually', 'really'
}

def get_common_words(limit=4500): # 稍微提高到 4500，介於 4000 與 5000 之間
    try:
        url = "https://raw.githubusercontent.com/first20hours/google-10000-english/master/google-10000-english-no-swears.txt"
        res = requests.get(url, timeout=10)
        return res.text.lower().splitlines()[:limit]
    except: return []

COMMON_SET = set(get_common_words(4500))

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
        excluded_entities = set()

        for sentence in headlines:
            tokens = word_tokenize(sentence)
            for chunk in ne_chunk(pos_tag(tokens)):
                if hasattr(chunk, 'label') and chunk.label() in ['PERSON', 'GPE', 'ORGANIZATION']:
                    for leaf in chunk: excluded_entities.add(leaf[0].lower())

        for sentence in headlines:
            raw_tokens = re.findall(r'\b[a-zA-Z]+\b', sentence)
            for token in raw_tokens:
                word_clean = token.lower()
                
                # 排除邏輯：
                # 1. 排除人名/地名 2. 排除 4500 常用字 3. 排除新聞贅詞 4. 長度過短
                if len(word_clean) < 5: continue # 既然你覺得 stun(4字) 太簡單，我們拉到 5 字以上
                if word_clean in NEWS_JUNK_WORDS or word_clean in COMMON_SET or word_clean in excluded_entities:
                    continue
                
                base = lemmatize_word(word_clean)
                
                # 最終檢查：還原後也不能在常用字或贅詞清單中
                if base not in COMMON_SET and base not in NEWS_JUNK_WORDS and base not in excluded_entities:
                    if len(base) >= 5:
                        word_pool[base] = sentence

        candidate_keys = list(word_pool.keys())
        print(f"篩選完成：符合難度標準的單字數為 {len(candidate_keys)}")
        
        # 顯示前 10 個篩選出的字作為 Debug 參考
        print(f"預選清單參考: {candidate_keys[:10]}")

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
        print(f"發生錯誤: {e}"); return []

def send_to_telegram(items):
    if not items: return
    message = "<b>今日時事精選單字 (品質精煉版)</b> 🎓\n" + "-"*20 + "\n\n"
    for i, item in enumerate(items, 1):
        p = f" <code>{item['phonetic']}</code>" if item['phonetic'] else ""
        message += f"{i}. <b>{item['word']}</b>{p}\n   🔹 {item['translation']}\n   📝 <i>{item['context_en']}</i>\n   💡 {item['context_cn']}\n\n"

    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                  data={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"})

if __name__ == "__main__":
    data = get_news_data()
    send_to_telegram(data)
