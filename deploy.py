# This is an executable deployment script with several functions for posting to Slack
# Largely based off of the existing set up in the Talend jobs
# This version is primarily for the regression library
'''
Note the following default run settings:
Merchants: REI.com,Black Diamond Equipment,Carousel Checks,Palmetto State Armory,RTIC Outdoors
(Reference available in json _sources/merchant_map.json)
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
import requests
import subprocess
import glob
import boto3
import time

from datetime import datetime, timedelta
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Argument collector
parser = argparse.ArgumentParser()
parser.add_argument("--job", type=str, help="Specifies the name of the job to use. Default is ds_validation", default="ds_validation")
parser.add_argument("--create-required", type=bool, help="Indicates if we need to use this script to create an image. Default is false.", default=False)
parser.add_argument("--containers", type=str, help="Comma separated string with a list of containers to deploy. Default is empty", default="")
parser.add_argument("--channel", type=str, help="Specifies the channel (ID) to output to slack. Default is ds_data_validation", default="C04HP5S5YNB")
parser.add_argument("--start", type=str, help="Specifies a start date for validation. Default is blank, which will use 30 days relative to yesterday.", default="")
parser.add_argument("--end", type=str, help="Specifies an end date for validation. Default is blank, which will force validation to end at yesterday.", default="")
parser.add_argument("--merchants", type=str, help="Specifies which merchant to run. Default is all.", default="all")
parser.add_argument("--skip-slack", type=bool, help="Indicates if we should skip posting to Slack for this run. Default is False", default=False)
parser.add_argument("--tag", type=str, help="Gives the tag label for the deployment. Default is test", default='test')
args = parser.parse_args()

def post_to_slack(channel, msg, fid):
    '''
    Posts a message to the chosen Slack channel

    Parameters:
        channel: str, the slack channel to post the alert to
        msg: str, contents to post to the Slack channel
        fid: str, gives the name of the file to post to Slack as an attachment

    Returns:
        None
    '''
    # Get API key for file attachment
    config = configparser.ConfigParser()
    config.read('avantlinkpy2.conf')
    slack_key = config.get('slack', 'api_key')

    # Build API client (with logging)
    client = WebClient(token=slack_key)
    logger = logging.getLogger(__name__)

    # Grab result and log it
    try:
        result = client.files_upload_v2(
            channel=channel,
            initial_comment=msg,
            file=fid
        )
        # Log the result
        logger.info(result)
    except SlackApiError as e:
        logger.error("Error uploading file: {}".format(e))

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
    client = boto3.client('batch')
    try:
        response = client.register_job_definition(
            jobDefinitionName=job_name,
            type='container',
            containerProperties={
                'image': image_name,
                'vcpus': cpus,
                'memory': memory
            }
        )
        print (response['jobDefinitionArn'])
    except Exception as e:
        print(e) # Logs errors registering job

def approve_mfa():
    '''
    We have MFA enabled on our AWS account
    Therefore, it's necessary to initialize a session with an approved connection
    These sessions are good for 24
    '''
    pass # TODO: Fill this in once design is tested elsewhere

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

if __name__ == "__main__":
    # Init
    now = time.strftime("%c")
    comment("Starting the release process on " + now)

    # Global parameters
    global client, tag
    client = boto3.client('ecs')
    tag = args.tag

    # Specify the uri of the image here
    uri = "701912468211.dkr.ecr.us-east-1.amazonaws.com/avantlink/" + args.job

    # Log in to ecs
    # ecs_login() FIXME: Need to uncomment to push images

    # Accept list of merchants
    # For all merchants, use our default merchant list
    if args.merchants == 'all':
        merchants = 'REI.com,Black Diamond Equipment,Carousel Checks,Palmetto State Armory,RTIC Outdoors'.split(',')
    # Supports multiple merchants
    else:
        merchants = args.merchants.split(',')

    # Let's trigger Le's code here for now
    # TODO: Comment this guy out once containerized- container will do this once run
    # Grab dates (30 days back ending yesterday is default)
    now = datetime.utcnow().replace(microsecond=0)
    if args.start == '' and args.end == '':
        end = now - timedelta(days=1)
        start = end - timedelta(days=30)
    else:
        start = args.start
        end = args.end

    # Try to parse dates
    # Since we allow input args for this, print a complaint if format fails
    try:
        end = end.strftime('%m/%d/%Y')
        start = start.strftime('%m/%d/%Y')
    except Exception as e:
        logging.error(f'Unable to process input args {start} and {end}')
        print(e)

    # Trigger script
    os.chdir('DataValidation')
    for merchant in merchants:
        # Cannot use spaces in cli, replace with _
        merchant = merchant.replace(' ', '_')
        cmd = f'python -m sources.comparison -m -sd {start} -ed {end} -mer {merchant}'
        subprocess.run(cmd, shell=True, timeout=60)
    os.chdir('..')

    # Slack configurations
    # Note the file tree here:
    '''
    xlsx
        date folder
            regression test folder
                EDW3_Production
                    xlsx file
    '''
    # Give the option to bypass Slack posting
    if args.skip_slack is False:
        channel = args.channel
        msg = f'''Regression test results ({now} run)'''
        file_list = build_file_list()
        for fid in file_list:
            post_to_slack(channel, msg, fid)

    # Grab list of images provided by args
    containers = args.containers.split(',')
    if containers == ['']:
        logging.warning('No containers specified to deploy. Exiting.')
        exit()
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

    # Cleanup
    files = glob.glob('DataValidation/validation_outputs/xlsx/*')
    for fid in files:
        os.remove(fid)

    # Mark completion of deployment
    now = time.strftime("%c")
    comment("End of release process on " + now)