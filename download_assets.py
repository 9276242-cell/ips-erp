import urllib.request
import os
import ssl

static_dir = os.path.join(os.path.dirname(__file__), "backend", "app", "static")
os.makedirs(static_dir, exist_ok=True)

assets = {
    "tailwind.min.css": "https://cdnjs.cloudflare.com/ajax/libs/tailwindcss/2.2.19/tailwind.min.css",
    "chart.min.js": "https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"
}

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

for filename, url in assets.items():
    dest = os.path.join(static_dir, filename)
    print(f"Downloading {url} to {dest}...")
    try:
        with urllib.request.urlopen(url, context=ctx) as response:
            with open(dest, "wb") as f:
                f.write(response.read())
        print(f"Successfully downloaded {filename}")
    except Exception as e:
        print(f"Failed to download {filename}: {e}")
