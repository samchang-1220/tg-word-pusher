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
import json
from datetime import datetime

# --- 環境初始化 ---
for pkg in ['wordnet', 'averaged_perceptron_tagger', 'averaged_perceptron_tagger_eng', 
            'omw-1.4', 'punkt', 'punkt_tab', 'maxent_ne_chunker', 'maxent_ne_chunker_tab', 'words']:
    nltk.download(pkg, quiet=True)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def save_to_history(items):
    if not items:
        return
    
    file_path = 'history.json'
    # 取得今天日期 (格式如 2023-10-27)
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 準備今天要儲存的資料格式
    daily_record = []
    for item in items:
        daily_record.append({
            'word': item['word'],
            'phonetic': item['phonetic'],
            'translation': item['translation']
        })

    # 讀取現有的歷史紀錄
    history = {}
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except:
            history = {}

    # 更新或覆蓋當天的資料
    history[today] = daily_record

    # 寫回檔案 (indent=2 讓 JSON 好讀，ensure_ascii=False 確保中文不亂碼)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    
    print(f"--- 歷史紀錄更新完成 ({today}) ---")

def get_manual_blacklist():
    blacklist = set()
    file_path = 'blacklist.txt'
    
    # 內建絕對排除
    internal_list = {'why', 'how', 'what', 'herself', 'himself'}
    blacklist.update(internal_list)
    
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    # 先去除空白與註釋
                    clean_line = line.strip().lower()
                    if not clean_line or clean_line.startswith('#'):
                        continue
                    
                    # 關鍵：同時處理「逗號分隔」與「空格分隔」
                    # 先把逗號換成空格，再用 split() 切開
                    words = clean_line.replace(',', ' ').split()
                    for w in words:
                        blacklist.add(w.strip())
            print(f"成功載入 {len(blacklist)} 個黑名單單字。")
        except Exception as e:
            print(f"讀取失敗: {e}")
    return blacklist

# 在主邏輯中調用
MANUAL_BLACKLIST = get_manual_blacklist()

def get_common_words(limit=5000):
    try:
        url = "https://raw.githubusercontent.com/first20hours/google-10000-english/master/google-10000-english-no-swears.txt"
        res = requests.get(url, timeout=10)
        return res.text.lower().splitlines()[:limit]
    except: return []

# 預載入兩個等級的過濾器
ALL_WORDS_SOURCE = get_common_words(5000)
FILTER_5000 = set(ALL_WORDS_SOURCE)
FILTER_3000 = set(ALL_WORDS_SOURCE[:3000])
lemmatizer = WordNetLemmatizer()

def lemmatize_word(word):
    try:
        tag = pos_tag([word])[0][1]
        tag_dict = {"J": wordnet.ADJ, "N": wordnet.NOUN, "V": wordnet.VERB, "R": wordnet.ADV}
        return lemmatizer.lemmatize(word, tag_dict.get(tag[0].upper(), wordnet.NOUN))
    except: return word

def filter_vocabulary(headlines, common_set):
    """通用的單字篩選邏輯"""
    word_pool = {}
    person_names = set()

    for sentence in headlines:
        # NER 辨識人名與地名
        tokens = word_tokenize(sentence)
        for chunk in ne_chunk(pos_tag(tokens)):
            if hasattr(chunk, 'label') and chunk.label() in ['PERSON', 'GPE', 'ORGANIZATION']:
                for leaf in chunk: person_names.add(leaf[0].lower())

        # 抓取 4 個字母以上的純英文字單字
        raw_words = re.findall(r'\b[a-zA-Z]{4,}\b', sentence)
        for rw in raw_words:
            word_clean = rw.lower().strip("'\"") # 徹底清除引號
            
            if word_clean in person_names or word_clean in common_set or word_clean in MANUAL_BLACKLIST:
                continue
            
            base = lemmatize_word(word_clean)
            if base not in common_set and base not in MANUAL_BLACKLIST and len(base) >= 4:
                if base not in word_pool:
                    word_pool[base] = sentence
    return word_pool

def get_news_data():
    url = "https://www.bbc.com/news"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        headlines = list(set([h.get_text().strip() for h in soup.find_all(['h2', 'h3']) if len(h.get_text().strip()) > 15]))
        
        # --- 第一層：5000 字過濾 ---
        current_mode = "第一層 (5000字級別)"
        word_pool = filter_vocabulary(headlines, FILTER_5000)

        # --- 第二層：如果不到 10 個，改用 3000 字過濾 ---
        if len(word_pool) < 10:
            current_mode = "第二層 (3000字級別 - 難詞不足自動降級)"
            word_pool = filter_vocabulary(headlines, FILTER_3000)

        candidate_keys = list(word_pool.keys())
        
        # --- Debug 機制：秀出所有抓到的單字 ---
        print(f"--- 系統診斷報告 ---")
        print(f"當前模式: {current_mode}")
        print(f"標題總數: {len(headlines)}")
        print(f"候選單字總數: {len(candidate_keys)}")
        print(f"完整候選清單: {candidate_keys}")
        print(f"--------------------")

        if not candidate_keys: return []

        selected_keys = random.sample(candidate_keys, min(len(candidate_keys), 10))
        results = []
        translator = GoogleTranslator(source='en', target='zh-TW')
        
        for word in selected_keys:
            try:
                dict_url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
                phonetic = ""
                d_res = requests.get(dict_url, timeout=5)
                if d_res.status_code == 200:
                    phonetic = d_res.json()[0].get('phonetic', "")

                results.append({
                    'word': word,
                    'phonetic': phonetic,
                    'translation': translator.translate(word),
                    'context_en': word_pool[word],
                    'context_cn': translator.translate(word_pool[word]),
                    'mode': current_mode # 紀錄來源模式
                })
                time.sleep(0.3)
            except: continue
        return results
    except Exception as e:
        print(f"Error: {e}"); return []

def send_to_telegram(items):
    if not items: return
    mode_info = items[0]['mode']
    message = f"<b>今日時事單字庫 ({mode_info})</b> 🎓\n" + "-"*20 + "\n\n"
    for i, item in enumerate(items, 1):
        p = f" <code>{item['phonetic']}</code>" if item['phonetic'] else ""
        message += f"{i}. <b>{item['word']}</b>{p}\n   🔹 {item['translation']}\n   📝 <i>{item['context_en']}</i>\n   💡 {item['context_cn']}\n\n"

    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                  data={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"})

if __name__ == "__main__":
    data = get_news_data()
    if data:
        send_to_telegram(data)
        save_to_history(data)
