# Backend Deployment Guide

Panduan ini fokus ke deploy FastAPI backend dulu.

## 1) Persiapan lokal

1. Pastikan backend jalan lokal:
   - Windows: .venv\\Scripts\\python.exe -m uvicorn api_server:app --host 0.0.0.0 --port 8000
   - Linux/macOS: python -m uvicorn api_server:app --host 0.0.0.0 --port 8000
2. Cek health endpoint: GET /api/health
3. Pastikan file dependencies sudah ada di requirements.txt.

## 2) Deploy cepat ke Railway (recommended)

1. Push repo ke GitHub (sudah).
2. Buka Railway > New Project > Deploy from GitHub repo.
3. Pilih service root di folder project ini (root repo).
4. Set environment variables:
   - AVE_API_KEY (required)
   - TELEGRAM_BOT_TOKEN (optional, kalau bot notifikasi dipakai)
   - WEB_APP_URL (optional, untuk deep link ke frontend)
   - API_BASE_URL (optional, isi URL backend production)
5. Start command:
   - uvicorn api_server:app --host 0.0.0.0 --port $PORT
6. Deploy dan tunggu status Healthy.
7. Verifikasi endpoint:
   - /api/health
   - /docs

## 3) Deploy ke Render (alternatif)

1. New Web Service dari repo GitHub.
2. Build Command:
   - pip install -r requirements.txt
3. Start Command:
   - uvicorn api_server:app --host 0.0.0.0 --port $PORT
4. Isi environment variables sama seperti Railway.
5. Save dan deploy.

## 4) Catatan penting produksi

1. alerts.json disimpan sebagai file lokal.
   - Di PaaS umumnya filesystem bisa ephemeral.
   - Untuk produksi stabil, pindahkan storage alert ke database (PostgreSQL/Redis).
2. CORS saat ini allow all di api_server.py.
   - Untuk production, batasi origin ke domain frontend kamu.
3. Pastikan frontend pakai API URL production (VITE_API_BASE).

## 5) Health checks yang disarankan

1. Liveness:
   - GET /api/health
2. Readiness:
   - GET /docs (opsional, untuk cek app mounted)

## 6) Rollback cepat

1. Railway/Render: redeploy dari commit sebelumnya yang stabil.
2. Simpan changelog commit supaya rollback gampang dilacak.
