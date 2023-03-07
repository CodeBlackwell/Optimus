# !#/bin/python3 -> this is just to indicate to the user this script is executable

import argparse
import asyncio
import copy
import json
import os
import re
import sys
from datetime import datetime

import arrow
import gspread
import http3
import pandas as pd
import requests
import sources
from compare_reports import Comparison
from args import args
from oauth2client.service_account import ServiceAccountCredentials

configs = json.load(open('../config.json'))


class Cascade:
    edw2_request_object = None
    edw3_request_object = None
    output_xlsx = True
    simple_difference = False
    force_picker_address = True
    cascade = False
    change_logs = []
    loop = None
    totals = {"count": {}, "difference": {}}
    cascade_start_date = None
    cascade_end_date = None
    report_name = ""
    request_objects = {
        "day": [],
        "week": [],
        "month": []
    }
    dashboard_categories = {
        "Sales": True,
        "Combined Commissions": True,
        "Affiliate Commission": True,
        "Network Commission": True,
        "Clicks % Impressions": True,
        "Adjustments": True
    }
    production_sim_name = "EDW3_Production"
    dashboard_regression_path = None
    comparisons = {
        "day": [],
        "week": [],
        "month": [],
        "simple": []
    }
    sem = None
    semaphore_count = 3
    edw2_url = 'https://picker-dev.avantlink.com/rpt'
    edw3_url = 'https://picker-shard.avantlink.com/rpt'
    arrow_formats = {
        "mm_dd_yyyy": "%m/%d/%Y",
        "yyyymmdd": "%Y%m%d"
    }
    display_groups = []
    prepared_col_map = None

    def __init__(self, start_date=None, end_date=None, edw2_request_object=None,
                 edw3_request_object=None, report_name=None, cascade=False):
        self.timestamp = None
        self.cascade_start_date = start_date
        self.report_name = report_name
        self.cascade_end_date = end_date
        self.edw2_request_object = edw2_request_object
        self.edw3_request_object = edw3_request_object
        self.cascade = cascade
        self.true = True
        self.false = False
        self.null = None
        self.sem = asyncio.Semaphore(self.semaphore_count)
        self.__build_map__()

    @staticmethod
    def generate_dates(starting_date, ending_date, interval='day'):
        result = {"dates": [],
                  "interval": interval}
        for r in arrow.Arrow.range(interval, starting_date, ending_date):
            result["dates"].append(r.format('MM/DD/YYYY'))
        # check if the last week covers to the last day of the month
        last_date = result["dates"][-1]
        start = arrow.get(starting_date)
        end = arrow.get(ending_date)
        date_split = last_date.split("/")
        # If the last day is not == to the last day of the range, fill in the last day.
        missing_days = (arrow.get(int(date_split[2]), int(date_split[0]), int(date_split[1])).is_between(start, end))
        if missing_days:
            # add the remaining days for the range
            result["dates"].append(ending_date.strftime('%m/%d/%Y'))
        return result

    def run(self):
        # generate request objects over the specified date range
        # if it is a cascade report, do it for all appropriate intervals
        dates_hash = self.generate_dates(self.cascade_start_date, self.cascade_end_date)
        loop = asyncio.new_event_loop()
        self.loop = loop
        try:
            loop.run_until_complete(
                self.loop_reports(dates_hash)
            )
        except KeyboardInterrupt:
            pass
        finally:
            loop.close()
        pass

    def __build_map__(self):
        loop = asyncio.new_event_loop()
        try:
            # loop.run_until_complete(
            #     self.get_display_groups()
            # )
            loop.run_until_complete(
                self.get_prepared_cols()
            )
        except KeyboardInterrupt:
            pass
        finally:
            loop.close()
            self.process_map(self.prepared_col_map)
        pass

    def process_map(self, prepared_cols_map):
        new_map = {}
        for fact_dim in prepared_cols_map:
            for prepared_col in prepared_cols_map[fact_dim]:
                try:
                    new_map[prepared_col["prepared_column_id"]] = prepared_col
                except KeyError as e:
                    print(f"This Prepared id was not found === {e}")
        self.prepared_col_map = new_map

    async def get_prepared_cols(self):
        client = http3.AsyncClient()
        headers = {
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            # 'Accept-Encoding': 'gzip, deflate, br',
            'user_id': configs["root_user_id"],
            'tz': 'America/Denver',
            'fmonth': 'jan',
            'currency': 'USD',
            'default_currency': 'USD',
        }

        response = await client.get('https://picker-shard.avantlink.com/prepared_cols', headers=headers)
        self.prepared_col_map = response.json()
        return response

    async def get_display_groups(self):

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        data = "{'secret': %s}" % {configs["api_secret"]}

        response = await requests.get('http://manifest.avantlink.com/api/v1/display_groups', headers=headers, data=data)
        return response

    async def get_cols_by_display_group(self, group):
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        data = "{'secret': %s}" % configs["api_secret"]

        return requests.get(f'http://manifest.avantlink.com/api/v1/prepared_ids/display_groups/{group}',
                            headers=headers, data=data).json()

    async def loop_reports(self, dates_hash, interval="day", force_picker_address=None):
        futures = []
        for date_idx, date in enumerate(dates_hash["dates"]):
            print('running date idx : ', dates_hash)
            if date_idx == len(dates_hash["dates"]) - 1 and interval != 'day':
                break
            edw2_request_copy = copy.deepcopy(self.edw2_request_object)
            edw3_request_copy = copy.deepcopy(self.edw3_request_object)
            futures.append(
                self.run_comparison(dates_hash, date_idx, edw2_request_copy, edw3_request_copy,
                                    interval=interval, force_picker_address=force_picker_address))

        result = await asyncio.gather(*futures)
        self.comparisons[interval].append(result)
        return result

    def check_replace(self, request_object, dates_hash, date_idx, interval, date_format=None):
        # extrapolate format info
        if date_format is None:
            date_format = {
                "filter_format": "mm_dd_yyyy",
                "dimension_format": "yyyymmdd",
                "date_col_name": "DATE"
            }
        column_name = date_format["date_col_name"]
        filter_field = "dim_date-%s" % date_format["filter_format"]
        dimension_field = "dim_date-%s" % date_format["dimension_format"]
        filter_format = self.arrow_formats[date_format["filter_format"]]

        # create a fresh filter
        start = dates_hash["dates"][date_idx]
        valid_start = start.split('/')
        valid_start = arrow.get(int(valid_start[2]), int(valid_start[0]), int(valid_start[1]))
        new_start = valid_start.strftime(filter_format)

        if interval != 'day':
            end = dates_hash["dates"][date_idx + 1]
            valid_end = end.split('/')
            valid_end = arrow.get(int(valid_end[2]), int(valid_end[0]), int(valid_end[1]))
            new_end = valid_end.strftime(filter_format)

        if interval == 'day':
            replacement_filter = {
                "field": filter_field,
                "op": "eq",
                "values": [
                    new_start
                ]
            }
        elif interval == 'week':
            # 1st iteration specification
            if date_idx == 0:
                replacement_filter = {
                    "field": filter_field,
                    "op": "between",
                    "values": [
                        new_start,
                        new_end
                    ]
                }
            else:
                split_start = start.split('/')
                shiftable_date_obj = arrow.get(int(split_start[2]), int(split_start[0]), int(split_start[1]))
                modified_start = shiftable_date_obj.shift(days=+1).strftime(filter_format)
                replacement_filter = {
                    "field": filter_field,
                    "op": "between",
                    "values": [
                        modified_start,
                        new_end
                    ]
                }
        elif interval == 'month':
            split_end = end.split('/')
            shiftable_date_obj = arrow.get(int(split_end[2]), int(split_end[0]), int(split_end[1]))
            modified_end = shiftable_date_obj.shift(days=-1).strftime(filter_format)
            # last iteration specification
            if date_idx == len(dates_hash["dates"]) - 2:
                replacement_filter = {
                    "field": filter_field,
                    "op": "between",
                    "values": [
                        new_start,
                        new_end
                    ]
                }

            else:
                replacement_filter = {
                    "field": filter_field,
                    "op": "between",
                    "values": [
                        new_start,
                        modified_end
                    ]
                }

        replacement_date_dim = {
            "id": dimension_field,
            "name": column_name,
            "alias": "date"
        }
        # Look in the filters
        dim_name = 'dim_date'
        for report_name in request_object:
            for col_idx, col_obj in enumerate(request_object[report_name]["cols"]):
                if 'prepared_id' in col_obj:
                    continue
                if dim_name in col_obj["id"]:
                    # print("Deleting - Dimension - ", col_obj)
                    # print("Replacement - Dimension - ", replacement_date_dim)
                    del request_object[report_name]["cols"][col_idx]
            request_object[report_name]["cols"].append(replacement_date_dim)
            # Replace Filter
            for filter_idx, filter_obj in enumerate(request_object[report_name]["filters"]):
                if dim_name in filter_obj["field"]:
                    # print("Deleting - Filter - ", filter_obj)
                    # print("Replacement - Filter - ", replacement_filter)
                    del request_object[report_name]["filters"][filter_idx]
            # Replace the Deleted (if found) filter
            request_object[report_name]["filters"].append(replacement_filter)
        self.request_objects[interval].append(request_object)

        # print("new object --- ", json.dumps(request_object))

    async def run_simple_difference(self, simple_difference_options, report_name=None, edw2_ro=None, edw3_ro=None,
                                    interval=None, dashboard_regression=None,
                                    sim=None, force_picker=None, manual_path=None):

        async with self.sem:
            if report_name is None:
                report_name = self.report_name
            else:
                report_name = report_name

            if force_picker:
                picker_url_1 = force_picker
                picker_url_2 = force_picker
            else:
                picker_url_1 = self.edw3_url
                picker_url_2 = self.edw2_url
            if edw2_ro:
                edw2_request_object = edw2_ro
            else:
                edw2_request_object = self.edw2_request_object
            if edw3_ro:
                edw3_request_object = edw3_ro
            else:
                edw3_request_object = self.edw3_request_object
            # if interval:
            #     self.replace_relative_dates(interval, request_object=edw2_ro)
            #     self.replace_relative_dates(interval, request_object=edw3_ro)
            if sim and edw3_ro:
                self.insert_simulation(sim, request_object=edw3_request_object)
            if manual_path:
                simple_difference_options["manual_path"] = manual_path
            comparison = Comparison(sources.PickerReport(picker_url=picker_url_1,
                                                         report_name=report_name,
                                                         request_object=edw3_request_object),
                                    sources.PickerReport(picker_url=picker_url_2,
                                                         report_name=report_name,
                                                         request_object=edw2_request_object)
                                    )

            comparison.set_outputs(simple_report_name=self.report_name,
                                   simple_difference=simple_difference_options,
                                   dashboard_regression=dashboard_regression)
            await comparison.run_and_barf()
            self.comparisons["simple"].append(comparison.simple_difference_comparison)

            return comparison

    async def run_comparison(self, dates_hash, date_idx, edw2_request_object, edw3_request_object,
                             interval="day", force_picker_address=None):
        if date_idx == len(dates_hash["dates"]) - 1 and interval != 'day':
            print('hitting end condition \n \n \n')
            return
        start = dates_hash["dates"][date_idx]
        split_start = start.split('/')
        shiftable_start_date_obj = arrow.get(int(split_start[2]), int(split_start[0]), int(split_start[1]))
        end = dates_hash["dates"][date_idx]
        try:
            end = dates_hash["dates"][date_idx + 1]
        except IndexError:
            pass
        split_end = end.split('/')
        shiftable_end_date_obj = arrow.get(int(split_end[2]), int(split_end[0]), int(split_end[1]))

        async with self.sem:
            if self.simple_difference:
                self.check_replace(edw2_request_object, dates_hash, date_idx, interval,
                                   self.simple_difference["date_format"])
                self.check_replace(edw3_request_object, dates_hash, date_idx, interval,
                                   self.simple_difference["date_format"])
            else:
                self.check_replace(edw2_request_object, dates_hash, date_idx, interval, )
                self.check_replace(edw3_request_object, dates_hash, date_idx, interval, )
            if interval == 'day':
                edw2_report_name = self.report_name + "__" + start + "_edw2"
                edw3_report_name = self.report_name + "__" + start + "_edw3"
            elif interval == 'week':
                if date_idx == 0:
                    edw2_report_name = self.report_name + "__" + start + "--" + end + "__" + interval + "_edw2"
                    edw3_report_name = self.report_name + "__" + start + "--" + end + "__" + interval + "_edw3"
                else:
                    modified_start = shiftable_start_date_obj.shift(days=+1).strftime('%m/%d/%Y')
                    edw2_report_name = self.report_name + "__" + modified_start + "--" + end + "__" + interval + "_edw2" + "--"
                    edw3_report_name = self.report_name + "__" + modified_start + "--" + end + "__" + interval + "_edw3"
            elif interval == 'month':
                if date_idx == len(dates_hash["dates"]) - 2:
                    edw2_report_name = self.report_name + "__" + start + "--" + end + "__" + interval + "_edw2" + "--"
                    edw3_report_name = self.report_name + "__" + start + "--" + end + "__" + interval + "_edw3"
                else:
                    modified_end = shiftable_end_date_obj.shift(days=-1).strftime('%m/%d/%Y')
                    edw2_report_name = self.report_name + "__" + start + "--" + modified_end + "__" + interval + "_edw2" + "--"
                    edw3_report_name = self.report_name + "__" + start + "--" + modified_end + "__" + interval + "_edw3"

            report_a_address = self.edw3_url
            report_b_address = self.edw2_url
            if force_picker_address == "edw3":
                report_a_address = self.edw3_url
                report_b_address = self.edw3_url
            if force_picker_address == "edw2":
                report_a_address = self.edw2_url
                report_b_address = self.edw2_url
            if self.simple_difference:
                comparison = Comparison(sources.PickerReport(picker_url=report_a_address,
                                                             report_name=edw3_report_name,
                                                             currency=self.simple_difference["currency"],
                                                             request_object=edw3_request_object),
                                        sources.PickerReport(picker_url=report_b_address,
                                                             report_name=edw2_report_name,
                                                             currency=self.simple_difference["currency"],
                                                             request_object=edw2_request_object)
                                        )
            else:
                comparison = Comparison(sources.PickerReport(picker_url=report_a_address,
                                                             report_name=edw3_report_name,
                                                             request_object=edw3_request_object),
                                        sources.PickerReport(picker_url=report_b_address,
                                                             report_name=edw2_report_name,
                                                             request_object=edw2_request_object)
                                        )
            comparison_start_date = start
            comparison_end_date = end
            try:
                comparison_start_date = modified_start
            except UnboundLocalError:
                pass
            try:
                comparison_end_date = modified_end
            except UnboundLocalError:
                pass
            if interval == 'day':
                comparison_end_date = comparison_start_date

            comparison.set_outputs(output_xlsx=self.output_xlsx, interval=interval, simple_report_name=self.report_name,
                                   comparison_start_date=comparison_start_date, comparison_end_date=comparison_end_date,
                                   cascade=self.cascade,
                                   simple_difference=self.simple_difference,
                                   cascade_start_date=self.cascade_start_date, cascade_end_date=self.cascade_end_date)
            await comparison.run_and_barf()
            self.comparisons[interval].append(comparison)
            return comparison

    def insert_simulation(self, sim_name, request_object=None):
        request = request_object or self.edw3_request_object
        for report_id in request:
            for col in request[report_id]["cols"]:
                if "prepared_id" in col:
                    col["sim"] = sim_name

    def replace_relative_dates(self, interval, request_object=None):
        intervals = {
            "last_quarter": {
                "field": "dim_date-mm_dd_yyyy",
                "op": "relative_date",
                "values": [],
                "alias": "date_filter1",
                "allow_empty": self.true,
                "to_date": self.false,
                "count": 1,
                "start": -1,
                "period": "quarter"
            },
            "last_month": {
                "op": "relative_date",
                "field": "dim_date-mm_dd_yyyy",
                "period": "day",
                "start": -1,
                "count": 30,
                "allow_empty": self.true,
                "to_date": self.false
            },

            "last_year": {
                "field": "dim_date-mm_dd_yyyy",
                "op": "relative_date",
                "values": [

                ],
                "alias": "date_filter1",
                "allow_empty": self.true,
                "to_date": self.false,
                "count": 1,
                "start": -1,
                "period": "year"
            }
        }
        if request_object is None:
            for report_id in self.edw3_request_object:
                for request_filter in self.edw3_request_object[report_id]["filters"]:
                    if "period" in request_filter and "to_date" in request_filter:
                        if interval == "quarter":
                            del request_filter
                            self.edw3_request_object[report_id]["filters"].append(intervals["last_quarter"])
                        if interval == "month":
                            del request_filter
                            self.edw3_request_object[report_id]["filters"].append(intervals["last_month"])
                        if interval == "year":
                            del request_filter
                            self.edw3_request_object[report_id]["filters"].append(intervals["last_year"])
            for report_id in self.edw2_request_object:
                for request_filter in self.edw2_request_object[report_id]["filters"]:
                    if "period" in request_filter and "to_date" in request_filter:
                        if interval == "quarter":
                            del request_filter
                            self.edw2_request_object[report_id]["filters"].append(intervals["last_quarter"])
                        if interval == "month":
                            del request_filter
                            self.edw2_request_object[report_id]["filters"].append(intervals["last_month"])
                        if interval == "year":
                            del request_filter
                            self.edw2_request_object[report_id]["filters"].append(intervals["last_year"])
        else:
            for report_id in request_object:
                for request_filter in request_object[report_id]["filters"]:
                    if "period" in request_filter and "to_date" in request_filter:
                        if interval == "quarter":
                            del request_filter
                            request_object[report_id]["filters"].append(intervals["last_quarter"])
                        if interval == "month":
                            del request_filter
                            request_object[report_id]["filters"].append(intervals["last_month"])
                        if interval == "year":
                            del request_filter
                            request_object[report_id]["filters"].append(intervals["last_year"])

    async def dashboard_regression(self, categories=None, interval="last_month", sim=None, date_interval="Day",
                                   sem_count=None, merchants=None, merchant_name=None):
        if categories is None:
            categories = {
                "trending_widget": {"Sales": True, "Combined Commissions": True,
                                    "Affiliate Commission": True, "Network Commission": True,
                                    "Clicks % Impressions": True, "Adjustments": True
                                    },
                "top_affiliate_widget": {"Sales": True, "Combined Commissions": True,
                                         "Affiliate Commission": True, "Network Commission": True,
                                         "Clicks % Impressions": True, "Adjustments": True
                                         }
            }

        # Create a timestamped Directory to hold all reports
        timestamp = datetime.now().strftime("%x %X")
        self.timestamp = timestamp
        timestamped_label = '/validation_outputs/xlsx/dashboard_regression--' + timestamp.replace("/", "_")
        dashboard_regression_report_dir_path = os.path.join(os.getcwd() + timestamped_label)
        self.dashboard_regression_path = dashboard_regression_report_dir_path
        os.mkdir(dashboard_regression_report_dir_path)
        self.sem = asyncio.Semaphore(sem_count or self.semaphore_count)
        if merchant_name:
            merc_id = search_merchant(merchant_name=merchant_name)

        async def generate_reports(sim_name=None, merchant_id=None):
            futures = []
            if sim_name:
                dir_basepath = os.path.join(dashboard_regression_report_dir_path, sim_name)
            elif sim_name is None:
                # sim_name = self.production_sim_name
                # @TODO: Uncomment this ^ line and check for bug  - Commented to avoid no data *error* output
                dir_basepath = os.path.join(dashboard_regression_report_dir_path, self.production_sim_name)
            try:
                os.mkdir(dir_basepath)
            except FileExistsError:
                pass

            for widget in categories:
                if not categories[widget]:
                    continue
                for category in categories[widget]:

                    if not categories[widget][category]:
                        continue
                    try:
                        os.mkdir(os.path.join(dir_basepath, category))
                    except FileExistsError:
                        pass
                    for request_object_name in sources.dashboard_objects["edw2_dashboard_objects"][widget][category]:
                        edw2_request_object = sources.dashboard_objects["edw2_dashboard_objects"][widget] \
                            [category][request_object_name]
                        edw3_request_object = sources.dashboard_objects["edw3_dashboard_objects"][widget] \
                            [category][request_object_name]
                        for report_name in edw2_request_object:
                            for col in edw2_request_object[report_name]["cols"]:
                                if "dim_date" not in col["id"] and "hidden" not in col \
                                        and "website" not in col["name"].lower():
                                    if merchant_id:
                                        replace_merchant(edw2_request_object, merchant_id)
                                        replace_merchant(edw3_request_object, merchant_id)
                                        # merchant_path = os.path.join(dir_basepath, merchant)
                                        # try:
                                        # #     os.mkdir(merchant_path)
                                        # except FileExistsError:
                                        #     pass
                                        # print(f"{merchant_path} ----- 596, {merchant}")
                                    comparison_col_name = col["name"]
                                    lookup_merchant_name = search_merchant(merch_id=get_merchant_id(edw3_request_object))
                                    dashboard_regression = {"path": dir_basepath,
                                                            "category": category,
                                                            "dashboard report name": request_object_name,
                                                            "merchant": merchant_id or lookup_merchant_name,
                                                            "sim_name": sim_name
                                                            }

                                    match_names(edw2_request_object, edw3_request_object)

                                    verify_relative_dates(edw2_request_object, edw3_request_object)
                                    match_date_aggregates(edw2_request_object, edw3_request_object)
                                    futures.append(self.run_simple_difference(
                                        {"join_on": define_join_on(edw2_request_object, edw3_request_object),
                                         "comparison_col_name": comparison_col_name},
                                        edw2_ro=edw2_request_object, edw3_ro=edw3_request_object,
                                        interval=interval, sim=sim_name, report_name=comparison_col_name,
                                        dashboard_regression=dashboard_regression)
                                    )

            result = await asyncio.gather(*futures)
            # self.create_change_log(result, sim_name)
            if dashboard_regression is not None:
                self.write_dashboard_regression_summary(date_interval, sim_name)
            return result

        if sim:
            print("608 ********** RUNNING SIM \n\n")
            await generate_reports(sim, search_merchant(merch_id=merchant_name))
            print("608 ********** RUNNING Non-SIM \n\n")
            await generate_reports(merchant_id=search_merchant(merch_id=merchant_name))
            print("combining summaries")
            self.combine_summaries()
        # elif merchants:
        #     for name in merchants:
        #         await generate_reports(merchant=name)
        #         print("SYS EXIT -----631")
        #         sys.exit()
        # self.combine_summaries()
        else:
            print('RUNNING FROM HERE')
            await generate_reports(merchant_id=merc_id)
        # self.upload_change_log()

    def perspective_regression(self):
        pass

    def upload_change_log(self):
        scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
                 "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
        client = gspread.authorize(creds)
        sheet = client.open("AvantLink Validation Changelog").sheet1

        for log in self.change_logs:
            for prop in log:
                if log[prop] is None:
                    log[prop] = "N/A"
        sheet.append_rows(self.change_logs)

    def create_change_log(self, comparisons, sim_name):
        if sim_name is None:
            sim_name = self.production_sim_name
        self.totals["count"][sim_name] = {}
        self.totals["difference"][sim_name] = {}
        for comparison in comparisons:
            report_name = list(comparison.merge)[1].replace("_edw2", "")
            diff_col = comparison.merge[list(comparison.merge)[3]]
            self.totals["count"][sim_name][report_name] = 0
            self.totals["difference"][sim_name][report_name] = 0
            for val in diff_col.values.tolist():
                if int(val) != 0:
                    self.totals["count"][sim_name][report_name] += 1

                self.totals["difference"][sim_name][report_name] += float(val)

            self.change_logs.append({
                "Run Time": self.timestamp,
                "Simulation Name": sim_name,
                "Timeframe": None,
                "Dashboard": None,
                "Dashboard Category": comparison.dashboard_regression["category"],
                "Dashboard Report Name": comparison.dashboard_regression["dashboard report name"],
                "Records Passed (Total)": f"{len(diff_col) - int(self.totals['count'][sim_name][report_name])} / {len(diff_col)}",
                "Total Difference": self.totals["difference"][sim_name][report_name],
                "Calculation Val.": comparison.validations["calculations"],
                "OLAP Val.": comparison.validations["OLAP"],
                "Merchant ID": None,
                "Affiliate ID": None,
                "Admin ID": None,
                "Agency ID": None
            })

    def write_dashboard_regression_summary(self, date_interval, sim=None):
        summary = []
        if sim:
            basepath = os.path.join(self.dashboard_regression_path, sim)
            workbook_path = f"{self.dashboard_regression_path}/{self.dashboard_regression_path.split('/').pop()}" \
                            f"_summary_{sim}.xlsx"
        else:
            basepath = os.path.join(self.dashboard_regression_path, self.production_sim_name)
            workbook_path = f"{self.dashboard_regression_path}/{self.dashboard_regression_path.split('/').pop()}" \
                            f"_summary_{self.production_sim_name}.xlsx"

        def format_dates(date_string):
            storage = date_string.split("/")
            day = int(storage[1])
            month = int(storage[0])
            year = int(storage[2])
            return datetime(year, month, day).strftime("%m/%d/%Y")

        for directory in os.listdir(basepath):
            category_directory = os.path.join(basepath, directory)
            for entry in os.listdir(category_directory):

                if os.path.isfile(os.path.join(category_directory, entry)):
                    filepath = os.path.join(category_directory, entry)
                    report_dataframe = pd.read_excel(filepath, engine="openpyxl")
                    edw2_comparison_col_name = '{col_name}'.format(col_name=report_dataframe.columns[2])
                    edw3_comparison_col_name = '{col_name}'.format(col_name=report_dataframe.columns[3])
                    report_dataframe.rename({
                        edw2_comparison_col_name: "edw2_result",
                        edw3_comparison_col_name: "edw3_result"
                    }, axis=1, inplace=True)
                    try:
                        report_dataframe[date_interval] = [format_dates(date) for date in
                                                           report_dataframe[date_interval]]

                    except IndexError as e:
                        pass
                    except KeyError as e:
                        print(report_dataframe.head(2))
                    finally:
                        report_dataframe.dropna(axis="columns", how="all", inplace=True)
                        report_dataframe.to_excel(workbook_path, sheet_name=entry, encoding='utf-8')
                    summary.append(report_dataframe)
                else:
                    print(f"{os.path.join(category_directory, entry)} is not a file!!")

        summary = pd.concat(summary)
        summary = summary.drop(["Unnamed: 0"], axis=1)
        # summary.sort_values(by=date_interval, inplace=True)
        with pd.ExcelWriter(workbook_path) as writer:
            summary.to_excel(writer, sheet_name="Summary", engine='openpyxl', encoding='utf-8')
            summary.swapaxes("index", "columns").to_excel(writer, sheet_name="Summary_inverted",
                                                          engine='openpyxl', encoding='utf-8')

    def combine_summaries(self):
        summaries = []
        base_dataframe = None
        for entry in os.listdir(self.dashboard_regression_path):
            if "summary" in entry:
                filepath = os.path.join(self.dashboard_regression_path, entry)
                if self.production_sim_name in filepath:
                    base_dataframe = pd.read_excel(filepath, engine="openpyxl")
                    continue
                summaries.append({"dataframe": pd.read_excel(filepath, engine="openpyxl"),
                                  "name": entry})
        for idx, summary in enumerate(summaries):
            col_a = summary["dataframe"]["edw3_result"]
            col_b = summary["dataframe"]["difference"]
            sim_name = re.search("_summary_\w+_dev", summary["name"]).group(0).replace("_summary_", "")
            base_dataframe[f"{sim_name}_edw3_result"] = col_a
            base_dataframe[f"{sim_name}_difference"] = col_b
        with pd.ExcelWriter(os.path.join(self.dashboard_regression_path, "combined_summary.xlsx")) as writer:

            base_dataframe.to_excel(writer, engine="openpyxl", encoding="utf-8")

    def process_prepared_ids(self, ro):
        ro_key = ''
        replacement_cols = []
        for key in ro:
            ro_key = key
        for idx, col in enumerate(ro[ro_key]["cols"]):
            if "id" in col:
                replacement_cols.append(col)
                continue
            replacement = self.prepared_col_map[col["prepared_id"]]["definition"]
            replacement_cols.append(replacement)
        del ro[ro_key]["cols"]
        ro[ro_key]["cols"] = replacement_cols
        return ro


