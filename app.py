from flask import Flask, render_template, request, jsonify, redirect, url_for, current_app
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import os
from waitress import serve
import pytz
from authapi import check_login, init, auth, username
import datetime
import re

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
    'Inbound':'Enquiry',
    'Contacted':'Contacted',
    'Response Received':'Spotting',
    'Prospect':'Prospect',
    'In Negotiation':'Docking',
    'Onboarded':'Boarded',
    'Dropped':'Dropped'
}
SAVE_COLUMNS = ['Contacted'	,'Response'	,'Floor'	,'Status']

CSV_FILE = "output.csv"

# File paths (relative to app root)
INITIAL_FILE = 'intialResponse.txt'
CLOSE_FILE = 'closeResponse.txt'


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
    df['ts'] = pd.to_datetime(df['Timestamp'], format='%d/%m/%Y %H:%M:%S')
    df['Days_past'] = (pd.Timestamp.today().normalize() - df['ts']).dt.days
    for status in STATUSES:
        if status == 'Inbound':
            filtered = df[df["Status"].isnull() | (df["Status"].str.strip() == '') | (df["Status"].str.strip() == 'Enquiry')]
        else:
            filtered = df[df["Status"].str.strip().str.lower() == FILTERTEXT[status].lower()]
        
        
        entries = filtered[["Your Name", "You can reach me on (Mobile Number)", "Timestamp", "Response", "Days_past"]].dropna(subset=["Your Name", "You can reach me on (Mobile Number)"]).values.tolist()
        views[status] = [{"Your Name": n, "You can reach me on (Mobile Number)": m, "Timestamp": o, "Response":p, "Days_past":q} for n, m, o, p, q in entries]
    return render_template("index.html", views=views, statuses=STATUSES, filters=FILTERTEXT, route=route_prefix)

@app.route("/save", methods=["POST"])
def save():
    data = request.json.get("data", [])
    update_sheet_data(data)
    return jsonify({"status": "success"})


@app.route('/search', methods=['POST'])
def search():
    query = request.form.get('query', '').strip().lower()

    df = pd.read_csv(CSV_FILE)
    df['ts'] = pd.to_datetime(df['Timestamp'], format='%d/%m/%Y %H:%M:%S')
    df['Days_past'] = (pd.Timestamp.today().normalize() - df['ts']).dt.days
    # Filter rows that contain the query (case-insensitive) in any column
    mask = df.apply(lambda row: row.astype(str).str.lower().str.contains(query).any(), axis=1)
    filtered = df[mask]
    jtf = filtered[["Your Name", "You can reach me on (Mobile Number)", "Timestamp", "Response", "Days_past"]].dropna(subset=["Your Name", "You can reach me on (Mobile Number)"])
    #results = [{"Your Name": n, "You can reach me on (Mobile Number)": m, "Timestamp": o, "Response":p, "Days_past":q} for n, m, o, p, q in tf]

    return render_template('partials/search_results.html', results=jtf.to_dict(orient="records"), route=route_prefix, search_term=query)

@app.route('/editresp', methods=['GET', 'POST'])
def editor():
    if request.method == 'POST':
        initial_text = request.form.get('initial_response', '')
        close_text = request.form.get('close_response', '')

        # Save contents to files
        with open(INITIAL_FILE, 'w', encoding='utf-8') as f:
            f.write(initial_text)
        with open(CLOSE_FILE, 'w', encoding='utf-8') as f:
            f.write(close_text)

        print("Files saved successfully.")
        return redirect(route_prefix + "/edit?rowid=" + request.form.get("rowid")  )

    

    # On GET, load current contents
    if os.path.exists(INITIAL_FILE):
        with open(INITIAL_FILE, 'r', encoding='utf-8') as f:
            initial_text = f.read()
    else:
        initial_text = ''

    if os.path.exists(CLOSE_FILE):
        with open(CLOSE_FILE, 'r', encoding='utf-8') as f:
            close_text = f.read()
    else:
        close_text = ''

    return render_template('editresp.html', initial_text=initial_text, close_text=close_text, rowid=request.args.get("rowid"))

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
    
    #Clean phone number and send it for wa link.
    mobile = re.sub(r'\D', '', mobile)
    mobile = mobile[-10:] if len(mobile) > 10 else mobile
    mobile = "91" + mobile


    row_series = row.iloc[0].to_dict()
    return render_template("edit.html", row=row_series, rowid=rowid,mobile=mobile, editable_fields=SAVE_COLUMNS, status_options=FILTERTEXT, ir=initialResponse, cr=closeResponse, route=route_prefix)

if __name__ == "__main__":
    #app.run(debug=True, port=7000)
    serve(app, host='0.0.0.0', port=7000)