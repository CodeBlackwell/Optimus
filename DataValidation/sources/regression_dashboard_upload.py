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
        "Black Diamond": "Merchant Summary!B2:B12",
        "Carousel Checks": "Merchant Summary!D2:D12",
        "Palmetto State Armory": "Merchant Summary!E2:E12",
        "RTIC Outdoors": "Merchant Summary!F2:F12",
        "A_Life_Plus": "Merchant Summary!G2:G12"
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
    all_sources_merchant_summary_RANGE = {
        "trending_widget": {
            "cube_postgres": {
                "Black Diamond": "Merchant Summary!B2:B12",
                "REI.com": "Merchant Summary!C2:C12",
                "Carousel Checks": "Merchant Summary!D2:D12",
                "Palmetto State Armory": "Merchant Summary!E2:E12",
                "RTIC Outdoors": "Merchant Summary!F2:F12",
                "A_Life_Plus": "Merchant Summary!G2:G12"
            },
            "fact_postgres": {
                "Black Diamond": "Merchant Summary!B15:B25",
                "REI.com": "Merchant Summary!C15:C25",
                "Carousel Checks": "Merchant Summary!D15:D25",
                "Palmetto State Armory": "Merchant Summary!E15:E25",
                "RTIC Outdoors": "Merchant Summary!F15:F25",
                "A_Life_Plus": "Merchant Summary!G15:G25"
            },
            "fact_redshift": {
                "Black Diamond": "Merchant Summary!B28:B38",
                "REI.com": "Merchant Summary!C28:C38",
                "Carousel Checks": "Merchant Summary!D28:D38",
                "Palmetto State Armory": "Merchant Summary!E28:E38",
                "RTIC Outdoors": "Merchant Summary!F28:F38",
                "A_Life_Plus": "Merchant Summary!28:G38G"
            },
            "cube_olap": {
                "Black Diamond": "Merchant Summary!B41:B51",
                "REI.com": "Merchant Summary!C41:C51",
                "Carousel Checks": "Merchant Summary!D41:D51",
                "Palmetto State Armory": "Merchant Summary!E41:E51",
                "RTIC Outdoors": "Merchant Summary!F41:F51",
                "A_Life_Plus": "Merchant Summary!G41:G51"
            }
        },
        "top_affiliates_widget": {
            "cube_postgres": {
                "Black Diamond": "Merchant Summary!I2:I12",
                "REI.com": "Merchant Summary!J2:J12",
                "Carousel Checks": "Merchant Summary!K2:K12",
                "Palmetto State Armory": "Merchant Summary!L2:L12",
                "RTIC Outdoors": "Merchant Summary!M2:M12",
                "A_Life_Plus": "Merchant Summary!N2:N12"
            },
            "fact_postgres": {
                "Black Diamond": "Merchant Summary!I15:I25",
                "REI.com": "Merchant Summary!J15:J25",
                "Carousel Checks": "Merchant Summary!K15:K25",
                "Palmetto State Armory": "Merchant Summary!L15:L25",
                "RTIC Outdoors": "Merchant Summary!M15:M25",
                "A_Life_Plus": "Merchant Summary!N15:N25"
            },
            "fact_redshift": {
                "Black Diamond": "Merchant Summary!I28:I38",
                "REI.com": "Merchant Summary!J28:J38",
                "Carousel Checks": "Merchant Summary!K28:K38",
                "Palmetto State Armory": "Merchant Summary!L28:L38",
                "RTIC Outdoors": "Merchant Summary!M28:M38",
                "A_Life_Plus": "Merchant Summary!N8:N38G"
            },
            "cube_olap": {
                "Black Diamond": "Merchant Summary!I41:I51",
                "REI.com": "Merchant Summary!J41:J51",
                "Carousel Checks": "Merchant Summary!K41:K51",
                "Palmetto State Armory": "Merchant Summary!L41:L51",
                "RTIC Outdoors": "Merchant Summary!M41:M51",
                "A_Life_Plus": "Merchant Summary!N41:N51"
            }
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
        tw_merchant_account_overview_body = {'values': self.merchant_summary_report_values["tw"]}
        try:
            # upload - Merchant Summary Report - All Sources - Trending Widget
            tw_merchant_account_overview = self.sheet.update(
                spreadsheetId=self.avantlog_spreadsheet_ids["all_sources"],
                range=self.all_sources_merchant_summary_RANGE["trending_widget"][self.sql_source][self.merchant_name],
                valueInputOption=VALUE_INPUT_OPTION,
                body=tw_merchant_account_overview_body
            ).execute()
            # print(tw_merchant_account_overview)
        except HttpError as err:
            print(tw_merchant_account_overview, err)

        ta_merchant_account_overview_body = {'values': self.merchant_summary_report_values["ta"]}
        try:
            # upload - Merchant Summary Report - All Sources - Top Affiliates Widget
            ta_merchant_account_overview = self.sheet.update(
                spreadsheetId=self.avantlog_spreadsheet_ids["all_sources"],
                range=self.all_sources_merchant_summary_RANGE["top_affiliates_widget"][self.sql_source][
                    self.merchant_name],
                valueInputOption=VALUE_INPUT_OPTION,
                body=ta_merchant_account_overview_body
            ).execute()
            # print(ta_merchant_account_overview)
        except HttpError as err:
            print(ta_merchant_account_overview, err)

    def update_merchant_summaries(self):
        self.update_merchant_summary("trending_widget")
        self.update_merchant_summary("top_affiliates_widget")

    def update_categorical_reports(self):
        self.update_merchant_categorical_report("trending_widget")
        self.update_merchant_categorical_report("top_affiliates_widget")

    def update_test_account_overviews(self):
        self.update_test_account_overview("trending_widget")
        self.update_test_account_overview("top_affiliates_widget")

    def update_test_account_overview(self, widget):
        widget_marker = self.get_widget_marker(widget)
        merchant_account_overview_body = {'values': [[
            f"{self.test_account_overview['Last Test']} \n {self.test_account_overview['pass/fail'][widget]}"]]}
        try:
            test_account_overview = self.sheet.update(
                spreadsheetId=self.avantlog_spreadsheet_ids[widget_marker][self.sql_source],
                range=self.test_account_overview_range[self.merchant_name],
                valueInputOption=VALUE_INPUT_OPTION,
                body=merchant_account_overview_body
            ).execute()
            pprint(test_account_overview)
        except HttpError as err:
            pprint(test_account_overview)
            print(err)

    def update_merchant_summary(self, widget):
        widget_marker = self.get_widget_marker(widget)
        account_overview_body = {'values': self.merchant_summary_report_values[widget_marker]}
        try:
            # upload - Merchant Summary Report - Trending Widget
            merchant_account_overview = self.sheet.update(
                spreadsheetId=self.avantlog_spreadsheet_ids[widget_marker][self.sql_source],
                range=self.merchant_summary_RANGE[self.merchant_name.lower()],
                valueInputOption=VALUE_INPUT_OPTION,
                body=account_overview_body
            ).execute()
            pprint(merchant_account_overview)
        except HttpError as err:
            print(err)

    def update_merchant_categorical_report(self, widget):
        widget_marker = self.get_widget_marker(widget)
        top_accounts_categorical_report_body = {'values': self.categorical_report_values[widget]}
        # upload Categorical Report for each Widget -- Top Affiliates / Trending widget
        try:
            top_accounts_result = self.sheet.append(
                spreadsheetId=self.avantlog_spreadsheet_ids[widget_marker][self.sql_source],
                range=self.categorical_report_RANGE[self.merchant_name.lower()],
                valueInputOption=VALUE_INPUT_OPTION,
                body=top_accounts_categorical_report_body
            ).execute()
            print(
                f"{(top_accounts_result.get('updates').get('updatedCells'))} cells appended. - {widget} - Categorical")
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

    def process_account_overview_report_for_google(self):
        result = []
        category_order = ["Sales", "Combined Commission", "Network Commission",
                          "Clicks % Impressions", "Adjustments", "Affiliate Commission"]
        subject = self.merchant_summary
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

    @staticmethod
    def get_widget_marker(widget):
        if widget == "top_affiliates_widget":
            return "ta"
        elif widget == "trending_widget":
            return "tw"
