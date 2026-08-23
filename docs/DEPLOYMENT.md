# GuardPay — Free Deployment Guide

This guide walks you through deploying **GuardPay** for **100% free** on popular cloud platforms (**Render**, **Vercel**, **Railway**, **Fly.io**, and **Docker**).

---

## 🎯 Quick Comparison — Which Platform to Choose?

| Platform | Best For | Cost | Setup Time | Architecture |
|---|---|---|---|---|
| **Render.com** *(Recommended)* | Full-Stack (Backend + Frontend together) | **Free** | 2 mins | Single Container (`render.yaml`) |
| **Railway.app** | Full-Stack 1-Click Deploy | **Free trial / $5 credit** | 2 mins | Single Container (`Dockerfile`) |
| **Vercel + Render** | Split (Vercel CDN Frontend + Render API) | **Free** | 4 mins | Distributed SPA + API |
| **Fly.io** | CLI-driven container deploy | **Free Tier** | 3 mins | Docker Container |
| **Local Machine** | Pitch video recording & Judge evaluation | **Free** | 30 secs | Local Python + Node |

---

## 🚀 Option 1: 1-Click Full-Stack Deploy on Render.com (Easiest & Recommended)

Render deploys the entire application (FastAPI backend + React SPA frontend) as a single container on a free `https://guardpay.onrender.com` URL with automatic SSL.

### Step-by-Step:
1. **Push your code to GitHub** (Make sure your repo is public or accessible):
   ```bash
   git push origin main
   ```
2. Go to **[Render.com](https://render.com/)** and sign up / log in with your GitHub account.
3. Click **New +** (top right) and select **Blueprint** (or **Web Service**):
   - Select your repository: `drgeekg/GuardPay`.
   - Render will automatically read [`render.yaml`](../render.yaml) and [`Dockerfile`](../Dockerfile).
4. Click **Apply** / **Create Web Service**:
   - **Environment:** `Docker`
   - **Plan:** `Free`
   - **Port:** `8000`
5. **Add Environment Variables** (Optional for test mode):
   - `RAZORPAY_KEY_ID`: `rzp_test_YOUR_KEY`
   - `RAZORPAY_KEY_SECRET`: `YOUR_SECRET`
   - `CLAUDE_API_KEY`: `sk-ant-YOUR_KEY` *(Optional — deterministic fallback works if omitted)*
6. Click **Deploy**. In ~2 minutes, Render will provide your live URL:
   ```
   https://guardpay.onrender.com
   ```
   Open the URL to see the live GuardPay dashboard!

---

## ⚡ Option 2: Split Deploy (Vercel Frontend + Render Backend)

If you prefer hosting the React frontend on **Vercel**'s edge CDN and the backend on **Render**:

### Step A: Deploy Backend on Render
1. In Render, create a **Web Service** from `drgeekg/GuardPay`.
2. Set Build Command: `pip install -r backend/requirements.txt`
3. Set Start Command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
4. Copy your backend URL (e.g., `https://guardpay-backend.onrender.com`).

### Step B: Deploy Frontend on Vercel
1. Go to **[Vercel.com](https://vercel.com/)** and click **Add New > Project**.
2. Select your `drgeekg/GuardPay` repository.
3. In **Project Settings**:
   - **Root Directory:** Edit and select `frontend`.
   - **Framework Preset:** `Vite`.
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`
4. **Environment Variables**:
   - `VITE_API_BASE`: `https://guardpay-backend.onrender.com` (Your Render backend URL).
5. Click **Deploy**. Vercel will launch your frontend on `https://guardpay.vercel.app`!

---

## 🚂 Option 3: Deploy on Railway.app

1. Go to **[Railway.app](https://railway.app/)** and log in with GitHub.
2. Click **New Project > Deploy from GitHub repo**.
3. Select `drgeekg/GuardPay`.
4. Railway will automatically detect the [`Dockerfile`](../Dockerfile).
5. Go to **Settings > Networking > Generate Domain**.
6. Your live dashboard is immediately accessible on your Railway domain!

---

## 🪶 Option 4: Deploy on Fly.io

1. Install the Fly CLI:
   ```powershell
   # Windows (PowerShell):
   iwr https://fly.io/install.ps1 -useb | iex
   ```
2. In the `GuardPay/` root directory, run:
   ```bash
   fly launch
   ```
   Follow the prompts (choose a free app name, region, and accept defaults from `Dockerfile`).
3. Deploy:
   ```bash
   fly deploy
   ```
4. Access your live app at `https://<your-app-name>.fly.dev`.

---

## 💻 Option 5: Local Execution (For 5-Minute Pitch Video)

For recording your demo video or evaluating locally without cloud signup:

### 1. Start the Live Full-Stack App:
```powershell
# In GuardPay repo root:
.\venv\Scripts\python.exe -m uvicorn backend.main:app --port 8000
```
Open **[http://localhost:8000](http://localhost:8000)** in Chrome/Edge.

### 2. Trigger the Attack Simulator:
```powershell
# In a separate terminal:
.\venv\Scripts\python.exe simulator\card_testing_burst.py --target http://localhost:8000
```

---

## ⚙️ Environment Variables Reference

| Variable | Description | Default / Example | Required? |
|---|---|---|---|
| `PORT` | Web server port | `8000` | No |
| `RAZORPAY_KEY_ID` | Razorpay test-mode API key | `rzp_test_...` | Optional (test-mode) |
| `RAZORPAY_KEY_SECRET` | Razorpay webhook signature secret | `...` | Optional |
| `CLAUDE_API_KEY` | Anthropic Claude API key for AI dossier | `sk-ant-...` | Optional (fallback active) |
| `VELOCITY_TXN_PER_CARD_PER_MIN` | Card-testing threshold | `10` | No |
| `VELOCITY_BIN_CLUSTER_THRESHOLD` | BIN rotation threshold | `5` | No |
| `VELOCITY_SUBNET_CLUSTER_THRESHOLD`| Subnet flood threshold | `8` | No |
| `VELOCITY_WINDOW_SECONDS` | Rolling window duration | `60` | No |

---

## ✅ Deployment Verification Checklist

Once deployed to any platform above:
- [ ] Visit `/health` → returns `200 {"status": "ok"}`
- [ ] Visit `/` → renders GuardPay AI Risk Desk React UI
- [ ] Visit `/metrics/summary` → returns 500-sample precision/recall stats
- [ ] Click **Card-Testing Burst** on dashboard → generates live incident alert & dossier
- [ ] Click **Auto-Block Subnet** → records 24h mitigation in `/audit-log`
- [ ] Click **Undo Action** in audit trail → reverses policy immediately