def replace_merchant(ro, merchant_id):
    for report_id in ro:
        for filter in ro[report_id]["filters"]:
            if filter["field"] == "dim_merchant-merchant_uuid":
                new_filter = {
                    "field": "dim_merchant-merchant_uuid",
                    "op": "eq",
                    "values": [
                        f"{merchant_id}"
                    ],
                    "alias": "merchant_filter1"
                }
                del filter
                ro[report_id]["filters"].append(new_filter)


def relative_to_exact_date(ro, start_date, end_date):
    new_date_filter = {
        "field": "dim_date-mm_dd_yyyy",
        "op": "between",
        "values": [
            start_date,
            end_date
        ]
    }
    for report_id in ro:
        for filter in ro[report_id]["filters"]:
            if filter["field"] == "dim_date-mm_dd_yyyy" and filter["op"] == "relative_date":
                del filter
                ro[report_id]["filters"].append(new_date_filter)
    return ro


def drop_columns(drop_list, ro):
    ro_key = ''
    for key in ro:
        ro_key = key
    for col in ro[ro_key]["cols"]:
        if col["name"] in drop_list:
            del col


def search_merchant(merchant_name=None, merch_id=None):
    merchant_map = json.load(open('./sources/json_sources/merchant_map.json'))
    if merchant_name:
        for merchant_id in merchant_map:
            if merchant_map[merchant_id].lower() == merchant_name.lower():
                return merchant_id
    if merch_id:
        return merchant_map[merch_id]


