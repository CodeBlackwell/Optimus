import sources
from sources.comparison import define_join_on

import re
import asyncio
import json
from datetime import datetime
from pprint import pprint
import sys
import os




false = False
true = True
null = None

request_objects = json.load(open('./sources/json_sources/manual_comparison_objects.json'))


def extract_words(messy_string):
    regex = re.compile('[^a-zA-Z]')
    messy_string = regex.sub(' ', messy_string)
    cleaned_string = " ".join(messy_string.split())
    return cleaned_string


def breakdown_calculations(calc_request_object: object) -> object:
    report_id = None
    calculation = None
    calculation_variables = None
    for id in calc_request_object:
        report_id = id
    for col in calc_request_object[report_id]["cols"]:
        if col["id"] == "calculation":
            calculation = col["calc"]
            calculation_variables = extract_words(calculation).split(' ')
    return calculation_variables


def build_single_var_request_object(calc_request_object, col_name):
    report_id = None
    calc_object = calc_request_object.copy()
    for id in calc_request_object:
        report_id = id
    for col in calc_object[report_id]["cols"]:
        if col["id"] == "calculation":
            col["calc"] = col_name
            col["name"] = col_name
            col["alias"] = col_name
    return {"ro": calc_object, "var_name": col_name}


def build_var_separated_request_objects(calc_request_object):
    result = []
    calculation_vars = breakdown_calculations(calc_request_object)
    for var in calculation_vars:
        separated_object = build_single_var_request_object(calc_request_object, var)
        result.append(separated_object)
    return result


def match_var_object_pairs(edw2_objects_list, edw3_objects_list):
    pairs = {}
    for single_var_request in edw2_objects_list:
        if single_var_request["var_name"] not in pairs:
            pairs[single_var_request["var_name"]] = []
        pairs[single_var_request["var_name"]].append(single_var_request["ro"])
    for single_var_request in edw3_objects_list:
        pairs[single_var_request["var_name"]].append(single_var_request["ro"])
    return pairs


def run_reports(request_object_pairs_list):
    timestamp = datetime.now().strftime("%x %X")
    timestamped_label = '/validation_outputs/xlsx/calc_breakdown--' + timestamp.replace("/", "_")
    calc_breakdown_report_dir_path = os.path.join(os.getcwd() + timestamped_label)
    os.mkdir(calc_breakdown_report_dir_path)
    # futures = []

    for key in request_object_pairs_list:
        comparison = sources.Cascade()
        comparison_col_name = None
        edw2_request_object = request_object_pairs_list[key][0]
        edw3_request_object = request_object_pairs_list[key][1]
        join_on = define_join_on(edw2_request_object, edw3_request_object)
        for report_id in edw3_request_object:
            for col in edw3_request_object[report_id]["cols"]:
                if "prepared_id" in col:
                    continue
                try:
                    if "dim_date" not in col["id"] and "hidden" not in col \
                            and "website" not in col["name"].lower():
                        comparison_col_name = col["name"]
                except TypeError:
                    raise
        loop = asyncio.new_event_loop()
        print(f"Comparison col name is defined as {comparison_col_name}, manpath = {calc_breakdown_report_dir_path}")
        try:
            start = datetime.now()
            # code ...
            loop.run_until_complete(
                comparison.run_simple_difference(
                    {"join_on": join_on,
                     "comparison_col_name": comparison_col_name},
                    edw2_ro=edw2_request_object, edw3_ro=edw3_request_object, sim=None, source=None,
                    report_name=key, manual_path=calc_breakdown_report_dir_path)
            )
            print("Total runtime: ", datetime.now() - start)
        except KeyboardInterrupt:
            sys.exit()
        except asyncio.TimeoutError as e:
            print(e)
        finally:
            loop.close()


if __name__ == '__main__':
    edw2_var_objects = build_var_separated_request_objects(request_objects["edw2_request_object"])
    edw3_var_objects = build_var_separated_request_objects(request_objects["edw3_request_object"])
    pairs = match_var_object_pairs(edw2_var_objects, edw3_var_objects)
    run_reports(pairs)