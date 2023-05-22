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

# Argument collector
parser = argparse.ArgumentParser()
parser.add_argument("--job", type=str, help="Specifies the name of the job to use. Default is ds_validation", default="ds_validation")
parser.add_argument("--create-required", type=bool, help="Indicates if we need to use this script to create an image. Default is false.", default=False)
parser.add_argument("--containers", type=str, help="Comma separated string with a list of containers to deploy. Default is empty", default="")
parser.add_argument("--channel", type=str, help="Specifies the channel (ID) to output to slack. Default is ds_data_validation", default="C04HP5S5YNB")
parser.add_argument("--start", type=str, help="Specifies a start date for validation. Default is blank, which will use 30 days relative to yesterday. Format: mm/dd/yyyy", default="")
parser.add_argument("--end", type=str, help="Specifies an end date for validation. Default is blank, which will force validation to end at yesterday. Format: mm/dd/yyyy", default="")
parser.add_argument("--merchants", type=str, help="Specifies which merchant to run. Default is a set of 5 top merchants.", default="default")
parser.add_argument("--skip-slack", action="store_true", help="Indicates if we should skip posting to Slack for this run. Default is False")
parser.add_argument("--skip-logging", action="store_true", help="Indicates if logging should be skipped to the master spreadsheet")
parser.add_argument("--tag", type=str, help="Gives the tag label for the deployment. Default is test", default='test')
parser.add_argument("--timeout", type=int, help="Sets the timeout for running the rgeression test before failing. Default is 5 minutes", default=300)
parser.add_argument("--source", type=str, help="Tells the picker to use a particular data source. Default is empty, which will use typical fallback system.", default="")
parser.add_argument("-ne", "--no-error", action="store_true")
args = parser.parse_args()

def post_to_slack(channel, msg, fid, merchant, timeout=False):
    '''
    Posts a message to the chosen Slack channel

    Parameters:
        channel: str, the slack channel to post the alert to
        msg: str, contents to post to the Slack channel
        fid: str, gives the name of the file to post to Slack as an attachment
        merchant: str, the merchant name tied to this data result
        timeout: boolean (optional), indicates if a timeout happened

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
        cmd = f'''curl -d "text={title}" -d "channel=ds_validation" -H "Authorization: Bearer {slack_key}" -X POST https://slack.com/api/chat.postMessage -k'''
        proc = subprocess.run(cmd, shell=True, timeout=30, stdout=subprocess.PIPE)
        result = json.loads(proc.stdout)
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
    if matches is True:
        title = upload_name.replace('.xlsx', '') + ' passed'
        cmd = f'''curl -d "text={title}" -d "channel=ds_validation" -H "Authorization: Bearer {slack_key}" -X POST https://slack.com/api/chat.postMessage -k'''
        proc = subprocess.run(cmd, shell=True, timeout=30, stdout=subprocess.PIPE)
        result = json.loads(proc.stdout)
    else:
        title = upload_name.replace('.xlsx', '') + ' FAILED!'
        # Simplify summary name
        if 'summary' in upload_name:
             upload_name = merchant + '_' + 'Combined_Summary.xlsx'
        cmd = f"curl -F title='{upload_name}' -F initial_comment='{title}'  --form-string channels=ds_validation -F file=@{fid} -F filename={upload_name} -F token={slack_key} https://slack.com/api/files.upload -k"
        proc = subprocess.run(cmd, shell=True, timeout=30, stdout=subprocess.PIPE)
        result = json.loads(proc.stdout)

    # Log result
    # If it failed, log the stdout for debug
    if result["ok"] is True:
        print('Posted to Slack')
    else:
        print('Error posting to slack')
        print(result)

def comment(comment):
    '''
    This posts comments to the batch job (such as status updates)

    Parameters:
        comment: str, gives the contents of the info you want to display

    Returns:
        None
    '''
    datetime_str = str(datetime.now())
    if (comment != None):
        logging.info('-- %s [%s] %s' % (datetime_str,str(os.getpid()),comment))
        print('INFO: -- %s [%s] %s' % (datetime_str,str(os.getpid()),comment))

