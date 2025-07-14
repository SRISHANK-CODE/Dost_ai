from flask import Flask, request, jsonify, render_template
import json
import os
from datetime import datetime
import wikipedia
import requests
import re
import logging
import difflib
from googlesearch import search

# Optional: Import other modules if using Google Calendar
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ========== CONFIG ==========
app = Flask(__name__)

SERP_API_KEY = "0578129080830a24f56142941516c3579cd6d538b428c9107c60b611594a9029"
WEATHER_API_KEY = "fff1cfc7063bdc874d8d6db27ba81495"
NEWS_API_KEY = "d5916ac487834fadba8f73fe08c3953c"
SCOPES = ['https://www.googleapis.com/auth/calendar.events']
CACHE_FILE = "data/cache.json"
HISTORY_FILE = "data/chat_history.json"
CORRECTIONS_FILE = "data/corrections.json"
STATS_FILE = "data/question_stats.json"
REMINDERS_FILE = "data/reminders.json"
BROWSER_HISTORY_FILE = "data/browser_history.json"

# ========== STATE ==========
cache = {}
chat_history = []
question_stats = {}
user_corrections = {}
reminders = []
browser_history = []

# ========== LOGGING ==========
LOG_FILE = "data/assistant.log"
logging.basicConfig(filename=LOG_FILE, level=logging.INFO)

# ========== LOAD SAVED DATA ==========
for file_path, target_dict in [
    (CACHE_FILE, cache),
    (CORRECTIONS_FILE, user_corrections),
    (STATS_FILE, question_stats),
    (REMINDERS_FILE, reminders),
    (BROWSER_HISTORY_FILE, browser_history)
]:
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            try:
                if file_path == REMINDERS_FILE:
                    loaded = json.load(f)
                    reminders.extend([(task, datetime.fromisoformat(time)) for task, time in loaded])
                elif file_path == BROWSER_HISTORY_FILE:
                    browser_history.extend(json.load(f))
                else:
                    target_dict.update(json.load(f))
            except:
                logging.error(f"Failed to load {file_path}")

# ========== HELPER FUNCTIONS ==========
def speak(text):
    return text  # Placeholder (TTS removed for web)

def greet():
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning! I'm ready to assist you today!"
    elif hour < 18:
        return "Good afternoon! What's on your mind?"
    else:
        return "Good evening! How can I make your night better?"

def farewell():
    return "Goodbye! Have a great day!"

def extract_city(query):
    match = re.search(r"in (.+)", query.lower())
    return match.group(1).strip() if match else "Karimnagar"

def get_local_weather(query):
    city = extract_city(query)
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
        response = requests.get(url)
        data = response.json()
        if data.get("cod") != 200:
            return "I couldn't get the weather info right now."
        temp = data["main"]["temp"]
        condition = data["weather"][0]["description"]
        humidity = data["main"]["humidity"]
        return f"In {city.title()}, it's {temp}°C with {condition}. Humidity is {humidity}%."
    except Exception as e:
        logging.error(f"Weather API error: {e}")
        return "Sorry, I couldn't fetch weather details."

def get_news():
    try:
        url = f"https://newsapi.org/v2/top-headlines?country=us&apiKey={NEWS_API_KEY}"
        response = requests.get(url)
        data = response.json()
        if data.get("status") != "ok":
            return "I couldn't fetch the news right now."
        articles = data["articles"][:3]
        news_summary = "Here are the top news headlines: "
        for i, article in enumerate(articles, 1):
            news_summary += f"{i}. {article['title']} from {article['source']['name']}. "
        return news_summary
    except Exception as e:
        logging.error(f"News API error: {e}")
        return "Sorry, I couldn't fetch the news."

def search_wikipedia(query):
    try:
        wikipedia.set_lang("en")
        results = wikipedia.search(query)
        if not results:
            return None
        return wikipedia.summary(results[0], sentences=2)
    except Exception as e:
        logging.error(f"Wikipedia error: {e}")
        return None

def search_serpapi(query):
    try:
        url = "https://serpapi.com/search"
        params = {
            "q": query,
            "api_key": SERP_API_KEY,
            "engine": "google",
            "num": 1
        }
        response = requests.get(url, params=params)
        data = response.json()
        if "answer_box" in data:
            box = data["answer_box"]
            return box.get("answer") or box.get("snippet") or box.get("definition")
        if "organic_results" in data:
            return data["organic_results"][0].get("snippet")
    except Exception as e:
        logging.error(f"SerpAPI error: {e}")
        return None

def enhanced_search(query):
    try:
        for url in search(query, num_results=3):
            return f"Here's something I found: {url}"
        return "I couldn't find anything relevant."
    except Exception as e:
        logging.error(f"Web search error: {e}")
        return "Error performing search."

def ask_assistant(query):
    query = query.strip().lower()

    # Handle greetings
    if any(greet_word in query for greet_word in ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"]):
        response = greet()

    # Handle identity
    elif "who made you" in query or "who created you" in query:
        response = "I was created by Srishank."

    # Farewell
    elif "bye" in query or "exit" in query or "quit" in query:
        response = farewell()

    # Weather
    elif "weather" in query:
        response = get_local_weather(query)

    # News
    elif "news" in query:
        response = get_news()

    # General info
    else:
        response = search_serpapi(query)
        if not response:
            response = search_wikipedia(query)
        if not response:
            response = enhanced_search(query)
        if not response:
            response = "I'm not sure, but that's an interesting question!"

    cache[query] = response
    chat_history.append((query, response))
    return response

# ========== ROUTES ==========
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def handle_query():
    query = request.json.get("query", "")
    response = ask_assistant(query)
    return jsonify({"response": response})

@app.route("/shutdown", methods=["POST"])
def shutdown():
    save_data()
    return jsonify({"status": "saved"})

# ========== RUN ==========
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
