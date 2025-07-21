# 🏠 Home Enquiry Web App

A Python Flask web app that:
- Reads data from a private Google Sheet using a Service Account.
- Displays mobile numbers grouped by lead status.
- Allows drag-and-drop to move leads between status lists.
- Saves updated statuses back to the Google Sheet.

---

## 🚀 Features

- Six lead stages: Inbound, Contacted, Response Received, Prospect, In Negotiation, Onboarded.
- Name and phone number shown for each entry.
- Drag-and-drop interaction using Sortable.js.
- Google Sheets integration with read/write access.

---

## 📦 Project Setup (Using `uv`)

### 1. Install `uv`

If not already installed:

```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Create virtual environment and install dependencies

```
cd home_enquiry_app
uv venv
uv pip install flask pandas google-api-python-client google-auth
```

### 3. Add your Google Sheet credentials

Place your `service_account.json` in the root folder.

Share the Google Sheet with your service account's email (e.g., `xxxx@project.iam.gserviceaccount.com`).

### 4. Configure Spreadsheet ID

Open `app.py` and replace:

```python
SPREADSHEET_ID = 'YOUR_SPREADSHEET_ID'
```

with your actual Google Sheet ID (found in the URL).

### 5. Run locally

```
python app.py
```

App will be available at `http://127.0.0.1:5000`

---

## 🌐 Deploy to Render

### 1. Push code to GitHub

Include all files and folders in this project.

### 2. Create a Web Service on Render

- Go to [https://dashboard.render.com](https://dashboard.render.com)
- Click **New > Web Service**
- Connect your GitHub repo
- Use these settings:

```
Build Command:      pip install -r requirements.txt
Start Command:      gunicorn app:app
Python Version:     3.10+
```

### 3. Configure Environment

- Upload `service_account.json` as a **Secret File**
- Set environment variable: `SPREADSHEET_ID` = your sheet ID

### 4. Done!

Render will build and deploy your app live. Test functionality at your public URL.

---

## 📁 Folder Structure

```
home_enquiry_app/
├── app.py
├── service_account.json      # <-- Not included in repo; add manually
├── templates/
│   └── index.html
├── static/
│   └── sortable.min.js       # Include actual SortableJS script
├── pyproject.toml
├── README.md
```

---

## 🧰 Built With

- Flask
- Google Sheets API
- Bootstrap 5
- Sortable.js (drag and drop)
- uv (Python dependency manager)

---

## ✍️ Author

Vinod Nair (with help from ChatGPT 🚀)