def register_image(image_name, job_name, cpus=2, memory=2000):
    '''
    Registers the image with ECS so it can be run from batch

    Parameters:
        image_name: str, gives the full URI path of the image
        cpus: int (optional), specifies the number of CPU cores required to process the job
        memory: int (optional), gives the memory (in mb) to use on container
    '''
    comment("Registering job for  " + job_name)
    # client = boto3.client('batch')
    # try:
    #     response = client.register_job_definition(
    #         jobDefinitionName=job_name,
    #         type='container',
    #         containerProperties={
    #             'image': image_name,
    #             'vcpus': cpus,
    #             'memory': memory
    #         }
    #     )
    #     print (response['jobDefinitionArn'])
    # except Exception as e:
    #     print(e) # Logs errors registering job

def ecs_login():
    '''
    This sets up the log in for the session
    Needed to do any ecs operations
    '''
    # Login to Docker using --no-include-email
    try:
        docker_login = subprocess.check_output("aws ecr --no-include-email get-login --region us-east-1",
            shell=True).decode(sys.stdout.encoding).strip()
    except Exception as e:
        print(e)
        raise
    print(docker_login)
    return_code = subprocess.run(docker_login, shell=True, stdout=os.devnull)
    if return_code.returncode != 0:
        comment("ERROR: Error login to ECS")
        print(return_code.returncode)
    else:
        comment("Successfully logged to ECS")

def create_ecs_image(job_name):
    '''
    Creates the actual docker image to be used by ECS

    Maybe can be done manually for purposes of this repo
    '''
    try :
        comment("Creating ECS for  " + job_name)
        #job_location = repo_directory + job_name
        #comment("Working on directory " + job_location)
        #os.chdir(job_location)

        # Build docker image
        return_code = subprocess.run("docker build -t avantlink/" + job_name + " .",shell=True, stdout=os.devnull)
        if return_code.returncode != 0:
            comment("ERROR: Error building ECS image")
        else:
            comment("Successfully built the docker image for " + job_name)

        # Tag the image
        job = "avantlink/" + job_name + ":" + tag + ""
        uri = "701912468211.dkr.ecr.us-east-1.amazonaws.com/" + job + ""
        return_code = subprocess.run("docker tag " + job + " " + uri + "", shell=True, stdout=os.devnull)
        if return_code.returncode != 0:
            comment("ERROR: Error tagging ECS")
        else:
            comment("Successfully tagged the image for " + job_name)

        # Delete last tag
        return_code = subprocess.run("aws ecr batch-delete-image --repository-name " + "avantlink/" + job_name + " --image-ids imageTag=production", shell=True, stdout=os.devnull)
        return_code1 = subprocess.run("aws ecr batch-delete-image --repository-name " + "avantlink/" + job_name + " --image-ids imageTag=Production", shell=True, stdout=os.devnull)
        return_code2 = subprocess.run("aws ecr batch-delete-image --repository-name " + "avantlink/" + job_name + " --image-ids imageTag=latest", shell=True, stdout=os.devnull)
        if return_code.returncode != 0 or return_code1.returncode != 0 or return_code2.returncode != 0:
            comment("ERROR: Error deleting prior tags")
        else:
            comment("Successfully deleted old tags/images")

    except Exception as e:
        print(e)

def push_ecs_image(uri, job_name):
    '''
    Tags and pushes the image to the AWS repository

    Parameters:
       uri: str, gives the reporitory uri in AWS for accessing the image

    Returns:
        None
    '''
    # Tag image
    tag_string = uri + f':{tag}'
    cmd = f'docker tag {tag_string}'
    subprocess.run(cmd, shell=True)

    # Push
    return_code = subprocess.run("docker push " + uri, shell=True)
    if return_code.returncode != 0:
        comment("ERROR: Error pushing ECS image")
    else:
        comment("Successfully pushed the image for " + job_name)

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
            if name.endswith('.xlsx'):
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

