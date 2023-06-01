# This is an executable deployment script with several functions for posting to Slack
# Largely based off of the existing set up in the Talend jobs
# This version is primarily for the regression library
'''
Note the following default run settings:
Merchants: REI.com,Black Diamond Equipment,Carousel Checks,Palmetto State Armory,RTIC Outdoors
(Reference available in merchant_map.json)
By default, we run for all metrics for these merchants for the following intervals:
    - Last 30 days
    - Last Year
'''

import sys
import os
import subprocess
import configparser
import argparse
import datetime
import logging
import json
import subprocess
import glob
import shutil
import time
import pandas as pd

from datetime import datetime, timedelta
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from runtime_args import args
from run_commands import NoErrorCommand, RunCommand, NoLoggingCommand

def post_to_slack(channel, msg, fid, merchant, source, timeout=False, js=None):
    '''
    Posts a message to the chosen Slack channel

    Parameters:
        channel: str, the slack channel to post the alert to
        msg: str, contents to post to the Slack channel
        fid: str, gives the name of the file to post to Slack as an attachment
        merchant: str, the merchant name tied to this data result
        source: str, data source we're loading from- displays in title
        timeout: boolean (optional), indicates if a timeout happened
        js: json object, contains a set of metadata required for reporting on the test suite (only usage)

    Returns:
        None
    '''
    # Get API key for file attachment
    config = configparser.ConfigParser()
    config.read('avantlinkpy2.conf')
    slack_key = config.get('slack', 'api_key')

    # If a timeout happend, go ahead and post that and carry on
    if timeout is True:
        title = f'{merchant} timed out'
        cmd = f'''curl -d "text={title}" -d "channel={channel}" -H "Authorization: Bearer {slack_key}" -X POST https://slack.com/api/chat.postMessage -k'''
        proc = subprocess.run(cmd, shell=True, timeout=30, stdout=subprocess.PIPE)
        result = json.loads(proc.stdout)
        return

    # Picker test suite doesn't post excel files
    # Instead post a pass/fail
    if fid is None:
        # Unpack json results for Slack
        title = js['test_name']
        edw2_ro = js['edw2_request_object']
        edw3_ro = js['edw3_request_object']

        # Create temp file
        fid = 'edw3_request_objects.json'
        with open(fid, 'a+') as f:
            f.write(json.dumps(edw3_ro))

        # Post to Slack and exit
        cmd = f"curl -F title='{fid}' -F initial_comment='{title}'  --form-string channels={channel} -F file=@{fid} -F filename={fid} -F token={slack_key} https://slack.com/api/files.upload -k"
        proc = subprocess.run(cmd, shell=True, timeout=30, stdout=subprocess.PIPE)
        result = json.loads(proc.stdout)

        # Delete temp file
        os.remove(fid)
        return

    # Check if file matches between edw and edw3
    # Only send those that do not match to Slack
    df = pd.read_excel(fid)
    columns = df.columns.to_list()
    for column in columns:
        if "edw2" in column and "request_object" not in column:
            edw2_column = column
        elif "edw3" in column and "request_object" not in column:
            edw3_column = column
    if df[edw2_column].equals(df[edw3_column]) is True:
        matches = True
    else:
        matches = False

    # Build an upload curl command to post to slack
    # The components here govern how the data is displayed- note the display file name != system file name
    # NOTE: If we match, just post the test passed
    upload_name = merchant + '_' + fid.split('/')[-1]
    source = source.replace('fact_', '')
    if matches is True:
        title = upload_name.replace('.xlsx', '') + f'({source})' + ' passed'
        cmd = f'''curl -d "text={title}" -d "channel={channel}" -H "Authorization: Bearer {slack_key}" -X POST https://slack.com/api/chat.postMessage -k'''
        proc = subprocess.run(cmd, shell=True, timeout=30, stdout=subprocess.PIPE)
        result = json.loads(proc.stdout)
    else:
        title = upload_name.replace('.xlsx', '') + f'({source})' + ' FAILED!'
        # Simplify summary name
        if 'summary' in upload_name:
             upload_name = merchant + '_' + 'Combined_Summary.xlsx'
        cmd = f"curl -F title='{upload_name}' -F initial_comment='{title}'  --form-string channels={channel} -F file=@{fid} -F filename={upload_name} -F token={slack_key} https://slack.com/api/files.upload -k"
        proc = subprocess.run(cmd, shell=True, timeout=30, stdout=subprocess.PIPE)
        result = json.loads(proc.stdout)

    # Log result
    # If it failed, log the stdout for debug
    if result["ok"] is True:
        print('Posted to Slack')
    else:
        print('Error posting to slack')
        print(result)

