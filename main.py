import requests
import smtplib
import datetime
import base64
import csv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from bs4 import BeautifulSoup
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# === CONFIGURATION ===
SOURCES = [
    "https://techcrunch.com/tag/artificial-intelligence/",
    "https://venturebeat.com/category/ai/",
    "https://www.reddit.com/r/MachineLearning/",
    "https://www.reddit.com/r/ArtificialInteligence/",
    "https://www.reddit.com/r/LocalLLaMA/",
    "https://github.com/trending?since=daily",
    "https://huggingface.co/models",
    "https://arxiv.org/list/cs.AI/recent",
    "https://arxiv.org/list/cs.LG/recent",
    "https://arxiv.org/list/cs.CL/recent"
]

HEADERS = {"User-Agent": "Mozilla/5.0"}
NB_INFOS = 5  # Limité à 5 actus
HTML_OUTPUT_PATH = "hauban_ai_watch_report.html"
TOGETHER_API_KEY = "tgp_v1_SqShGD9hKF8X5dOXKX7fvyBwjVaChBBaS6f50Jij5RU"
TOGETHER_MODEL = "mistralai/Mixtral-8x7B-Instruct-v0.1"
MAILJET_API_KEY = "e51d0fef891dc4ba270077871341767c"
MAILJET_SECRET_KEY = "2041777d4c316f65e38596d73e709b32"
EMAIL_FROM = "spectramediabots@gmail.com"
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1-JLDxbW5RQukZk4o_imik0UsjIMI-bgrRlnNNyzicpo"
SERVICE_ACCOUNT_FILE = "google-credentials.json"

# === FONCTIONS ===

def fetch_url(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Erreur sur {url}: {e}")
        return ""

def extract_info():
    results = []
    today = datetime.datetime.now()
    seven_days_ago = today - datetime.timedelta(days=7)

    for url in SOURCES:
        html = fetch_url(url)
        soup = BeautifulSoup(html, "html.parser")

        if "techcrunch" in url:
            articles = soup.select("a.post-block__title__link")
            for a in articles:
                if len(results) < NB_INFOS:
                    results.append({"source": "TechCrunch", "title": a.text.strip(), "url": a['href']})

        elif "venturebeat" in url:
            articles = soup.select("h2 a")
            for a in articles:
                if a and a.text and len(results) < NB_INFOS:
                    results.append({"source": "VentureBeat", "title": a.text.strip(), "url": a['href']})

        elif "reddit.com" in url:
            posts = soup.select("h3")
            for post in posts:
                if len(results) < NB_INFOS:
                    title = post.text.strip()
                    results.append({"source": "Reddit", "title": title, "url": url})

        elif "github.com" in url:
            repos = soup.select("article h2 a")
            for repo in repos:
                if len(results) < NB_INFOS:
                    full_url = f"https://github.com{repo['href']}"
                    results.append({"source": "GitHub Trending", "title": repo.text.strip(), "url": full_url})

        elif "huggingface.co" in url:
            models = soup.select("a.styles_modelCard__fKzfZ")
            for model in models:
                if len(results) < NB_INFOS:
                    results.append({"source": "HuggingFace", "title": model.text.strip(), "url": f"https://huggingface.co{model['href']}"})

        elif "arxiv.org" in url:
            titles = soup.select("dd > div.list-title.mathjax")
            links = soup.select("dt > span.list-identifier a[title='Abstract']")
            for t, l in zip(titles, links):
                if len(results) < NB_INFOS:
                    results.append({
                        "source": "ArXiv",
                        "title": t.text.replace("Title:", "").strip(),
                        "url": f"https://arxiv.org{l['href']}"
                    })

        if len(results) >= NB_INFOS:
            break

    return results[:NB_INFOS]

def summarize_text(text):
    prompt = f"Résume en français cette actualité IA en trois lignes : {text}"
    try:
        response = requests.post(
            "https://api.together.xyz/inference",
            headers={"Authorization": f"Bearer {TOGETHER_API_KEY}"},
            json={
                "model": TOGETHER_MODEL,
                "prompt": prompt,
                "max_tokens": 256,
                "temperature": 0.7,
                "top_p": 0.9
            },
            timeout=30
        )
        data = response.json()
        return data["choices"][0]["text"].strip()
    except Exception as e:
        print("Erreur Together AI:", e)
        return "Résumé indisponible."

def generate_html_report(data):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    html = f"<html><head><meta charset='UTF-8'><title>Hauban IA Watch</title></head><body>"
    html += f"<h1>Rapport Hauban IA Watch – {now}</h1><ul>"

    for item in data:
        summary = summarize_text(item['title'])
        html += f"<li><b>[{item['source']}]</b> <a href='{item['url']}'>{item['title']}</a><br/>{summary}</li><br/>"

    html += "</ul></body></html>"

    with open(HTML_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print("✅ Rapport généré :", HTML_OUTPUT_PATH)

def get_emails_from_google_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_url(GOOGLE_SHEET_URL).sheet1
    emails = sheet.col_values(1)
    return [email for email in emails if "@" in email]

def send_email(file_path, recipients):
    with open(file_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    for email_to in recipients:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_FROM
        msg['To'] = email_to
        msg['Subject'] = "Votre rapport Hauban IA Watch"
        msg.attach(MIMEText(html_content, "html"))

        try:
            with smtplib.SMTP('in-v3.mailjet.com', 587) as server:
                server.starttls()
                server.login(MAILJET_API_KEY, MAILJET_SECRET_KEY)
                server.sendmail(EMAIL_FROM, email_to, msg.as_string())
            print(f"📧 Email envoyé à {email_to} !")
        except Exception as e:
            print(f"Erreur envoi à {email_to}:", e)

# === LANCEMENT ===
if __name__ == "__main__":
    infos = extract_info()
    generate_html_report(infos)
    emails = get_emails_from_google_sheet()
    send_email(HTML_OUTPUT_PATH, emails)
