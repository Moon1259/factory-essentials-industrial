import os
import json
import time
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

SHOPIFY_STORE = os.getenv("SHOPIFY_STORE")
SHOPIFY_TOKEN = os.getenv("SHOPIFY_ADMIN_TOKEN")

# Progress file saved in /tmp (survives restarts for 24h on Render)
PROGRESS_FILE = "/tmp/tender_progress.json"

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"total": 0, "uploaded": 0, "failed": 0, "lastSKU": "", "status": "idle", "logs": []}

def save_progress(data):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(data, f)

progress = load_progress()

@app.route("/")
def home():
    return "Factory Essentials Industrial - Service Running! Use /upload to upload 1 product, /upload-batch for 15 products fast, /progress to check"

@app.route("/progress", methods=["GET"])
def get_progress():
    p = load_progress()
    return jsonify(p)

@app.route("/upload", methods=["POST"])
def upload_product():
    data = request.json
    if not SHOPIFY_STORE or not SHOPIFY_TOKEN:
        return jsonify({"error": "Missing SHOPIFY_STORE or SHOPIFY_ADMIN_TOKEN env vars"}), 500

    url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/products.json"
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_TOKEN,
        "Content-Type": "application/json"
    }

    product_data = {
        "product": {
            "title": data.get("title", "New Industrial Spare"),
            "body_html": data.get("body_html", data.get("description", "")),
            "vendor": data.get("vendor", "Factory Essentials"),
            "product_type": data.get("product_type", data.get("category", "Industrial")),
            "tags": data.get("tags", "inventory-visible, policy-continue-ON, iso-9001"),
            "variants": [{
                "price": data.get("price", "100.00"),
                "sku": data.get("sku", ""),
                "inventory_management": "shopify",
                "inventory_quantity": data.get("inventory_quantity", 100),
                "inventory_policy": "continue"
            }],
            "images": [{"src": data.get("image_src", "")}] if data.get("image_src") else []
        }
    }

    r = requests.post(url, json=product_data, headers=headers)
    
    p = load_progress()
    if r.status_code in [200, 201]:
        p["uploaded"] += 1
        p["lastSKU"] = data.get("sku", "")
        p["logs"].append(f"{time.strftime('%H:%M:%S')} - OK {data.get('sku')}")
    else:
        p["failed"] += 1
        p["logs"].append(f"{time.strftime('%H:%M:%S')} - FAIL {data.get('sku')} - {r.text[:100]}")
    p["logs"] = p["logs"][-50:]
    save_progress(p)
    
    return jsonify(r.json()), r.status_code

@app.route("/upload-batch", methods=["POST"])
def upload_batch():
    """Upload 15 items in 1 call - Fixes 15 min sleep issue"""
    global progress
    data = request.json
    items = data.get("products", [])
    
    if not items:
        return jsonify({"error": "Send {\"products\": [15 items]}"}), 400
    
    p = load_progress()
    p["total"] = len(items)
    p["status"] = "running"
    p["logs"].append(f"{time.strftime('%H:%M:%S')} - START batch {len(items)} items")
    save_progress(p)
    
    uploaded = 0
    failed = 0
    
    for idx, item in enumerate(items):
        try:
            url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/products.json"
            headers = {
                "X-Shopify-Access-Token": SHOPIFY_TOKEN,
                "Content-Type": "application/json"
            }
            product_data = {
                "product": {
                    "title": item.get("title", f"Product {idx}"),
                    "body_html": item.get("body_html", ""),
                    "vendor": item.get("vendor", "Factory Essentials"),
                    "product_type": item.get("product_type", "Industrial"),
                    "tags": item.get("tags", ""),
                    "variants": [{
                        "price": str(item.get("price", "100")),
                        "sku": item.get("sku", f"SKU-{idx}"),
                        "inventory_management": "shopify",
                        "inventory_quantity": item.get("inventory_quantity", 100),
                        "inventory_policy": "continue"
                    }],
                    "images": [{"src": item.get("image_src", "")}] if item.get("image_src") else []
                }
            }
            r = requests.post(url, json=product_data, headers=headers, timeout=15)
            
            if r.status_code in [200, 201]:
                uploaded += 1
                p["lastSKU"] = item.get("sku", "")
            else:
                failed += 1
            
            p["uploaded"] = uploaded
            p["failed"] = failed
            p["logs"].append(f"{time.strftime('%H:%M:%S')} - {idx+1}/{len(items)} - {item.get('sku')} - {r.status_code}")
            p["logs"] = p["logs"][-50:]
            save_progress(p)
            
            time.sleep(0.5)
            
        except Exception as e:
            failed += 1
            p["failed"] = failed
            p["logs"].append(f"{time.strftime('%H:%M:%S')} - EXCEPTION {item.get('sku')} - {str(e)[:100]}")
            save_progress(p)
    
    p["status"] = "completed"
    save_progress(p)
    
    return jsonify({
        "total": len(items),
        "uploaded": uploaded,
        "failed": failed,
        "time_taken": "15 items in ~30 seconds, not 15 min",
        "progress_url": "/progress"
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
