import requests
from bs4 import BeautifulSoup
import re
from deep_translator import GoogleTranslator
import os
import nltk
import time
import random
import json
from datetime import datetime, timedelta
from nltk.stem import WordNetLemmatizer
from nltk.corpus import wordnet
from nltk import ne_chunk, pos_tag, word_tokenize

# --- 環境初始化 ---
for pkg in ['wordnet', 'averaged_perceptron_tagger', 'averaged_perceptron_tagger_eng', 
            'omw-1.4', 'punkt', 'punkt_tab', 'maxent_ne_chunker', 'maxent_ne_chunker_tab', 'words']:
    nltk.download(pkg, quiet=True)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
lemmatizer = WordNetLemmatizer()

# --- 1. 黑名單讀取 (含去引號與空格處理) ---
def get_manual_blacklist():
    blacklist = set()
    file_path = 'blacklist.txt'
    internal_list = {'why', 'how', 'what', 'herself', 'himself'}
    blacklist.update(internal_list)
    
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    clean_line = line.strip().lower()
                    if not clean_line or clean_line.startswith('#'):
                        continue
                    words = clean_line.replace(',', ' ').split()
                    for w in words:
                        safe_word = w.strip().strip("'\"")
                        if safe_word:
                            blacklist.add(safe_word)
            print(f"成功載入 {len(blacklist)} 個黑名單單字。")
        except Exception as e:
            print(f"讀取 blacklist.txt 失敗: {e}")
    return blacklist

MANUAL_BLACKLIST = get_manual_blacklist()

# --- 2. 基礎工具函式 ---
def get_common_words(limit=5000):
    try:
        url = "https://raw.githubusercontent.com/first20hours/google-10000-english/master/google-10000-english-no-swears.txt"
        res = requests.get(url, timeout=10)
        return res.text.lower().splitlines()[:limit]
    except: return []

ALL_WORDS_SOURCE = get_common_words(5000)
FILTER_5000 = set(ALL_WORDS_SOURCE)
FILTER_3000 = set(ALL_WORDS_SOURCE[:3000])

def lemmatize_word(word):
    try:
        tag = pos_tag([word])[0][1]
        tag_dict = {"J": wordnet.ADJ, "N": wordnet.NOUN, "V": wordnet.VERB, "R": wordnet.ADV}
        return lemmatizer.lemmatize(word, tag_dict.get(tag[0].upper(), wordnet.NOUN))
    except: return word

def filter_vocabulary(headlines, common_set):
    word_pool = {}
    person_names = set()
    for sentence in headlines:
        tokens = word_tokenize(sentence)
        for chunk in ne_chunk(pos_tag(tokens)):
            if hasattr(chunk, 'label') and chunk.label() in ['PERSON', 'GPE', 'ORGANIZATION']:
                for leaf in chunk: person_names.add(leaf[0].lower())

        raw_words = re.findall(r'\b[a-zA-Z]{4,}\b', sentence)
        for rw in raw_words:
            word_clean = rw.lower().strip("'\"")
            # 第一道過濾：黑名單
            if word_clean in person_names or word_clean in common_set or word_clean in MANUAL_BLACKLIST:
                continue
            # 詞形還原後第二道過濾
            base = lemmatize_word(word_clean)
            if base not in common_set and base not in MANUAL_BLACKLIST and len(base) >= 4:
                if base not in word_pool:
                    word_pool[base] = sentence
    return word_pool

# --- 3. 核心功能：抓取與存檔 ---
def save_to_history(items):
    if not items: return
    file_path = 'history.json'
    today = datetime.now().strftime('%Y-%m-%d')
    daily_record = [{'word': i['word'], 'phonetic': i['phonetic'], 'translation': i['translation']} for i in items]
    history = {}
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except: history = {}
    history[today] = daily_record
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f"--- 歷史紀錄更新完成 ({today}) ---")

def send_weekly_summary():
    """週報功能：含缺漏值防呆"""
    file_path = 'history.json'
    if not os.path.exists(file_path): return
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            history = json.load(f)
    except: return

    today = datetime.now()
    past_7_days = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]
    past_7_days.reverse()

    message = "<b>📊 每週單字複習總匯 (過去 7 天)</b>\n" + "="*20 + "\n\n"
    found_any = False
    for d in past_7_days:
        if d in history:
            found_any = True
            message += f"📅 <b>{d}</b>\n"
            for item in history[d]:
                p = f" {item['phonetic']}" if item['phonetic'] else ""
                message += f"• <code>{item['word']}</code>{p} : {item['translation']}\n"
            message += "\n"
        else:
            message += f"📅 <b>{d}</b>\n⚠️ <i>本日無紀錄</i>\n\n"
    
    if found_any:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                      data={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"})
        print("--- 週報已發送 ---")

def get_news_data():
    url = "https://www.bbc.com/news"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        headlines = list(set([h.get_text().strip() for h in soup.find_all(['h2', 'h3']) if len(h.get_text().strip()) > 15]))
        
        mode = "第一層 (5000字級別)"
        word_pool = filter_vocabulary(headlines, FILTER_5000)
        if len(word_pool) < 10:
            mode = "第二層 (3000字級別)"
            word_pool = filter_vocabulary(headlines, FILTER_3000)

        candidate_keys = list(word_pool.keys())
        print(f"--- 診斷報告 ---\n候選總數: {len(candidate_keys)}\n清單: {candidate_keys}\n---------------")

        if not candidate_keys: return []
        selected_keys = random.sample(candidate_keys, min(len(candidate_keys), 10))
        
        results = []
        translator = GoogleTranslator(source='en', target='zh-TW')
        for word in selected_keys:
            try:
                dict_url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
                d_res = requests.get(dict_url, timeout=5)
                phonetic = d_res.json()[0].get('phonetic', "") if d_res.status_code == 200 else ""
                results.append({
                    'word': word, # 首字不轉大寫
                    'phonetic': phonetic,
                    'translation': translator.translate(word),
                    'context_en': word_pool[word],
                    'context_cn': translator.translate(word_pool[word]),
                    'mode': mode
                })
                time.sleep(0.3)
            except: continue
        return results
    except Exception as e:
        print(f"Error: {e}"); return []

# --- 4. 執行入口 ---
if __name__ == "__main__":
    data = get_news_data()
    if data:
        # 發送今日單字
        mode_info = data[0]['mode']
        message = f"<b>今日時事單字庫 ({mode_info})</b> 🎓\n" + "-"*20 + "\n\n"
        for i, item in enumerate(data, 1):
            p = f" <code>{item['phonetic']}</code>" if item['phonetic'] else ""
            message += f"{i}. <b>{item['word']}</b>{p}\n   🔹 {item['translation']}\n   📝 <i>{item['context_en']}</i>\n   💡 {item['context_cn']}\n\n"
        
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                      data={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"})
        
        # 儲存歷史
        save_to_history(data)
    
    # 週日判定發送週報 (0=Mon, 6=Sun)
    if datetime.now().weekday() == 6:
        send_weekly_summary()