def replace_merchant(ro, merchant_id):
    new_filters = []
    if len(merchant_id) != 36:
        merchant_id = search_merchant(merchant_name=merchant_id)
    for report_id in ro:
        for filter in ro[report_id]["filters"]:
            if filter["field"] == "dim_merchant-merchant_uuid" and filter['values'] != f"{merchant_id}":
                new_filter = {
                    "field": "dim_merchant-merchant_uuid",
                    "op": "eq",
                    "values": [
                        f"{merchant_id}"
                    ],
                    "alias": "merchant_filter1"
                }
                new_filters.append(new_filter)
                ro[report_id]["filters"].remove(filter)
        for new_filter in new_filters:
            ro[report_id]["filters"].append(new_filter)


def align_columns(ro):
    '''
    This helper function pulls in a request object and nicely aligns all the columns
    It will set up the request objects so they are in the same order with the same name list

    Paramters:
        ro: json request object, cotains the full complete edw2/3 ro
    Returns:
        names: list, gives all of the output names for the ro
        ro: json request object, returns the modified request object
        skipped_indices: list, gives a list of indices we skipped because they don't have a name
    '''
    names = []
    skipped_indices = []
    hidden_indices = []
    for report_id in ro:
        for index, column in enumerate(ro[report_id]["cols"]):
            # Only continue if hidden is not present
            try:
                test = column["hidden"]
                hidden = True
                hidden_indices.append(index)
            except:
                hidden = False
            if hidden is False:
                try:
                    names.append(column["name"])
                # If there's an error, then it's a dim
                # For edw2, log any skipped columns to remove from edw3
                except KeyError:
                    skipped_indices.append(index)
    return ro, names, skipped_indices, hidden_indices


