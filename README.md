# RSSB Bhayander Dera - Fan Dashboard (Streamlit)

## Run
    pip install -r requirements.txt
    streamlit run app.py

Open the URL it prints (http://localhost:8501). To use it from phones on the same Wi-Fi, open
http://<your-computer-IP>:8501.

## Optional PIN
    ACCESS_PIN=1234 streamlit run app.py          (Mac/Linux)
    set ACCESS_PIN=1234 && streamlit run app.py   (Windows)
Or create `.streamlit/secrets.toml` containing:  ACCESS_PIN = "1234"

## Data
All reports are saved to `data.json` next to app.py (change with the DATA_FILE environment variable).
Every browser shares it and the screen refreshes itself every 5 seconds.

## Put it online
Push this folder to GitHub and deploy on Streamlit Community Cloud. Note: its disk resets on restart,
so use a host with a persistent disk (Render, a VPS) if you need reports to survive.