class RunCommand():

    def __init__(self, 
            args='',
            merchants='',
            logging=True
        ):
        '''
        Parameters:
            args: str, list of custom arguments joined into a string to append to command
            merchants: str, gives all of the merchants in a joined string to run for
            logging: boolean, indicates if we should send results to ouput loggin dashboard
        '''
        self.args = args
        
        # Start with base command we always use
        _base_command = 'python3.8 -m sources.comparison'

        # Merchants argument
        if self.merchants != '':
            _base_command += f' -mer {self.merchants}'

        # Custom argument list
        if self.args != '':
            _base_command += self.args

        # Logging argument
        if self.logging is True:
            _base_command += ' -ul'
        
        # Final command to run
        self.command = _base_command

class NoErrorCommand(RunCommand):
    '''
    Picker test suite, gives simple pass/fail
    '''
    args = ' -ne'
    logging = False

    def __init__(self):
        super().__init(
            args = self.args
        )

class RunMerchantsCommand(RunCommand):
    '''
    Used for running full regression on merchants
    '''
    args = ' -ra'

    def __init__(self,
         merchants=''):
         self.merchants=merchants
         super().__init(
             args=self.args,
             merchants=self.merchants
         )

if __name__ == "__main__":
    # Init
    now = time.strftime("%c")
    comment("Starting the release process on " + now)

    # Global parameters
    #global client, tag
    #client = boto3.client('ecs')
    tag = args.tag

    # Specify the uri of the image here
    uri = "701912468211.dkr.ecr.us-east-1.amazonaws.com/avantlink/" + args.job

    # Log in to ecs
    # ecs_login() FIXME: Need to uncomment to push images

    # Accept list of merchants
    # The "default" gives a list of 5 merchants we frequently run. This is the default setting
    if args.merchants == 'default':
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
            raise TypeError(f'The given source is not valid. Must be in {valid_sources} but got {args.source}')
        else:
            source = args.source
    else:
        source = None

    # Let's trigger Le's code here for now
    # TODO: Comment this guy out once containerized- container will do this once run
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
                cmd = f'python3.8 -m sources.comparison -ne'
            else:
                #cmd = f'python -m sources.comparison -ra -sd {start} -ed {end} -mer {merchant}'
                # Generally, logging will be done here: https://docs.google.com/spreadsheets/d/1JKJ_hQA4xzOxPHEd1xqgAPYk9vfmgpxeGXf21sBkWYw/edit#gid=0
                # It can be skipped however (see args)
                if args.skip_logging is False:
                    cmd = f'python3.8 -m sources.comparison -ra -mer={merchant} -ul'
                else:
                    cmd = f'python3.8 -m sources.comparison -ra -mer={merchant}'
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
                file_list = build_file_list()
                for fid in file_list:
                    if ' ' in fid:
                        try:
                            os.rename(fid, fid.replace(' ', '_'))
                            fid = fid.replace(' ', '_')
                        except FileNotFoundError:
                            print(fid)
                            raise
                    post_to_slack(channel, msg, fid, merchant, timeout=timeout)
                    # Only post 1 timeout message
                    if timeout is True:
                        break

            # Grab list of images provided by args
            containers = args.containers.split(',')
            if containers == ['']:
                logging.warning('No containers specified to deploy')
                #exit()
            else:
                print(containers)

            # For each container in the args list, 1st see if it needs to be dcreated
            # Then, register and deploy it
            for container in containers:
                if args.create_required is True:
                    print('Will create in a future release')
                    #create_ecs_image(container)
                else:
                    print('Skipping image creation')

                # Register and deploy- eventually, maybe
                #register_image(uri, container)
                #push_ecs_image(uri, container)

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
    comment("End of release process on " + now)