def match_names(edw2_ro, edw3_ro):
    '''
    If the name of the columns is different, let's rename them to match
    This also raises an exception if the lengths don't match
    '''
    edw3_ro, edw3_names, edw3_skip, edw3_hidden_indices = align_columns(edw3_ro)
    edw2_ro, edw2_names, skipped_indices, edw2_hidden_indices = align_columns(edw2_ro)

    # Drop any skipped indices
    for index in skipped_indices:
        edw3_names.pop(index)

    # There exists a possibility that we had prepared_ids in edw3 with no name
    # If that is the case, add that in now
    if len(edw2_names) > len(edw3_names):
        for index, name in enumerate(edw2_names):
            try:
                test = edw3_names[index]
            except IndexError:
                edw3_names.append(name)

    # Make sure the length of the columns is the same
    # If it is, update the edw3 request obj to have the same names as edw2
    if len(edw2_names) == len(edw3_names):
        for index, name in enumerate(edw3_names):
            if edw3_names[index] != edw2_names[index]:
                for report_id in edw3_ro:
                    if index in edw3_hidden_indices:
                        try:
                            edw3_ro[report_id]["cols"][index + 1]["name"] = edw2_names[index]
                        except IndexError:
                            continue  # Indicates last entry is a hidden column
                    else:
                        edw3_ro[report_id]["cols"][index]["name"] = edw2_names[index]
    else:
        print(edw2_names)
        print(edw3_names)
        print(edw3_ro)
        raise Exception('The length of the edw2 column names does not match edw3')


