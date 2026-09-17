import urllib.request
from urllib.error import URLError

urllib.request.urlopen("http://localhost:8080/api/health", timeout=5).read()
