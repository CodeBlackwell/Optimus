from __future__ import print_function

import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# The ID and range of a sample spreadsheet.
SPREADSHEET_ID = '1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms'
RANGE = "Sheet1!A1:Z"
avantlog_spreadsheet_id = "1JKJ_hQA4xzOxPHEd1xqgAPYk9vfmgpxeGXf21sBkWYw"
VALUE_INPUT_OPTION = "USER_ENTERED"


def update_log(logs_batch=None):
    """Shows basic usage of the Sheets API.
    Prints values from a sample spreadsheet.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('sheets', 'v4', credentials=creds)

        # Call the Sheets API
        sheet = service.spreadsheets().values()
        values = logs_batch # must be an Array of Arrays -[ [ each, col, value, per, cell ], [], [], [] ]

        body = {
            'values': values
        }
        result = sheet.append(
            spreadsheetId=avantlog_spreadsheet_id, range=RANGE,
            valueInputOption=VALUE_INPUT_OPTION, body=body).execute()
        print(f"{(result.get('updates').get('updatedCells'))} cells appended.")
        return result
    except HttpError as err:
        print(err)

