#!/usr/bin/env python3
"""Cloudflare Pages deployment script for Guide Me Xian."""
import os, json, base64, hashlib, urllib.request, urllib.error

ACCOUNT_ID   = "0b490c60804e0c022a06dea46a8a9e8a"
PROJECT_NAME = "guideme-xian"
TOKEN        = os.environ.get("CLOUDFLARE_API_TOKEN", "")
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
        body_bytes = e.read()
        print(f"HTTP {e.code}: {body_bytes.decode()[:500]}")
        raise

# ── 1. collect files ─────────────────────────────────────────────
print("Collecting files...")
files = []
manifest = {}
for root, dirs, filenames in os.walk(OUT_DIR):
    for fname in filenames:
        fpath = os.path.join(root, fname)
        rel   = os.path.relpath(fpath, OUT_DIR)
        with open(fpath, "rb") as f:
            content = f.read()
        digest = hashlib.sha256(content).hexdigest()
        files.append({"path": rel, "content_b64": base64.b64encode(content).decode()})
        manifest[rel] = {"etag": digest, "size": len(content)}

print(f"  {len(files)} files, {sum(m['size'] for m in manifest.values()):,} bytes total")

# ── 2. create deployment ───────────────────────────────────────────
print("Creating deployment with manifest...")
dep = api("POST", f"/pages/projects/{PROJECT_NAME}/deployments", {
    "branch": "main",
    "manifest": manifest,
})
if not dep["success"]:
    print("Error:", dep["errors"])
    exit(1)

deployment_id = dep["result"]["id"]
upload_url     = dep["result"]["upload_url"]
print(f"  deployment: {deployment_id}")
print(f"  upload_url: {upload_url}")

# ── 3. upload files in batches ─────────────────────────────────────
print(f"Uploading {len(files)} files...")
batch_size = 20
for i in range(0, len(files), batch_size):
    batch = files[i:i+batch_size]
    upload = api("POST", upload_url, {"files": batch})
    if not upload["success"]:
        print(f"  Upload error at batch {i//batch_size}:", upload["errors"])
        exit(1)
    print(f"  batch {i//batch_size + 1}/{(len(files)-1)//batch_size + 1}: {len(batch)} files")

# ── 4. trigger build ───────────────────────────────────────────────
print("Triggering build...")
build = api("PATCH", f"/pages/projects/{PROJECT_NAME}/deployments/{deployment_id}", {
    "stage": "build",
})
if not build["success"]:
    print("Build trigger error:", build["errors"])

# Wait for deployment
print("\nFetching deployment status...")
import time
for attempt in range(12):
    time.sleep(10)
    status = api("GET", f"/pages/projects/{PROJECT_NAME}/deployments/{deployment_id}")
    if status["success"]:
        st = status["result"]["status"]
        print(f"  [{attempt+1}] status: {st}")
        if st in ("success", "failure", "canceled"):
            break
    else:
        print(f"  [{attempt+1}] failed to get status")

url = status["result"]["url"] if status["success"] else "unknown"
print(f"\nDeployment URL: {url}")
print(f"Project: https://{PROJECT_NAME}.pages.dev")