def build_file_list():
    '''
    Builds a list of files by walking the file path
    Uses a relative path to where Le's code outputs the files
    At some point, might want to be able to choose which files to include or not
    '''
    output_dir = 'DataValidation/validation_outputs/xlsx/'
    file_list = []

    # Walk the data directory and grab all output files (not dirs)
    for root, dirs, files in os.walk(output_dir):
        for name in files:
            fid = os.path.join(root, name)
            # Only applend excel files
            if name.endswith('.xlsx'):
                # Replace empty spaces with _
                if ' ' in fid:
                    try:
                        os.rename(fid, fid.replace(' ', '_'))
                        fid = fid.replace(' ', '_')
                    except FileNotFoundError:
                        print(fid)
                        raise
                file_list.append(fid)
    return file_list

def calculate_times(now):
    '''
    Builds lists of start and end times
    We'll exclude today and run for the following:
        - month_to_date (30 days back from yesterday)
        - last_month
        - last_year

    Parameters:
        now: datetime, gives the current time

    Returns:
        start_times: a list of start times
        end_times: a list of end times to use
    '''
    # Drop time
    now = now.replace(hour=0, minute=0, second=0)

    # Last 30 days
    mtd_end = now - timedelta(days=1)
    mtd_start = mtd_end - timedelta(days=30)

    # Last month
    day_of_month = int(now.strftime("%d"))
    lm_end = now - timedelta(days=day_of_month)
    lm_start = lm_end.replace(day=1)
    lm_end = lm_end + timedelta(days=1)

    # Last year
    doy = int(now.strftime("%j"))
    ly_end = now - timedelta(days=doy)
    ly_start = ly_end - timedelta(days=364)
    ly_end = ly_end + timedelta(days=1)

    # Collect into lists
    start_times = [mtd_start, lm_start, ly_start]
    end_times = [mtd_end, lm_end, ly_end]
    return start_times, end_times

