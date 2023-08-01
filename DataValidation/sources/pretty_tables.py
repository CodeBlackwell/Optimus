import copy
import os
import json
import sys

from pprint import pprint
import pandas as pd

import sources


class PrettyTableMaker:
    tables_list = []
    summary_tables = []
    category_literal = {
        "trending_widget": {
            "Sales": {
                "Sales": {},
                "ROAS %": {},
                "ROAS": {},
                "Orders": {},
                "Gross Sales": {},
                "Conversion Rate": {},
                "Average Order Amount": {}
            },
            "Combined Commission": {
                "Total Cost": {},
                "Sale Commission": {},
                "Paid Placement": {},
                "Incentive Commission": {},
                "CPC": {},
                "Bonus": {}
            },
            "Network Commission": {
                "Network Bonus": {},
                "Network CPC": {},
                "Network Paid Placement": {},
                "Network Sale Commission": {},
                "Network Total Commission Average Rate": {},
                "Network Total Earnings": {},
                "Network Total Earnings Average Rate": {}
            },
            "Clicks % Impressions": {
                "Click Through Rate": {},
                "Clicks": {},
                "Impressions": {}
            },
            "Adjustments": {
                "Adjusted Affiliate Earnings": {},
                "Adjusted Sales": {},
                "Adjustments": {},
                "Reversal Rate": {}
            },
            "Affiliate Commission": {
                "Affiliate Bonus": {},
                "Affiliate CPC": {},
                "Affiliate Incentive Commission": {},
                "Affiliate Paid Placement": {},
                "Affiliate Sale Commission": {},
                "Affiliate Total Commission Average Rate": {},
                "Affiliate Total Earnings": {},
                "Affiliate Total Earnings Average Rate": {},
                "EPC": {}
            }
        },
        "top_affiliates_widget": {
            "Sales": {
                "Average Order Amount": {},
                "Sales": {},
                "ROAS %": {},
                "ROAS": {},
                "Orders": {},
                "Gross Sales": {},
                "Conversion Rate": {}
            },
            "Combined Commission": {
                "Total Cost": {},
                "Sale Commission": {},
                "Paid Placement": {},
                "Incentive Commission": {},
                "CPC": {},
                "Bonus": {}
            },
            "Affiliate Commission": {
                "Affiliate Bonus": {},
                "Affiliate CPC": {},
                "Affiliate Incentive Commission": {},
                "Affiliate Paid Placement": {},
                "Affiliate Sale Commission": {},
                "Affiliate Total Commission Average Rate": {},
                "Affiliate Total Earnings": {},
                "Affiliate Total Earnings Average Rate": {},
                "EPC": {}
            },
            "Network Commission": {
                "Network CPC": {},
                "Network Paid Placement": {},
                "Network Bonus": {},
                "Network Sale Commission": {},
                "Network Total Commission Average Rate": {},
                "Network Total Earnings": {},
                "Network Total Earnings Average Rate": {}
            },
            "Clicks % Impressions": {
                "Click Through Rate": {},
                "Clicks": {},
                "Impressions": {}
            },
            "Adjustments": {
                "Adjusted Affiliate Earnings": {},
                "Adjusted Cost": {},
                "Adjusted Network Earnings": {},
                "Adjusted Sales": {},
                "Adjustments": {},
                "Reversal Rate": {}
            }
        }
    }
    report_index_map = {
        "trending_widget": {
            "Sales": {
                "Sales": 3,
                "ROAS %": 4,
                "ROAS": 5,
                "Gross Sales": 6,
                "Conversion Rate": 7,
                "Average Order Amount": 8
            },
            "Combined Commission": {
                "Total Cost": 10,
                "Sale Commission": 11,
                "Paid Placement": 12,
                "Incentive Commission": 13,
                "CPC": 14,
                "Bonus": 15
            },
            "Network Commission": {
                "Network Bonus": 17,
                "Network CPC": 18,
                "Network Paid Placement": 19,
                "Network Sale Commission": 20,
                "Network Total Commission Average Rate": 21,
                "Network Total Earnings": 22,
                "Network Total Earnings Average Rate": 23
            },
            "Clicks % Impressions": {
                "Click Through Rate": 25,
                "Clicks": 26,
                "Impressions": 27
            },
            "Adjustments": {
                "Adjusted Affiliate Earnings": 29,
                "Adjusted Sales": 30,
                "Adjustments": 31,
                "Reversal Rate": 32
            },
            "Affiliate Commission": {
                "Affiliate Bonus": 34,
                "Affiliate CPC": 35,
                "Affiliate Incentive Commission": 36,
                "Affiliate Paid Placement": 37,
                "Affiliate Sale Commission": 38,
                "Affiliate Total Commission Average Rate": 39,
                "Affiliate Total Earnings Average Rate": 40,
                "Affiliate Total Earnings": 41,
                "EPC": 42
            }
        },
        "top_affiliates_widget": {
            "Sales": {
                "Average Order Amount": 3,
                "Sales": 4,
                "ROAS %": 5,
                "ROAS": 6,
                "Orders": 7,
                "Gross Sales": 8,
                "Conversion Rate": 9
            },
            "Combined Commission": {
                "Total Cost": 11,
                "Sale Commission": 12,
                "Paid Placement": 13,
                "Incentive Commission": 14,
                "CPC": 15,
                "Bonus": 16
            },
            "Network Commission": {
                "Network CPC": 18,
                "Network Paid Placement": 19,
                "Network Bonus": 20,
                "Network Sale Commission": 21,
                "Network Total Commission Average Rate": 22,
                "Network Total Earnings": 23,
                "Network Total Earnings Average Rate": 24
            },
            "Clicks % Impressions": {
                "Click Through Rate": 26,
                "Clicks": 27,
                "Impressions": 28
            },
            "Adjustments": {
                "Adjusted Affiliate Earnings": 30,
                "Adjusted Sales": 31,
                "Adjustments": 32,
                "Reversal Rate": 33,
                "Adjusted Cost": 34,
                "Adjusted Network Earnings": 35
            },
            "Affiliate Commission": {
                "Affiliate Bonus": 37,
                "Affiliate CPC": 38,
                "Affiliate Incentive Commission": 39,
                "Affiliate Paid Placement": 40,
                "Affiliate Sale Commission": 41,
                "Affiliate Total Commission Average Rate": 42,
                "Affiliate Total Earnings Average Rate": 43,
                "Affiliate Total Earnings": 44,
                "EPC": 45
            }
        }
    }
    reversed_report_index_map = {
        'top_affiliates_widget': {},
        'trending_widget': {}
    }
    start_date = None
    end_date = None
    date_range = []
    categorical_report = {
        'top_affiliates_widget': {
            'Adjustments': {'Adjusted Affiliate Earnings': '',
                            'Adjusted Cost': '',
                            'Adjusted Network Earnings': '',
                            'Reversal Rate': ''},
            'Affiliate Commission': {'Affiliate Bonus': '',
                                     'Affiliate CPC': '',
                                     'Affiliate Incentive Commission': '',
                                     'Affiliate Paid Placement': '',
                                     'Affiliate Sale Commission': '',
                                     'Affiliate Total Commission Average Rate': '',
                                     'Affiliate Total Earnings': '',
                                     'Affiliate Total Earnings Average Rate': '',
                                     'EPC': ''},
            'Clicks % Impressions': {'Click Through Rate': '',
                                     'Clicks': '',
                                     'Impressions': ''},
            'Combined Commission': {'Bonus': '',
                                    'CPC': '',
                                    'Incentive Commission': '',
                                    'Paid Placement': '',
                                    'Sale Commission': '',
                                    'Total Cost': ''},
            'Network Commission': {'Network Bonus': '',
                                   'Network CPC': '',
                                   'Network Paid Placement': '',
                                   'Network Sale Commission': '',
                                   'Network Total Commission Average Rate': '',
                                   'Network Total Earnings': '',
                                   'Network Total Earnings Average Rate': ''},
            'Sales': {'Average Order Amount': '',
                      'Conversion Rate': '',
                      'Gross Sales': '',
                      'Orders': '',
                      'ROAS': '',
                      'ROAS %': '',
                      'Sales': ''}},
        'trending_widget': {'Adjustments': {'Adjusted Affiliate Earnings': '',
                                            'Adjusted Sales': '',
                                            'Adjustments': '',
                                            'Reversal Rate': ''},
                            'Affiliate Commission': {'Affiliate Bonus': '',
                                                     'Affiliate CPC': '',
                                                     'Affiliate Incentive Commission': '',
                                                     'Affiliate Sale Commission': '',
                                                     'Affiliate Total Commission Average Rate': '',
                                                     'Affiliate Total Earnings': '',
                                                     'Affiliate Total Earnings Average Rate': '',
                                                     'EPC': ''},
                            'Clicks % Impressions': {'Click Through Rate': '',
                                                     'Clicks': '',
                                                     'Impressions': ''},
                            'Combined Commission': {'Bonus': '',
                                                    'CPC': '',
                                                    'Incentive Commission': '',
                                                    'Paid Placement': '',
                                                    'Sale Commission': '',
                                                    'Total Cost': ''},
                            'Network Commission': {'Network Bonus': '',
                                                   'Network CPC': '',
                                                   'Network Paid Placement': '',
                                                   'Network Sale Commission': '',
                                                   'Network Total Commission Average Rate': '',
                                                   'Network Total Earnings': '',
                                                   'Network Total Earnings Average Rate': ''},
                            'Sales': {'Average Order Amount': '',
                                      'Conversion Rate': '',
                                      'Gross Sales': '',
                                      'ROAS': '',
                                      'ROAS %': '',
                                      'Sales': ''}}}
    merchant_result_overview = {
        "Last Test": None,
        "Merchant": None,
        "Currency": None,
        "Network": None,
        "Sales": None,
        "Combined Commission": None,
        "Network Commission": None,
        "Clicks & Impressions": None,
        "Adjustments": None,
        "Affiliate Commission": None
    }
    dir_path = None

    def build_reverse_index_map(self):
        result = {}
        for widget in self.report_index_map:
            result[widget] = {}
            for category in self.report_index_map[widget]:
                for report_name in self.report_index_map[widget][category]:
                    result[widget][self.report_index_map[widget][category][report_name]] = {category: report_name}
        self.reversed_report_index_map = result
        return result

    def run(self):
        self.retrieve_tables()
        self.generate_test_account_overview_update_literal()
        self.build_reverse_index_map()
        self.generate_merchant_reports()
        return self.merchant_result_overview, self.categorical_report

    def retrieve_tables(self):
        sim_dir = os.listdir(self.dir_path)
        sim_path = os.path.join(self.dir_path, sim_dir[0])
        source_name = os.listdir(sim_path)[0]
        source_path = os.path.join(sim_path, source_name)

        source_path_files = os.listdir(source_path)
        for widget in source_path_files:
            if os.path.isdir(os.path.join(source_path, widget)):
                widget_path = os.path.join(source_path, widget)
                for category in os.listdir(widget_path):
                    category_path = os.path.join(widget_path, category)
                    for filename in os.listdir(category_path):
                        filepath = os.path.join(category_path, filename)
                        new_df = pd.read_excel(filepath)
                        if self.start_date is None:
                            self.start_date = new_df["Day"].values[0]
                        if self.end_date is None:
                            self.end_date = new_df["Day"].values[-1]
                        if self.start_date is not None and self.end_date is not None:
                            self.date_range = f"{self.start_date} - {self.end_date}]"
                        self.tables_list.append(new_df)
            else:
                summary_name = os.path.join(source_path, widget)
                self.summary_tables.append(pd.read_excel(summary_name))

    def generate_test_account_overview_update_literal(self):
        """
         create the object used to update Test Accounts Overview. This overview shows a compressed view of
         each merchant being tested listing the following;
         -1 merchant per row,
         -each category of tests run, if fails are present - the names of the failed reports will be listed in the cell

        Returns:
            None  - Side effect = set self.merchant_result_overview (see class definition self.merchant_result_overview)
        """

        result = {}
        if len(self.summary_tables) > 1:
            for summary in self.summary_tables:
                for index, row in summary.iterrows():
                    widget_name = row["widget"]
                    category_name = row["Dashboard Category"]
                    # Check if the widget is in the result already, if not - create entry
                    if widget_name not in result:
                        result[widget_name] = {}
                    # Check if the category is in the widget result already, if not - create entry
                    if category_name not in result[widget_name]:
                        result[widget_name][category_name] = {}
            for summary in self.summary_tables:
                for index, row in summary.iterrows():
                    widget_name = row["widget"]
                    category_name = row["Dashboard Category"]
                    if row["Dashboard Report Name"] not in result[widget_name][category_name]:
                        result[widget_name][category_name][row["Dashboard Report Name"]] = row['pass/fail']

        result["Last Test"] = self.dir_path.split("/").pop()
        result["Merchant"] = self.get_merchant()
        result["Currency"] = self.get_currency()
        result["SQL_source"] = self.get_sql_source()
        result["Date Range"] = self.date_range
        # # @TODO: figure out how to know which network the test was run for - consult Zach.
        result["Network"] = None
        self.merchant_result_overview = result

    def generate_merchant_reports(self):
        overview = copy.deepcopy(self.merchant_result_overview)
        result = {
            "top_affiliates_widget": [],
            "trending_widget": []
        }
        for widget_key in overview:
            if "widget" in widget_key:
                for cell in range(list(self.reversed_report_index_map[widget_key].keys()).pop() + 1):
                    if cell not in self.reversed_report_index_map[widget_key]:
                        result[widget_key].append([])
                    else:
                        category_literal = self.reversed_report_index_map[widget_key][cell]
                        category = list(category_literal.keys()).pop()
                        report_name = category_literal[category]
                        try:
                            result[widget_key].append(
                                [self.merchant_result_overview[widget_key][category][report_name]])
                        except KeyError:
                            result[widget_key].append([f"N/A"])

        for widget_key in result:
            result[widget_key].pop(0)
            result[widget_key].insert(0, [self.convert_run_time()])
        self.categorical_report = result

    # def upload_test_account_overview(self):
    #     pass
    #
    # def upload_merchant_report(self):
    #     pass

    def get_currency(self):
        """
        Returns:
            string - Currency listed in the request Object for the comparison
        """
        for report in self.tables_list[0]["edw3_request_object"]:
            ro = json.loads(report)
            for ro_key in ro:
                for key in ro[ro_key]:
                    if key == "currency":
                        return ro[ro_key][key]

    def get_sql_source(self):
        """
                Returns:
                    string - data source used for the comparison
                """
        return self.tables_list[0]["SQL_source"][0]

    def convert_run_time(self):
        ugly_runtime = self.dir_path.split("/").pop()
        clean_runtime = ugly_runtime.split("_").pop()
        clean_date = "/".join(ugly_runtime.split("_")[:-1])
        return f"{clean_date}\n@\n{clean_runtime}\n{self.date_range}"

    def get_merchant(self):
        """
        Returns:
           string - Merchant listed for the comparison
        """
        return self.tables_list[0]["merchant"][0]