def remove_hidden(ro, reversal=None):
    hidden_count = 0
    ro_key = ''
    for key in ro:
        ro_key = key
    for col in ro[ro_key]["cols"]:
        if "hidden" in col:
            if reversal:
                col["hidden"] = False
            col["name"] = f"hidden_col_{hidden_count}"
            hidden_count += 1


def remove_date_aggregates(ro):
    ro_key = ''
    for key in ro:
        ro_key = key
    for col in ro[ro_key]["cols"]:
        try:
            if "dim_date" in col["id"]:
                if "aggregate" in col:
                    del col["aggregate"]
        except KeyError:
            pass


def remove_sort(ro):
    ro_key = ''
    for key in ro:
        ro_key = key
    del ro[ro_key]["sort"]


def verify_relative_dates(ro_1, ro_2, match=True):
    ro_key_1 = ''
    ro_key_2 = ''
    ro_1_filter = None
    ro_2_filter = None
    for key in ro_1:
        ro_key_1 = key
    for key in ro_2:
        ro_key_2 = key
    for filter_1 in ro_1[ro_key_1]["filters"]:
        if filter_1["op"] == "relative_date":
            ro_1_filter = filter_1
    for filter_2 in ro_2[ro_key_2]["filters"]:
        if filter_2["op"] == "relative_date":
            ro_2_filter = filter_2
    if match:
        del ro_2_filter
        ro_2[ro_key_2]["filters"].append(ro_1_filter)
        return
    for key in ro_1_filter:
        try:
            if ro_1_filter[key] != ro_2_filter[key]:
                print(f"Edw2 filter  === \n {ro_1_filter} \n Edw3 filter === \n {ro_2_filter}")
                raise Exception(
                    "mismatching relative date filters -Check the values of the relative date filters in the request objects are matching")
        except KeyError:
            print(f"Edw2 filter  === \n {ro_1_filter} \n Edw3 filter === \n {ro_2_filter}")
            raise Exception(
                "mismatching relative date filters -Check the values of the relative date filters in the request objects are matching")