if __name__ == "__main__":
    # Init
    now = time.strftime("%c")

    # Accept list of merchants
    # The "default" gives a list of 5 merchants we frequently run. This is the default setting
    if args.merchants == 'default':
        if args.no_error:
            merchants = ['REI.com']
        else:
            merchants = 'REI.com,Black Diamond Equipment,Carousel Checks,Palmetto State Armory,RTIC Outdoors,Patagonia_CA,A_Life_Plus'.split(',')
    # For all merchants, read from merchant map and run them all
    elif args.merchants == 'all':
        with open('merchant_map.json', 'r+') as f:
            data_set = json.load(f)
            merchants = list(data_set.values())
    # Custom list or single entry- supports multiple merchants
    else:
        merchants = args.merchants.split(',')

    # Check is source was specified. If it was, confirm we can use it
    if args.source != '':
        valid_sources = ['fact_redshift', 'fact_postgres', 'olap', 'cube_postgres', 'athena']
        if args.source not in valid_sources:
            valid_string = ', '.join(valid_sources)
            raise TypeError(f'The given source is not valid. Must be in {valid_string} but got {args.source}')
        else:
            source = args.source
    else:
        source = ''

    # Grab dates (30 days back ending yesterday is default)
    now = datetime.utcnow().replace(microsecond=0)
    if args.start == '' and args.end == '':
        start_times, end_times = calculate_times(now)
    else:
        # Cover case where end wasn't given
        if args.start != '' and args.end == '':
            logging.warning('Start given without end. Defaulting to now')
            end = now
        start_times = args.start.split(',')
        end_times = args.end.split(',')

    # Run for every input date
    for index, start_time in enumerate(start_times):
        start = start_times[index]
        end = end_times[index]

        # Try to parse dates
        # Since we allow input args for this, print a complaint if format fails
        try:
            end = end.strftime('%m/%d/%Y')
            start = start.strftime('%m/%d/%Y')
        except Exception as e:
            logging.error(f'Unable to process input args {start} and {end}')
            print('Hint: start/end should be in the format mm/dd/yyyy')
            print(e)

        # Make sure end isn't after now
        if datetime.strptime(end, '%m/%d/%Y') > now:
            logging.warning(f'End time given {end} is in the future! Resetting to now')
            end = now

        # Move to working directory (for cron)
        os.chdir('/home/ubuntu/ds-data_validation/')

        # Trigger script
        for merchant in merchants:
            print(f'Running regression for merchant {merchant}')
            try:
                os.chdir('DataValidation')
            except:
                print(os.getcwd())
            # Cannot use spaces in cli, replace with _
            merchant = merchant.replace(' ', '_')
            if args.no_error:
                run_command = NoErrorCommand(merchants=merchant, source=source)
            else:
                #cmd = f'python -m sources.comparison -ra -sd {start} -ed {end} -mer {merchant}' # FIXME: Le's script hasn't been tested with custom times
                # Generally, logging will be done here: https://docs.google.com/spreadsheets/d/1JKJ_hQA4xzOxPHEd1xqgAPYk9vfmgpxeGXf21sBkWYw/edit#gid=0
                # It can be skipped however (see args)
                if args.skip_logging is False:
                    run_command = RunCommand(merchants=merchant, source=source)
                else:
                    run_command = NoLoggingCommand(merchants=merchant, source=source)
            cmd = run_command.command

            # Print the command and run it
            # If it should fail, make note of that here as well so we can print that out to slack
            try:
                print(cmd)
                subprocess.run(cmd, shell=True, timeout=args.timeout)
                timeout = False
            except subprocess.TimeoutExpired:
                timeout = True # Log the timeout and then continue

            # Slack configurations
            # Note the file tree here:
            '''
            xlsx
                date folder
                    regression test folder
                        EDW3_Production
                            xlsx file
            '''
            os.chdir('..')
            # Give the option to bypass Slack posting
            if args.skip_slack is False:
                channel = args.channel
                msg = f'''Regression test results ({now} run)'''
                logging.info(msg)

                # For Picker test suite, don't post files
                # Instead, grab results from the log file on disk
                if args.no_error:
                    json_dicts = []
                    with open('DataValidation/test_suite_outputs.json') as f:
                        for line in f:
                            json_dicts.append(json.loads(line))

                    # Post results to Slack
                    for json_dict in json_dicts:
                        post_to_slack(channel, msg, None, merchant, source, timeout=timeout, js=json_dict)
                else:
                    file_list = build_file_list()
                    for fid in file_list:
                        post_to_slack(channel, msg, fid, merchant, source, timeout=timeout)
                        # Only post 1 timeout message
                        if timeout is True:
                            break

            # Cleanup files stored on server
            files = glob.glob('DataValidation/validation_outputs/xlsx/*')
            for fid in files:
                ctime = os.stat(fid).st_ctime
                shutil.rmtree(fid)
            print(f'Cleanup done for merchant {merchant}')

            # On the conclusion of each run, wait 30 seconds if running again
            # This is to prevent Slack from blocking outputs
            if merchant.replace('_', ' ') != merchants[-1]:
                print('Waiting 30 seconds before starting next merchant...')
                time.sleep(30)

        break # This is to skip the extra time ranges for now

    # Mark completion of deployment
    now = time.strftime("%c")