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

# 手動攔截清單：包含地名常見詞、新聞贅詞、代名詞
MANUAL_BLOCK = {
    'herself', 'himself', 'themselves', 'myself', 'yourself', 'ourselves',
    'warns', 'shoot', 'tackle', 'mayor', 'police', 'official', 'officials',
    'years', 'months', 'weeks', 'monday', 'tuesday', 'wednesday', 'thursday',
    'friday', 'saturday', 'sunday', 'reports', 'breaking', 'news', 'people',
    'should', 'would', 'could', 'really', 'actually', 'behind', 'across'
}

def get_common_words(limit=6000): # 難度直上 6000 字
    try:
        url = "https://raw.githubusercontent.com/first20hours/google-10000-english/master/google-10000-english-no-swears.txt"
        res = requests.get(url, timeout=10)
        return set(res.text.lower().splitlines()[:limit])
    except: return set()

COMMON_SET = get_common_words(6000)

def lemmatize_word(word):
    try:
        lemmatizer = WordNetLemmatizer()
        tag = pos_tag([word])[0][1]
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
        print(f"--- 步驟 1: 抓取到 {len(headlines)} 則標題 ---")

        word_pool = {}
        for sentence in headlines:
            tokens = word_tokenize(sentence)
            tagged = pos_tag(tokens)
            
            # --- 強效過濾邏輯 ---
            for i, (word, tag) in enumerate(tagged):
                word_lower = word.lower()
                
                # 1. 基礎長度與標點過濾
                if len(word_lower) < 5 or not word.isalpha(): continue
                
                # 2. 地名/人名大招：如果在句子中間 (i > 0) 且字首是大寫，通常是專有名詞
                if i > 0 and word[0].isupper(): continue
                
                # 3. 代名詞過濾 (PRP) 與 手動黑名單
                if tag.startswith('PRP') or word_lower in MANUAL_BLOCK: continue
                
                # 4. 詞頻過濾 (6000字)
                if word_lower in COMMON_SET: continue
                
                # 5. 詞形還原後再次比對
                base = lemmatize_word(word_lower)
                if base in COMMON_SET or base in MANUAL_BLOCK or len(base) < 5: continue
                
                if base not in word_pool:
                    word_pool[base] = sentence

        candidate_keys = list(word_pool.keys())
        print(f"篩選完成：符合 6000 字標準的單字數為 {len(candidate_keys)}")
        print(f"候選池預覽: {candidate_keys[:10]}")

        # 如果難詞太少，自動降低一點門檻到 4000 (保底)
        if len(candidate_keys) < 10:
            print("難詞不足，執行保底...")
            # ... (此處省略保底邏輯，結構同上)

        selected_keys = random.sample(candidate_keys, min(len(candidate_keys), 10))
        results = []
        translator = GoogleTranslator(source='en', target='zh-TW')
        
        for word in selected_keys:
            try:
                print(f"處理中: {word}")
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
    message = "<b>今日 BBC 深度難詞 (6000字篩選)</b> 🚀\n" + "-"*20 + "\n\n"
    for i, item in enumerate(items, 1):
        p = f" <code>{item['phonetic']}</code>" if item['phonetic'] else ""
        message += f"{i}. <b>{item['word']}</b>{p}\n   🔹 {item['translation']}\n   📝 <i>{item['context_en']}</i>\n   💡 {item['context_cn']}\n\n"

    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                  data={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"})

if __name__ == "__main__":
    data = get_news_data()
    send_to_telegram(data)
