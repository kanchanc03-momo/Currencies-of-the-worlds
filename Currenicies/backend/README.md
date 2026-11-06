# Currency Atlas backend

Run this from the project root after placing `cleaned_currency_data.csv` there:

```powershell
py -m pip install -r backend/requirements.txt
py -m uvicorn backend.main:app --reload
```

Open the website at `http://127.0.0.1:8000`. Do not open `index.html`
directly; the FastAPI server now serves both the webpage and dataset API.

Endpoints: `/currencies`, `/history/{currency}`, `/forecast/{currency}`, and `/statistics`.
