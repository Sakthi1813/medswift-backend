# MedSwift - Urgent Rescue Alert System

## To Run

```bash
cd C:\Users\VAIBHAVRAI\OneDrive\Desktop\C702
pip install -r requirements.txt
python app.py
```

Open browser: http://localhost:5000

## IMPORTANT - Firebase Setup Required

1. Go to https://console.firebase.google.com
2. Create project named `medswift-app`
3. Enable Authentication > Email/Password + Google sign-in
4. Create Firestore database (test mode)
5. Project Settings > Service Accounts > Generate private key > save as `firebase-credentials.json` in this folder
6. Project Settings > General > Your apps > Web app > copy config values
7. Paste those values into `firebase_config.py` (replace the placeholder values)

## API Keys (already set in .env)

- Gemini: AIzaSyC4U40FohFsirOAvhkABUYn8G92WR4zy1U
- OpenRouteService: configured
- SMTP: ayushtiwari.creatorslab@gmail.com

## Hospital Dataset (Optional Upgrade)

1. Download from https://www.kaggle.com/datasets/nehaprabhavalkar/indian-hospitals-data
2. Open notebooks/hospital_processing.ipynb in Google Colab
3. Run all cells, download output hospitals.csv
4. Replace data/hospitals.csv with the downloaded file

System has 40+ hospitals pre-loaded as fallback.
