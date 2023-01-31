# ds-data_validation repo readme

## Purpose

This is the repo we (the DS team) use for end to end validation and provide as overview of the health of the system. This repo uses versioning as we work through issues and find bugs. This readme provides an overview of what's in here, how to use it, and much more!

## How the regression works
TODO: Le, fill this in when you get the chance

## The deploy.py script

The deploy script is our executable "wrapper" script that launches the regression library with default settings (and some customizations!). This script can be run by simply running python deploy.py from the root directory of the repo, which will invoke the script with default settings. Those settings are as follows (January 2022):

- Job name: ds_validation
- Channel to output to: ds_validation
- Some container stuff (it's all skipped and commented out right now)
- A blank start... this equates to the following start times:
    - Today - 31 days (last 30 days)
    - 1st day of last month (last month)
    - 1st day of last year (last year)
- A blank end... this equates to the following end times:
    - Today - 1 days (last 30 days)
    - 1st day of this month- non-inclusive (last month)
    - 1st day of this year- non-inclusive (last year)
- Merchants: all (which runs the top 5 merchants as of this release
- Skip-slack = False. This prevents suppressing output to Slack.

The following arguments are available for the deploy script:
--job: Gives the name of the job. Mostly unused
--create-required: For containers. Keep false.
--containers: Unused, keep blank.
--channel: The output channel to Slack. Use this flag to output to a different channel
--start: The start time for validation. Can be specified here to manually choose an interval to run
--end: Ditto here except for the end time. If unspecified, will default to start + 30 days or now
--merchants: Allows for a list of merchants specified to run for (no spaces). Can be by name or uuid (see DataValidation/json_sources/merchant_map.json)
--skip-slack: If toggled to True, will suppress output to Slack. Mainly for debugging.
--tag: For Docker. Unused right now.

The idea is to have the deploy script run under default settings (or with args) on a cron job until it is integrated into the avant cli

## Versioning and Issues

We'll release major and minor version releases to maintain this and keep it working as expected as updates come through our system. The code is, admittedly, set up for a quick release, but since we're using this for data control, some maintenance will be done.

For any bugs or errors found with this, please submit a github issue here and create a card through Jira. You can also flag bugs directly from the ds_validation channel in Avantlink Slack.
