from __future__ import print_function

import os.path
import json
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def get_values(spreadsheet_id, range_name):
    """
    Creates the batch_update the user has access to.
    Load pre-authorized user credentials from the environment.
    TODO(developer) - See https://developers.google.com/identity
    for guides on implementing OAuth2 for the application.
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
            token.write(creds.to_json())    # pylint: disable=maybe-no-member
    try:
        service = build('sheets', 'v4', credentials=creds)

        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=range_name).execute()
        rows = result.get('values', [])
        print(f"{len(rows)} rows retrieved")
        return result
    except HttpError as error:
        print(f"An error occurred: {error}")
        return error

def fix_json(broken_json):
    broken_json["Query"].replace("'", '"').replace("True", "true").replace("False", "false")
def process_rows(rows):
    cache = []
    unique_most_recent = {"EDW2": {}, "EDW3": {}}

    def mysort(e):
        return e['Date']

    for row in rows['values']:
        cache.append({
            'Report/Graph': row[0],
            'Version': row[1],
            'Date': row[2],
            'Query': row[3]
        })


    for idx, item in enumerate(cache):
        report_id = None
        if idx == 0:
            continue
        print()
        # for report_idz in item["Query"]:
        #     report_id = report_idz

        sys.exit()
        report_name = None
        if item["Version"] == "EDW2":
            if not unique_most_recent["EDW2"][item["Report/Graph"]]:
                # If the report has not been found, create entry
                unique_most_recent["EDW2"][item["Report/Graph"]] = {"request_object": item["Query"], "date": item["Date"]}
            if unique_most_recent["EDW2"][item["Report/Graph"]]:
                compare_date = [
                    unique_most_recent["EDW2"][item["Report/Graph"]],
                    {"request_object": item["Query"], "date": item["Date"]}
                ].sort(key=mysort)
                unique_most_recent["EDW2"][item["Report/Graph"]] = compare_date[0]
            if not unique_most_recent["EDW3"][item["Report/Graph"]]:
                # If the report has not been found, create entry
                unique_most_recent["EDW3"][item["Report/Graph"]] = {"request_object": item["Query"],
                                                                    "date": item["Date"]}
            if unique_most_recent["EDW3"][item["Report/Graph"]]:
                compare_date = [
                    unique_most_recent["EDW3"][item["Report/Graph"]],
                    {"request_object": item["Query"], "date": item["Date"]}
                ].sort(key=mysort)
                unique_most_recent["EDW3"][item["Report/Graph"]] = compare_date[0]

                #Standing bug - ALl dates that are 'Last Quarter', 'Last Year' etc. - Write exception

            #Write fix_Json function

    return cache

if __name__ == '__main__':
    # Pass: spreadsheet_id, and range_name
    rows = get_values("1sA8anBPSorLyLiYwf0oTOZ7FSRkvE9nDK16Wm83Cc-Y", "A1:ZZ")
    cached = process_rows(rows)
    # print(cached[1])