def match_date_aggregates(ro_1, ro_2):
    """
    verifies that date aggregates in dim_date cols are matching. if they are not - replicates a copy of one to the other.
    sets ro_2 as the source of truth for which dim_date col will be copied to the other.
    Args:
        ro_1: Edw(2 or 3) request object
        ro_2: Edw(2 or 3) request object

    Returns:

    """
    ro_key_1 = ''
    ro_key_2 = ''
    ro_1_filter = None
    ro_2_filter = None
    source_of_truth = None
    for key in ro_1:
        ro_key_1 = key
    for key in ro_2:
        ro_key_2 = key
    try:
        for col_1 in ro_1[ro_key_1]["cols"]:
            if "dim_date" in col_1["id"]:
                source_of_truth = col_1
        for col_2 in ro_2[ro_key_2]["cols"]:
            if "dim_date" in col_2["id"]:
                col_2["aggregate"] = []
                col_2["aggregate"].append(source_of_truth["aggregate"][0])
    except KeyError:
        pass


def get_merchant_id(ro):
    key = ''
    for ro_key in ro:
        key = ro_key
    for ro_filter in ro[key]["filters"]:
        if ro_filter["field"] == "dim_merchant-merchant_uuid":
            return ro_filter["values"][0]


def define_join_on(ro1, ro2):
    join_on = []
    ro_key = ''
    ro_key_2 = ''
    edw3_col_names = []
    for key in ro1:
        ro_key = key
    for key in ro2:
        ro_key_2 = key
    for col in ro1[ro_key]["cols"]:
        try:
            if "dim_date" in col["id"]:
                join_on.append(col["name"])

            elif "name" in col["name"].lower() or "website" in col["name"].lower():
                join_on.append(col["name"])
        except KeyError:
            pass
    for col in ro2[ro_key_2]["cols"]:
        if "hidden" in col:
            if col["hidden"] is True:
                continue
        elif "prepared_id" in col:
            continue
        else:
            edw3_col_names.append(col["name"])
    for col_name in join_on:
        if col_name not in edw3_col_names:
            raise Exception(
                f"Join columns established were {join_on} -- a column named -- {col_name}  -- was not found in the EDW3 Request Object Columns")
    return join_on


