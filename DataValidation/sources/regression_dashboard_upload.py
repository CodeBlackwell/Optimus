from __future__ import print_function

import os.path
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

avantlog_spreadsheet_ids = {
    "ta": {
        "fact_postgres": "1VJkxttwbiVLfip04xICyDlFoBQy5Mf_HizP9hzvjtss",
        "fact_redshift": "1y7zHDaod2cjhqm8lqJIMGl2KViSnRR_FWhbpUcHrgjY",
        "cube_postgres": "15FjO9ubVNNJkd_RL8l1qtErhfFaJWEcr17tzAo5Os4E"
    },
    "tw": {
        "fact_postgres": "1KCMR8viLCLerUPJXyV3Fc2f3v8lZFnuyFSnQ1FSjsFw",
        "fact_redshift": "1VJkxttwbiVLfip04xICyDlFoBQy5Mf_HizP9hzvjtss",
        "cube_postgres": "1knT1Q0qKsucl1YEjzT8e7iNsVWouhXp5oJ4zS9RWfbE"
    },
    "historic_logs": ""
}
VALUE_INPUT_OPTION = "USER_ENTERED"


def update_dashboard_log(account_overview_report, categorical_report):
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
        categorical_report_values = categorical_report  # must be an Array of Arrays -[ [ each, col, value, per, cell ], [], [], [] ]
        account_overview_report_values = None

        account_overview_body = {
            'values': account_overview_report_values
        }
        trending_widget_categorical_report_body = {
            'values': categorical_report_values["trending_widget"]
        }
        top_accounts_categorical_report_body = {
            'values': categorical_report_values["top_affiliates_widget"]
        }
        # print(len(trending_widget_categorical_report_body["values"]), "trending widget length")
        # print(len(top_accounts_categorical_report_body["values"]), "top accounts length")

        # @TODO: Dynamically Generate Ranges - Tab name and rows
        overview_report_RANGE = "Test Accounts Overview!B1:Z"
        merchant_report_RANGE = "REI.com!E1:Z"

        # @TODO: Dynamically Generate spreadsheet id
        # google_spreadsheet_id = "1knT1Q0qKsucl1YEjzT8e7iNsVWouhXp5oJ4zS9RWfbE"

        # upload Test Accounts Overview Report
        # merchant_account_overview = sheet.append(
        #     spreadsheetId=google_spreadsheet_id, range=overview_report_RANGE,
        #     valueInputOption=VALUE_INPUT_OPTION, body=account_overview_body).execute()
        # print(categorical_report_body)
        # runtime_string = f"{account_overview_report['']}"
        # upload Categorical Report for each Widget -- Top Accounts / Top Affiliates
        top_accounts_result = sheet.append(
            spreadsheetId=avantlog_spreadsheet_ids["ta"]["cube_postgres"], range=merchant_report_RANGE,
            valueInputOption=VALUE_INPUT_OPTION, body=top_accounts_categorical_report_body).execute()

        # upload Categorical Report for each Widget -- Trending
        trending_result = sheet.append(
            spreadsheetId=avantlog_spreadsheet_ids["tw"]["cube_postgres"], range=merchant_report_RANGE,
            valueInputOption=VALUE_INPUT_OPTION, body=trending_widget_categorical_report_body).execute()

        print(f"{(trending_result.get('updates').get('updatedCells'))} cells appended.")
        print(f"{(top_accounts_result.get('updates').get('updatedCells'))} cells appended.")

        return trending_result, top_accounts_result

    except HttpError as err:
        print(err)


def process_account_overview_report_for_google(account_overview_update_literal):
    pass
