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
    service = None
    categorical_report = None
    merchant_summary = None
    sheet = None
    merchant_name = None
    test_account_overview = None
    merchant_summary_report_values = {
        "ta": [],
        "tw": []
    }

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
        "all_sources": "1ANxSTK3-QdFyTnt8PAknVpFQZXwNdYombcyw87gx7rk",
        "historic_logs": "1JKJ_hQA4xzOxPHEd1xqgAPYk9vfmgpxeGXf21sBkWYw"
    }
    merchant_summary_RANGE = {
        "rei.com": "Merchant Summary!C2:C12",
        "Black Diamond": "Merchant Summary!A3",
        "Carousel Checks": "Merchant Summary!A4",
        "Palmetto State Armory": "Merchant Summary!A5",
        "RTIC Outdoors": "Merchant Summary!A6",
        "A_Life_Plus": "Merchant Summary!A7"
    }
    categorical_report_RANGE = {
        "rei.com": "REI.com!E1:Z"
    }
    test_account_overview_range = {
        "REI.com": "Test Accounts Overview!A2",
        "Black Diamond": "Test Accounts Overview!A3",
        "Carousel Checks": "Test Accounts Overview!A4",
        "Palmetto State Armory": "Test Accounts Overview!A5",
        "RTIC Outdoors": "Test Accounts Overview!A6",
        "A_Life_Plus": "Test Accounts Overview!A7"
    }

    all_sources_test_account_range = {
        "trending_widget": {
            "cube_postgres": {},
            "fact_postgres": {},
            "fact_redshift": {},
            "cube_olap": {}
        },
        "top_affiliates_widget": {
            "cube_postgres": {},
            "fact_postgres": {},
            "fact_redshift": {},
            "cube_olap": {}
        }
    }

    def __init__(self, merchant_summary, categorical_report, test_account_overview):
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
        self.merchant_summary = merchant_summary
        self.test_account_overview = test_account_overview
        self.sql_source = merchant_summary["SQL_source"]
        self.merchant_name = self.merchant_summary["Merchant"]

        self.run()

    def run(self):
        self.process_account_overview_report_for_google()
        # self.update_categorical_reports()
        self.simplify_merchant_summary()
        self.update_merchant_summaries()
        # self.update_test_account_overviews()

    def update_all_sources_merchant_summary(self):
        pass

    def update_merchant_summaries(self):
        # self.update_ta_merchant_summary()
        self.update_tw_merchant_summary()

    def update_categorical_reports(self):
        self.update_ta_merchant_categorical_report()
        self.update_tw_merchant_categorical_report()

    def update_test_account_overviews(self):
        # self.update_ta_test_account_overview()
        self.update_tw_test_account_overview()

    def update_ta_test_account_overview(self):
        value_range_body = {
            "values": [self.test_account_overview["Last Test"]]
        }
        request = self.sheet.update(
            spreadsheetId=self.avantlog_spreadsheet_ids["ta"][self.sql_source],
            range=self.test_account_overview_range[self.merchant_name],
            valueInputOption=VALUE_INPUT_OPTION,
            body=value_range_body
        )
        response = request.execute()
        pprint(response)

    def update_tw_test_account_overview(self):

        account_overview_body = {'values': [[
            f"{self.test_account_overview['Last Test']} \n {self.test_account_overview['pass/fail']['trending_widget']}"]]}
        try:
            test_account_overview = self.sheet.update(
                spreadsheetId=self.avantlog_spreadsheet_ids["tw"][self.sql_source],
                range=self.test_account_overview_range[self.merchant_name],
                valueInputOption=VALUE_INPUT_OPTION,
                body=account_overview_body
            ).execute()
            pprint(test_account_overview)
        except HttpError as err:
            print(err)

    def update_ta_merchant_summary(self):
        account_overview_body = {'values': self.merchant_summary_report_values["ta"]}
        try:
            merchant_account_overview = self.sheet.append(
                spreadsheetId=self.avantlog_spreadsheet_ids["ta"][self.sql_source],
                range=self.merchant_summary_RANGE[self.merchant_name.lower()],
                valueInputOption=VALUE_INPUT_OPTION,
                body=account_overview_body
            ).execute()
            print(
                f"{(merchant_account_overview.get('updates').get('updatedCells'))} cells appended. - Top accounts - Overview")
        except HttpError as err:
            print(err)

    def update_tw_merchant_summary(self):
        account_overview_body = {'values': self.merchant_summary_report_values["tw"]}
        try:
            # upload Test Accounts Overview Report - Trending Widget
            merchant_account_overview = self.sheet.append(
                spreadsheetId=self.avantlog_spreadsheet_ids["tw"][self.sql_source],
                range=self.merchant_summary_RANGE[self.merchant_name.lower()],
                valueInputOption=VALUE_INPUT_OPTION,
                body=account_overview_body
            ).execute()
            print(
                f"{(merchant_account_overview.get('updates').get('updatedCells'))} cells appended. - Trending Widget - Overview")
        except HttpError as err:
            print(err)

    def update_ta_merchant_categorical_report(self):
        top_accounts_categorical_report_body = {'values': self.categorical_report_values["top_affiliates_widget"]}
        # upload Categorical Report for each Widget -- Top Accounts / Top Affiliates
        try:
            top_accounts_result = self.sheet.append(
                spreadsheetId=self.avantlog_spreadsheet_ids["ta"][self.sql_source],
                range=self.categorical_report_RANGE[self.merchant_name.lower()],
                valueInputOption=VALUE_INPUT_OPTION,
                body=top_accounts_categorical_report_body
            ).execute()
            print(
                f"{(top_accounts_result.get('updates').get('updatedCells'))} cells appended. - Top Accounts - Categorical")
        except HttpError as err:
            print(err)

    def update_tw_merchant_categorical_report(self):
        trending_widget_categorical_report_body = {'values': self.categorical_report_values["trending_widget"]}
        try:
            # upload Categorical Report for each Widget -- Trending Widget
            trending_result = self.sheet.append(
                spreadsheetId=self.avantlog_spreadsheet_ids["tw"][self.sql_source],
                range=self.categorical_report_RANGE[self.merchant_name.lower()],
                valueInputOption=VALUE_INPUT_OPTION,
                body=trending_widget_categorical_report_body
            ).execute()
            print(
                f"{(trending_result.get('updates').get('updatedCells'))} cells appended. - Trending Widget - Categorical")
        except HttpError as err:
            print(err)

    def process_account_overview_report_for_google(self, subject=None):
        result = []
        category_order = ["Sales", "Combined Commission", "Network Commission",
                          "Clicks % Impressions", "Adjustments", "Affiliate Commission"]
        subject = subject or self.merchant_summary
        result.append([subject["Last Test"]])
        result.append([subject["Date Range"]])
        result.append([subject["Merchant"]])
        result.append([subject["Currency"]])
        result.append([subject["Network"]])
        ta_result = copy.deepcopy(result)
        tw_result = copy.deepcopy(result)
        for category in category_order:
            ta_result.append([subject["top_affiliates_widget"][category]])
        for category in category_order:
            tw_result.append([subject["trending_widget"][category]])
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
        self.merchant_summary_report_values["ta"] = ta_result
        self.merchant_summary_report_values["tw"] = tw_result
        return tw_result, ta_result

    def simplify_merchant_summary(self):
        new_summary_values = copy.deepcopy(self.merchant_summary_report_values)
        for widget_name in new_summary_values:
            for sublist in new_summary_values[widget_name]:
                if "fail" in str(sublist).lower():
                    sublist[0] = "FAIL"
                if "pass" in str(sublist).lower():
                    sublist[0] = "PASS!"
        self.merchant_summary_report_values = new_summary_values
        return new_summary_values
