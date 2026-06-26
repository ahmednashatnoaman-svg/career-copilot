# Deployment Guide

## Architecture

```
User Browser
     │
     ▼
[Vercel] Next.js Frontend
     │  NEXT_PUBLIC_API_BASE
     ▼
[Render] FastAPI Backend
     │              │
     ▼              ▼
[Supabase]      [Qdrant Cloud]
Postgres + Auth  Vector DB
```

---

## Step 1: Supabase (Postgres + Auth)

1. Go to **supabase.com** → Create new project (free)
2. Copy your **Project URL** and **anon key** from: Settings → API
3. Copy your **Service Role key** (backend uses this)
4. Go to **SQL Editor** → New query → paste `supabase-schema.sql` → Run
5. Enable Google OAuth (optional): Authentication → Providers → Google
6. Copy **Database URL**: Settings → Database → Connection string → "Transaction" mode

**Keys you need:**
```
SUPABASE_URL=https://xxxx.supabase.co          ← project Settings → API
SUPABASE_SERVICE_ROLE_KEY=...                   ← project Settings → API (secret!)
NEXT_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=...              ← project Settings → API
DATABASE_URL=postgresql://postgres.xxx:pw@...   ← project Settings → Database
```

---

## Step 2: Qdrant Cloud (Vector DB)

1. Go to **cloud.qdrant.io** → Create free cluster (1GB)
2. Choose region closest to your Render region (Oregon → us-west)
3. Wait ~3 minutes for cluster to provision
4. Copy **Cluster URL** and **API Key**

**Keys you need:**
```
QDRANT_URL=https://xxxx.us-west-2.aws.cloud.qdrant.io:6333
QDRANT_API_KEY=your-qdrant-api-key
```

---

## Step 3: Backend → Render

1. Go to **render.com** → New → Web Service
2. Connect your GitHub repo (`ahmednashatnoaman-svg/career-copilot`)
3. Settings:
   - **Name**: `career-copilot-api`
   - **Root Directory**: _(leave empty — render.yaml at root)_
   - **Runtime**: Docker
   - **Dockerfile Path**: `./backend/Containerfile`
   - **Docker Context**: `.`
   - **Plan**: Free
4. Add Environment Variables (from your `.env`):
   - `GROQ_API_KEY`
   - `TAVILY_API_KEY`
   - `DATABASE_URL` (Supabase connection string)
   - `QDRANT_URL` (Qdrant Cloud URL)
   - `QDRANT_API_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `FRONTEND_URL` (your Vercel URL, set after Step 4)

   - `LANGCHAIN_API_KEY`
5. Click **Create Web Service**
6. Copy your Render URL: `https://career-copilot-api.onrender.com`

**GitHub Secret for CI/CD:**
- Go to Render → Service → Settings → Deploy Hook → copy the URL
- Add to GitHub: Settings → Secrets → `RENDER_DEPLOY_HOOK_URL`
- Also add: `RENDER_BACKEND_URL=https://career-copilot-api.onrender.com`

---

## Step 4: Frontend → Vercel

1. Go to **vercel.com** → New Project → Import from GitHub
2. Select `ahmednashatnoaman-svg/career-copilot`
3. Settings:
   - **Framework**: Next.js (auto-detected)
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Install Command**: `npm ci`
4. Add Environment Variables:
   - `NEXT_PUBLIC_SUPABASE_URL` (from Step 1)
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY` (from Step 1)
   - `NEXT_PUBLIC_API_BASE` = `https://career-copilot-api.onrender.com`
5. Click **Deploy**
6. Copy your Vercel URL: `https://career-copilot.vercel.app`
7. **Go back to Render** and set `FRONTEND_URL` to your Vercel URL

**GitHub Secrets for CI/CD:**
- `VERCEL_TOKEN` — Vercel dashboard → Settings → Tokens
- `VERCEL_ORG_ID` — from `.vercel/project.json` after `vercel link`
- `VERCEL_PROJECT_ID` — same file

To get `VERCEL_ORG_ID` and `VERCEL_PROJECT_ID`:
```bash
cd frontend
npx vercel link
cat .vercel/project.json
```

---

## Step 5: Vercel OAuth Callback (if using Google sign-in)

In Supabase → Authentication → URL Configuration:
- **Site URL**: `https://career-copilot.vercel.app`
- **Redirect URLs**: `https://career-copilot.vercel.app/auth/callback`

---

## Local Development

```bash
# 1. Copy env files
cp .env.example .env              # fill in keys
cp frontend/.env.local.example frontend/.env.local  # fill in Supabase keys

# 2. Start infra
podman-compose -f infra/compose.yaml up -d    # local Postgres + Qdrant

# 3. Run migrations
uv run alembic upgrade head

# 4. Start backend
uv run uvicorn app.main:app --reload

# 5. Start frontend
cd frontend && npm run dev
```

---

## GitHub Actions Secrets Summary

Add all of these in: GitHub repo → Settings → Secrets and variables → Actions

| Secret | Where to get it |
|--------|-----------------|
| `VERCEL_TOKEN` | vercel.com → Account Settings → Tokens |
| `VERCEL_ORG_ID` | `frontend/.vercel/project.json` after `vercel link` |
| `VERCEL_PROJECT_ID` | same file |
| `RENDER_DEPLOY_HOOK_URL` | Render → Service → Settings → Deploy Hook |
| `RENDER_BACKEND_URL` | your Render service URL |
