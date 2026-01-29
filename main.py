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

# 手動攔截清單：包含新聞基本職業、行為、以及常見地名人名
MANUAL_BLOCK = {
    'lawmaker', 'lawmakers', 'voter', 'voters', 'protester', 'protesters', 'gather', 'gathers',
    'protest', 'protests', 'strike', 'strikes', 'attack', 'attacks', 'blast', 'blasts',
    'warns', 'insists', 'insist', 'claim', 'claims', 'actually', 'really', 'behind',
    'police', 'official', 'officials', 'government', 'president', 'minister', 'mayor',
    'palace', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
    'celebrity', 'famous', 'everything', 'something', 'another', 'himself', 'herself',
    'comeback', 'outside', 'inside', 'through', 'across', 'against', 'without'
}

def get_common_words(limit=5000): # 難度提升至 5000 字
    try:
        url = "https://raw.githubusercontent.com/first20hours/google-10000-english/master/google-10000-english-no-swears.txt"
        res = requests.get(url, timeout=10)
        return set(res.text.lower().splitlines()[:limit])
    except: return set()

COMMON_SET = get_common_words(5000)

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
            
            for i, (word, tag) in enumerate(tagged):
                word_lower = word.lower()
                
                # 1. 基礎長度門檻 (4字以上)
                if len(word_lower) < 4: continue
                
                # 2. 實體排除邏輯 (大寫通常是地名人名)
                # 如果單字開頭大寫，且不在我們常用字的前 1000 名(避免標題第一個字被誤殺)，就排除
                if word[0].isupper() and word_lower not in list(COMMON_SET)[:1000]:
                    continue
                
                # 3. 詞性排除 (代名詞、數詞)
                if tag.startswith('PRP') or tag == 'CD': continue
                
                # 4. 手動黑名單 & 5000字常用字排除
                if word_lower in MANUAL_BLOCK or word_lower in COMMON_SET:
                    continue
                
                # 5. 詞形還原後再次過濾
                base = lemmatize_word(word_lower)
                if base in COMMON_SET or base in MANUAL_BLOCK or len(base) < 4:
                    continue
                
                if base not in word_pool:
                    word_pool[base] = sentence

        candidate_keys = list(word_pool.keys())
        print(f"篩選完成：符合 5000 字標準的單字數為 {len(candidate_keys)}")
        print(f"難詞候選池預覽: {candidate_keys[:10]}")

        # 如果 5000 字太嚴格導致單字不夠 10 個，退而求其次用 3000 字保底
        if len(candidate_keys) < 10:
            print("難詞不足，啟動保底補充...")
            backup_set = set(list(COMMON_SET)[:3000])
            # ... (保底邏輯)

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
        print(f"Error: {e}"); return []

def send_to_telegram(items):
    if not items: return
    message = "<b>今日時事精選：深度難詞 (5000字版)</b> 🎓\n" + "-"*20 + "\n\n"
    for i, item in enumerate(items, 1):
        p = f" <code>{item['phonetic']}</code>" if item['phonetic'] else ""
        message += f"{i}. <b>{item['word']}</b>{p}\n   🔹 {item['translation']}\n   📝 <i>{item['context_en']}</i>\n   💡 {item['context_cn']}\n\n"

    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                  data={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"})

if __name__ == "__main__":
    data = get_news_data()
    send_to_telegram(data)
