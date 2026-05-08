import json
import re
from difflib import SequenceMatcher

def load_food_db():
    try:
        with open("food_db.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def calculate_norms(w, h, a, g):
    bmr = (10 * w) + (6.25 * h) - (5 * a) + (5 if g == "Чоловік" else -161)
    calories = round(bmr * 1.2)
    proteins = round(w * 1.8)
    fats = round(w * 0.9)
    carbs = round((calories - (proteins * 4) - (fats * 9)) / 4)
    return {"cal": calories, "p": proteins, "f": fats, "c": carbs}

def find_food_matches(query, db):
    query = query.lower().strip()
    query_words = query.split()
    if not query_words: return []
    
    matches = []
    for item in db:
        name = item["name"].lower()
        name_words = name.split()
        similarity = SequenceMatcher(None, query_words[0], name_words[0]).ratio()
        if similarity > 0.8 or query_words[0] in name:
            matches.append(item)
    return matches

def parse_user_input(text):
    parts = re.split(r'[,+\n]|\s+та\s+|\s+і\s+', text.lower())
    results = []
    for p in parts:
        p = p.strip()
        if not p: continue
        weight_match = re.search(r"(\d+)", p)
        weight = int(weight_match.group(1)) if weight_match else 100
        name = re.sub(r"\d+", "", p).replace("г", "").replace("гр", "").strip()
        if name:
            results.append({"name": name, "weight": weight})
    return results