def main():
    # Define comparison column name and join_on vars here

    # Instantiate the class
    cascade = Cascade()
    cascade.semaphore_count = 3
    cascade.get_prepared_cols()
    cascade.get_display_groups()

    if args.manual:
        try:
            request_objects = json.load(open('./sources/json_sources/manual_comparison_objects.json'))
        except FileNotFoundError as e:
            print(f"A json File containing an edw2 and edw3 request object "
                  f"must be created @@ {e}")
            raise e

        # edw2_ro = cascade.process_prepared_ids(request_objects["edw2_request_object"])
        # edw3_ro = cascade.process_prepared_ids(request_objects["edw3_request_object"])
        edw2_ro = request_objects["edw2_request_object"]
        edw3_ro = request_objects["edw3_request_object"]

        sim = args.sim or None
        if args.join:
            join_on = args.join.split(',')
            join_on = [col_name.strip() for col_name in join_on]
        else:
            join_on = define_join_on(edw2_ro, edw3_ro)

        if args.start_date and args.end_date:
            relative_to_exact_date(edw2_ro, args.start_date, args.end_date)
            relative_to_exact_date(edw3_ro, args.start_date, args.end_date)

        if args.merchant:
            replace_merchant(edw2_ro, args.merchant)
            replace_merchant(edw3_ro, args.merchant)

        # if args.remove: #TODO: Implement
        #     drop_columns(args.drop, edw2_ro)
        #     drop_columns(args.drop, edw3_ro)
        match_names(edw2_ro, edw3_ro)
        lookup_name = search_merchant(id=get_merchant_id(edw3_ro))
        verify_relative_dates(edw2_ro, edw3_ro)
        match_date_aggregates(edw2_ro, edw3_ro)
        timestamp = datetime.now().strftime("%x %X")
        timestamped_label = '/validation_outputs/xlsx/manual_comparison--' + timestamp.replace("/", "_")
        manual_comparison_report_dir_path = os.path.join(os.getcwd() + timestamped_label)
        os.mkdir(manual_comparison_report_dir_path)
        for report_key in edw2_ro:
            for col in edw2_ro[report_key]["cols"]:
                if "prepared_id" in col:
                    continue
                if not args.comparison_column:
                    try:
                        if "dim_date" not in col["id"] and "hidden" not in col \
                                and "website" not in col["name"].lower():
                            comparison_col_name = col["name"]
                    except TypeError:
                        raise
                else:
                    comparison_col_name = args.comparison_column
            loop = asyncio.new_event_loop()
            try:
                start = datetime.now()
                # code ...
                loop.run_until_complete(
                    cascade.run_simple_difference(
                        {"join_on": join_on,
                         "comparison_col_name": comparison_col_name},
                        edw2_ro=edw2_ro, edw3_ro=edw3_ro, sim=sim, report_name=comparison_col_name,
                        manual_path=manual_comparison_report_dir_path)
                )
                print("Total runtime: ", datetime.now() - start)
            except KeyboardInterrupt:
                sys.exit()
            finally:
                loop.close()

    # Instructions for Automated Dashboard Regression
    else:
        print("Dashboard Regression - Automated - Request Objects: Hard Coded \n \n")
        categories = ["Sales"]
                      # ,"Combined Commission", "Network Commission",
                      # "Clicks % Impressions", "Adjustments", "Affiliate Commission"]
        run_categories = {"trending_widget": False, "top_affiliates_widget": False}
        minimum_flag = False
        if args.run_all:
            for widget in run_categories:
                run_categories[widget] = {}
                for category in categories:
                    run_categories[widget][category] = True
            sim = args.sim or None
            start = datetime.now()
            loop = asyncio.new_event_loop()
            merchants = None
            merchant_name = None
            if args.multi_merchant:
                merchants = args.multi_merchant.split(',')
                merchants = [col_name.strip() for col_name in merchants]
            if args.merchant:
                merchant_name = args.merchant
            try:
                start = datetime.now()
                # code ...
                loop.run_until_complete(
                    cascade.dashboard_regression(categories=run_categories, interval="last month",
                                                 sem_count=3, sim=sim, merchants=merchants, merchant_name=merchant_name)
                )
            except KeyboardInterrupt:
                sys.exit()
            finally:
                loop.close()
                print("Total runtime: ", datetime.now() - start)
                sys.exit()
        print("Select the widgets you would like to perform regression over (Y/n) \n")
        for widget in run_categories:
            user_input = input(f" \n --{widget}? \n")
            if user_input == "True" or user_input == "T" or user_input == 't' or user_input == "Y" or user_input == "y":
                run_categories[widget] = True
            elif user_input == "False" or user_input == "F" or user_input == 'f' or user_input == "N" or user_input == "n":
                run_categories[widget] = False
            else:
                print("Invalid input provided: {user_input} -- ".format(user_input=user_input) +
                      " -- The input must be either ('True', 'T', 't', or 'y' - For True) " +
                      "or ('False', 'F', 'f', or 'n' - For False)")
            if not run_categories:
                print(run_categories)
            if run_categories[widget]:
                for category in categories:
                    user_input = input(f"Would you like to run regression on {category}? \n")
                    if run_categories[widget] is True:
                        run_categories[widget] = {}
                    if user_input == "True" or user_input == "T" or user_input == 't' or user_input == "y":
                        run_categories[widget][category] = True
                        minimum_flag = True
                    elif user_input == "False" or user_input == "F" or user_input == 'f' or user_input == "n":
                        run_categories[widget][category] = False
                    else:
                        print(f"Invalid input provided: {user_input} -- " +
                              " -- The input must be either ('True', 'T', 't', or 'y' - For True) " +
                              "or ('False', 'F', 'f', or 'n' - For False)")
        if not minimum_flag:
            raise IndexError(
                "USER INPUT ERROR: No Request Objects were added to the list of Reports to run in the regression test assisted options."
                "Must reply to atleast one category with True ('True', 'T', 't', or 'y')")

        sim = input("Would you like to specify a build (kiran_dev, adam_dev etc.)? if so - specify the name of it.")
        if sim == "":
            sim = None
        merchants = None
        if args.multi_merchant:
            merchants = args.multi_merchant.split(',')
            merchants = [col_name.strip() for col_name in merchants]
        # Start event loop for the given function
        loop = asyncio.new_event_loop()
        try:
            start = datetime.now()
            # code ...
            loop.run_until_complete(
                cascade.dashboard_regression(categories=run_categories, interval="last quarter",
                                             sem_count=3, sim=sim, merchants=merchants)
            )
            print("Total runtime: ", datetime.now() - start)
        except KeyboardInterrupt:
            sys.exit()
        finally:
            loop.close()


if __name__ == '__main__':
    main()
    pass
