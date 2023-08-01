from __future__ import print_function

import copy
import os.path
from pprint import pprint

import sys
from pprint import pprint
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
VALUE_INPUT_OPTION = "USER_ENTERED"


class UpdateDashboardLog:
    categorical_report = None
    account_overview_report = None
    account_overview_report_values = {
        "ta": [],
        "tw": []
    }
    sheet = None
    merchant_name = None
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
        "historic_logs": "1JKJ_hQA4xzOxPHEd1xqgAPYk9vfmgpxeGXf21sBkWYw"
    }
    overview_report_RANGE = {
        "rei.com": "Test Accounts Overview!C1:Z12"
    }
    merchant_report_RANGE = {
        "rei.com": "REI.com!E1:Z"
    }

    def __init__(self, account_overview_report, categorical_report):
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
        # Call the Sheets API
        service = build('sheets', 'v4', credentials=creds)
        self.service = service
        self.sheet = service.spreadsheets().values()
        self.categorical_report_values = categorical_report  # must be an Array of Arrays -[ [ each, col, value, per, cell ], [], [], [] ]
        self.account_overview_report = account_overview_report
        self.sql_source = account_overview_report["SQL_source"]
        self.merchant_name = self.account_overview_report["Merchant"]

        self.run()

    def run(self):
        self.process_account_overview_report_for_google()
        self.update_categorical_reports()
        self.update_test_accounts_overview()

    def update_test_accounts_overview(self):
        self.update_ta_test_accounts_overview()
        self.update_tw_test_accounts_overview()

    def update_categorical_reports(self):
        self.update_ta_merchant_categorical_report()
        self.update_tw_merchant_categorical_report()

    def update_ta_test_accounts_overview(self):
        account_overview_body = {'values': self.account_overview_report_values["ta"]}
        try:
            merchant_account_overview = self.sheet.append(
                spreadsheetId=self.avantlog_spreadsheet_ids["ta"][self.sql_source], range=self.overview_report_RANGE[self.merchant_name.lower()],
                valueInputOption=VALUE_INPUT_OPTION, body=account_overview_body).execute()
            print(f"{(merchant_account_overview.get('updates').get('updatedCells'))} cells appended. - Top accounts - Overview")
        except HttpError as err:
            print(err)

    def update_tw_test_accounts_overview(self):
        account_overview_body = {'values': self.account_overview_report_values["tw"]}
        try:
            # upload Test Accounts Overview Report - Trending Widget
            merchant_account_overview = self.sheet.append(
                spreadsheetId=self.avantlog_spreadsheet_ids["tw"][self.sql_source], range=self.overview_report_RANGE[self.merchant_name.lower()],
                valueInputOption=VALUE_INPUT_OPTION, body=account_overview_body).execute()
            print(f"{(merchant_account_overview.get('updates').get('updatedCells'))} cells appended. - Trending Widget - Overview")
        except HttpError as err:
            print(err)

    def update_ta_merchant_categorical_report(self):
        top_accounts_categorical_report_body = {'values': self.categorical_report_values["top_affiliates_widget"]}
        # upload Categorical Report for each Widget -- Top Accounts / Top Affiliates
        try:
            top_accounts_result = self.sheet.append(
                spreadsheetId=self.avantlog_spreadsheet_ids["ta"][self.sql_source], range=self.merchant_report_RANGE[self.merchant_name.lower()],
                valueInputOption=VALUE_INPUT_OPTION, body=top_accounts_categorical_report_body).execute()
            print(f"{(top_accounts_result.get('updates').get('updatedCells'))} cells appended. - Top Accounts - Categorical")
        except HttpError as err:
            print(err)

    def update_tw_merchant_categorical_report(self):
        trending_widget_categorical_report_body = {'values': self.categorical_report_values["trending_widget"]}
        try:
            # upload Categorical Report for each Widget -- Trending Widget
            trending_result = self.sheet.append(
                spreadsheetId=self.avantlog_spreadsheet_ids["tw"][self.sql_source], range=self.merchant_report_RANGE[self.merchant_name.lower()],
                valueInputOption=VALUE_INPUT_OPTION, body=trending_widget_categorical_report_body).execute()
            print(f"{(trending_result.get('updates').get('updatedCells'))} cells appended. - Trending Widget - Categorical")
        except HttpError as err:
            print(err)

    def process_account_overview_report_for_google(self):
        result = []
        category_order = ["Sales", "Combined Commission", "Network Commission",
                          "Clicks % Impressions", "Adjustments", "Affiliate Commission"]

        result.append([self.account_overview_report["Last Test"]])
        result.append([self.account_overview_report["Date Range"]])
        result.append([self.account_overview_report["Merchant"]])
        result.append([self.account_overview_report["Currency"]])
        result.append([self.account_overview_report["Network"]])
        ta_result = copy.deepcopy(result)
        tw_result = copy.deepcopy(result)
        for category in category_order:
            ta_result.append([self.account_overview_report["top_affiliates_widget"][category]])
        for category in category_order:
            tw_result.append([self.account_overview_report["trending_widget"][category]])
        for sublist in ta_result:
            for val in sublist:
                new_val = str(val).replace("{", "").replace("}", "").replace(",", "\n").replace("]", "")
            sublist.pop()
            sublist.append(new_val)
        for sublist in tw_result:
            for val in sublist:
                new_val = str(val).replace("{", "").replace("}", "").replace(",", "\n").replace("]", "")
            sublist.pop()
            sublist.append(new_val)
        self.account_overview_report_values["ta"] = ta_result
        self.account_overview_report_values["tw"] = tw_result
        return tw_result, ta_result


def detect_range(spreadsheet_id):
    pass
