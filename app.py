from flask import Flask, render_template, request, jsonify, redirect, url_for
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import os

app = Flask(__name__)

SPREADSHEET_ID = '1Yv1gxQdbc5Aq4bo1CMnCAeVMvarltkryPzE4W96DtNw'
RANGE_NAME = 'Home Enquiry Responses'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT_FILE = 'service_account.json'

STATUSES = [
    'Inbound', 'Contacted', 'Response Received', 'Prospect',
    'In Negotiation', 'Onboarded', 'Dropped'
]

FILTERTEXT = {
    'Inbound':'',
    'Contacted':'Enquiry',
    'Response Received':'Spotting',
    'Prospect':'Prospect',
    'In Negotiation':'Docking',
    'Onboarded':'Boarded',
    'Dropped':'Dropped'
}
SAVE_COLUMNS = ['Contacted'	,'Response'	,'Floor'	,'Status']

CSV_FILE = "output.csv"

script_dir = os.path.dirname(__file__)

def get_sheet_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build('sheets', 'v4', credentials=creds)

def fetch_sheet_data():
    service = get_sheet_service()
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
    values = result.get('values', [])

    if not values or len(values) < 2:
        return pd.DataFrame()

    df = pd.DataFrame(values[1:], columns=values[0])
    df.columns = [c.strip() for c in df.columns]
    df.to_csv(CSV_FILE, index=False)
    return df

def read_data():
    if os.path.exists(CSV_FILE) == False:
        fetch_sheet_data()
    df = pd.read_csv(CSV_FILE)
    return df

def save_data(df):
    df.to_csv(CSV_FILE, index=False)

def update_sheet_data(mobile, dt):
    df = read_data()
    row = df.loc[(df["You can reach me on (Mobile Number)"].str.lower() == mobile.lower()) & (df["Timestamp"].str.lower() == dt.lower())]
    row = row.fillna('')
    values = [row.columns.tolist()] + row.values.tolist()
    service = get_sheet_service()
    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_NAME,
        valueInputOption="RAW",
        body={"values": values}
    ).execute()

@app.route("/fetch", methods=["GET"])
def fetch():
    df = fetch_sheet_data()
    return redirect(url_for('index')) 


@app.route("/")
def index():    
    df = read_data()
    views = {}
    for status in STATUSES:
        if FILTERTEXT[status] == '':
            filtered = df[df["Status"].isnull()]
        else:
            filtered = df[df["Status"].str.strip().str.lower() == FILTERTEXT[status].lower()]
        entries = filtered[["Your Name", "You can reach me on (Mobile Number)", "Timestamp"]].dropna().values.tolist()
        views[status] = [{"Your Name": n, "You can reach me on (Mobile Number)": m, "Timestamp": o} for n, m, o in entries]
    return render_template("index.html", views=views, statuses=STATUSES, filters=FILTERTEXT)

@app.route("/save", methods=["POST"])
def save():
    data = request.json.get("data", [])
    update_sheet_data(data)
    return jsonify({"status": "success"})

@app.route("/edit", methods=["GET", "POST"])
def edit():
    df = read_data()
    rowid = request.args.get("rowid")
    mobile = rowid.split("__")[0]
    dt = rowid.split("__")[1]

    row = df.loc[(df["You can reach me on (Mobile Number)"].str.lower() == mobile.lower()) & (df["Timestamp"].str.lower() == dt.lower())]
    row = row.fillna('')
    initialResponse = ""
    closeResponse = ""

    with open(os.path.join(script_dir, 'intialResponse.txt'), 'r') as f:
            initialResponse = f.read()
    with open(os.path.join(script_dir, 'closeResponse.txt'), 'r') as f:
            closeResponse = f.read()

    if row is None:
        return "Record not found", 404

    if request.method == "POST":
        for col in SAVE_COLUMNS:
            df.loc[row.index, col] = request.form.get(col)
        save_data(df)
        update_sheet_data(mobile=mobile, dt=dt)
        return redirect(url_for("index"))
    
    row_series = row.iloc[0].to_dict()
    return render_template("edit.html", row=row_series, rowid=rowid, editable_fields=SAVE_COLUMNS, status_options=FILTERTEXT, ir=initialResponse, cr=closeResponse)


if __name__ == "__main__":
    app.run(debug=True)