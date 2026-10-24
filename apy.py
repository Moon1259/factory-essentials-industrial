import os
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

SHOPIFY_STORE = os.getenv("SHOPIFY_STORE")
SHOPIFY_TOKEN = os.getenv("SHOPIFY_ADMIN_TOKEN")

@app.route("/")
def home():
    return "Factory Essentials Industrial - Service Running! Use /upload to upload products"

@app.route("/upload", methods=["POST"])
def upload_product():
    data = request.json
    if not SHOPIFY_STORE or not SHOPIFY_TOKEN:
        return jsonify({"error": "Missing SHOPIFY_STORE or SHOPIFY_ADMIN_TOKEN env vars"}), 500
    
    # Shopify product create
    url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/products.json"
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_TOKEN,
        "Content-Type": "application/json"
    }
    
    product_data = {
        "product": {
            "title": data.get("title", "New Industrial Spare"),
            "body_html": data.get("description", ""),
            "vendor": data.get("vendor", "Factory Essentials"),
            "product_type": data.get("category", "Industrial"),
            "variants": [{"price": data.get("price", "100.00")}]
        }
    }
    
    r = requests.post(url, json=product_data, headers=headers)
    return jsonify(r.json()), r.status_code

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
