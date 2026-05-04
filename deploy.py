#!/usr/bin/env python3
"""Cloudflare Pages direct-upload deployment script."""
import os, json, base64, hashlib
import urllib.request, urllib.error

ACCOUNT_ID   = "0b490c60804e0c022a06dea46a8a9e8a"
PROJECT_NAME = "xian-guide"
TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "")
OUT_DIR      = os.path.join(os.path.dirname(__file__), "out")

BASE_URL = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}"

def api(method, path, data=None):
    url = BASE_URL + path
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode()[:500]}")
        raise

# ── 1. collect files + build manifest ───────────────────────────────
print("Collecting files...")
files = []
manifest = {}
for root, dirs, filenames in os.walk(OUT_DIR):
    for fname in filenames:
        fpath = os.path.join(root, fname)
        rel   = os.path.relpath(fpath, OUT_DIR)
        with open(fpath, "rb") as f:
            content = f.read()
        # Cloudflare uses sha256 as etag
        digest = hashlib.sha256(content).hexdigest()
        files.append({"path": rel, "content_b64": base64.b64encode(content).decode()})
        manifest[rel] = {"etag": digest, "size": len(content)}

print(f"  {len(files)} files")

# ── 2. create deployment WITH manifest ─────────────────────────────
print("Creating deployment with manifest...")
dep = api("POST", f"/pages/projects/{PROJECT_NAME}/deployments", {
    "branch": "main",
    "manifest": manifest,
})
if not dep["success"]:
    print("Error:", dep["errors"])
    exit(1)

deployment_id = dep["result"]["id"]
upload_url    = dep["result"]["upload_url"]
print(f"  deployment: {deployment_id}")
print(f"  upload_url: {upload_url}")

# ── 3. upload files to upload_url ──────────────────────────────────
print("Uploading files to storage...")
payload = json.dumps({"files": files}).encode()
req = urllib.request.Request(upload_url, data=payload, method="POST")
req.add_header("Content-Type", "application/json")
try:
    with urllib.request.urlopen(req, timeout=120) as r:
        result = json.loads(r.read())
    print(f"  uploaded {len(result.get('files', []))}/{len(files)} files")
except urllib.error.HTTPError as e:
    print(f"Upload failed: {e.read().decode()[:500]}")
    raise

# ── 4. patch to complete ───────────────────────────────────────────
print("Completing deployment...")
done = api("PATCH",
           f"/pages/projects/{PROJECT_NAME}/deployments/{deployment_id}")
if not done["success"]:
    print("Error:", done["errors"])
    exit(1)

url = done["result"]["url"]
print(f"\n✓ Live!")
print(f"  → https://{url}")
print(f"  → https://{PROJECT_NAME}.pages.dev")
