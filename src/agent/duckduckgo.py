import requests
from bs4 import BeautifulSoup

query = "chagoit"
url = "https://html.duckduckgo.com/html/"
res = requests.post(url, data={"q": query})

soup = BeautifulSoup(res.text, "html.parser")
results = soup.find_all("a", class_="result__a", limit=10)

for r in results:
    print(r.text)
    print(r["href"])
    print("-----")
