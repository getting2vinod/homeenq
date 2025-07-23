from flask import Flask, render_template, request, jsonify, redirect, url_for, current_app
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import os
from waitress import serve
import pytz
from authapi import check_login, init, auth, username

tz_IN = pytz.timezone('Asia/Kolkata')  

route_prefix = os.getenv('APP_ROUTE') or ""

if(route_prefix != ""):
    route_prefix = "/" + route_prefix

print("Prefix loaded : " + route_prefix)

app = Flask(__name__)
app.secret_key = "thisismyveryloooongsecretkey"
app.register_blueprint(auth)

SPREADSHEET_ID = '1Yv1gxQdbc5Aq4bo1CMnCAeVMvarltkryPzE4W96DtNw'
RANGE_NAME = 'Home Enquiry Responses'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT_FILE = './json/myutils-437714-bd0d0a3e77bd.json'

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

init(app)

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

def update_sheet_from_csv_using_googleapi(    
    timestamp_value: str,
    phone_value: str    
):
    """
    Search a row in a CSV by timestamp and phone number,
    and update Contacted, Response, Floor, Status fields
    in a Google Sheet using googleapiclient.
    """
    # === Read CSV ===
    df = pd.read_csv(CSV_FILE)

    # === Find matching row ===
    row_match = df[
        (df["Timestamp"].astype(str) == str(timestamp_value)) &
        (df["You can reach me on (Mobile Number)"].astype(str) == str(phone_value))
    ]
    if row_match.empty:
        print("❌ No matching row found in CSV.")
        return
    row_data = row_match.iloc[0]

    row_data = row_data.fillna('')
    service = get_sheet_service()

    # === Get Sheet Data to locate the row ===
    sheet_range = f"{RANGE_NAME}!A1:Z1000"  # adjust as needed
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=sheet_range
    ).execute()

    values = result.get("values", [])
    if not values:
        print("❌ Sheet is empty.")
        return

    headers = values[0]

    # === Locate row by timestamp and phone ===
    timestamp_idx = headers.index("Timestamp")
    phone_idx = headers.index("You can reach me on (Mobile Number)")

    target_row_index = None
    for i, row in enumerate(values[1:], start=2):  # Google Sheets rows are 1-indexed
        ts = row[timestamp_idx].strip() if timestamp_idx < len(row) else ""
        ph = row[phone_idx].strip() if phone_idx < len(row) else ""
        if ts == str(timestamp_value).strip() and ph == str(phone_value).strip():
            target_row_index = i
            break

    if target_row_index is None:
        print("❌ Matching row not found in Google Sheet.")
        return

    # === Prepare update payload ===
    update_fields = ['Contacted', 'Response', 'Floor', 'Status']
    update_values = [str(row_data.get(field, "")) for field in update_fields]
    update_column_indices = [headers.index(field) for field in update_fields]

    # Convert to A1 notation range like 'D5:G5'
    start_col = min(update_column_indices)
    end_col = max(update_column_indices)
    start_col_letter = chr(ord('A') + start_col)
    end_col_letter = chr(ord('A') + end_col)
    update_range = f"{RANGE_NAME}!{start_col_letter}{target_row_index}:{end_col_letter}{target_row_index}"

    # === Execute batch update ===
    body = {
        "range": update_range,
        "majorDimension": "ROWS",
        "values": [update_values]
    }

    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=update_range,
        valueInputOption="USER_ENTERED",
        body=body
    ).execute()

    print(f"✅ Row {target_row_index} updated in range {update_range}")

@app.route('/favicon.ico')
def favicon():
    return current_app.send_static_file("images/favicon.png")


@app.route("/fetch", methods=["GET"])
def fetch():
    df = fetch_sheet_data()
    return redirect(route_prefix) #url_for('index') 


@app.route("/")
def index():    
    df = read_data()
    views = {}
    for status in STATUSES:
        if FILTERTEXT[status] == '':
            filtered = df[df["Status"].isnull() | (df["Status"].str.strip() == '')]
        else:
            filtered = df[df["Status"].str.strip().str.lower() == FILTERTEXT[status].lower()]
        entries = filtered[["Your Name", "You can reach me on (Mobile Number)", "Timestamp", "Response"]].dropna(subset=["Your Name", "You can reach me on (Mobile Number)"]).values.tolist()
        views[status] = [{"Your Name": n, "You can reach me on (Mobile Number)": m, "Timestamp": o, "Response":p} for n, m, o, p in entries]
    return render_template("index.html", views=views, statuses=STATUSES, filters=FILTERTEXT, route=route_prefix)

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

    with open(os.path.join(script_dir, 'intialResponse.txt'), 'r') as f1:
            initialResponse = f1.read()
    with open(os.path.join(script_dir, 'closeResponse.txt'), 'r') as f2:
            closeResponse = f2.read()

    if row is None:
        return "Record not found", 404

    if request.method == "POST":
        for col in SAVE_COLUMNS:
            df.loc[row.index, col] = request.form.get(col)
        save_data(df)
        #save ir and cr if changed
        if request.form.get("irtext").replace("\r\n", "\n") != initialResponse :
              with open(os.path.join(script_dir, 'intialResponse.txt'), 'w') as f3:
                f3.write(request.form.get("irtext")) 
        if request.form.get("crtext").replace("\r\n", "\n") != closeResponse :
              with open(os.path.join(script_dir, 'closeResponse.txt'), 'w') as f4:
                f4.write(request.form.get("crtext")) 

        update_sheet_from_csv_using_googleapi(timestamp_value=dt, phone_value=mobile)
        return redirect(route_prefix)
    
    row_series = row.iloc[0].to_dict()
    return render_template("edit.html", row=row_series, rowid=rowid, editable_fields=SAVE_COLUMNS, status_options=FILTERTEXT, ir=initialResponse, cr=closeResponse, route=route_prefix)

@app.route("/cards")
def card_view():
    cards = [
        {"title": "Card 1", "text": "This is the first card."},
        {"title": "Card 2", "text": "This is the second card."},
        {"title": "Card 3", "text": "This is the third card."},
        {"title": "Card 4", "text": "This is the fourth card."},
    ]
    return render_template("card.html", cards=cards)

if __name__ == "__main__":
    #app.run(debug=True, port=7000)
    serve(app, host='0.0.0.0', port=7000)