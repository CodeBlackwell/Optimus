import os
import json

import pandas as pd


class PrettyTableMaker:
    tables_list = []
    summary_tables = []
    test_results = {
        "each_test": {
            "sql_source": None,
            "date_range": None,
            "merchant_name": None,
            "widget_name": None,
            "category": None,
            "report_name": None
        }
    }
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

    def run(self):
        self.retrieve_tables()
        self.generate_test_account_overview_update_literal()

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
                        self.tables_list.append(pd.read_excel(filepath))
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

        result = {
            "pass": {},
            "fail": {}
        }
        if len(self.summary_tables) > 1:
            for summary in self.summary_tables:
                for index, row in summary.iterrows():
                    widget_name = row["widget"]
                    category_name = row["Dashboard Category"]
                    for boolean in result:
                        # Check if the widget is in the result already, if not - create entry
                        if widget_name not in result[boolean]:
                            result[boolean][widget_name] = {}
                        # Check if the category is in the widget result already, if not - create entry
                        if category_name not in result[boolean][widget_name]:
                            result[boolean][widget_name][category_name] = []
            for boolean_val in result:
                for summary in self.summary_tables:
                    for index, row in summary.iterrows():
                        widget_name = row["widget"]
                        category_name = row["Dashboard Category"]
                        if row["pass/fail"] == boolean_val:
                            if row["Dashboard Report Name"] not in result[boolean_val][widget_name][category_name]:
                                result[boolean_val][widget_name][category_name].append(row["Dashboard Report Name"])

        result["Last Test"] = self.dir_path.split("/").pop()
        result["Merchant"] = self.get_merchant()

        result["Currency"] = self.get_currency()
        print(result)
        # return result
        # # @TODO: figure out how to know which network the test was run for - consult Zach.
        # result["Network"] = None
        # self.merchant_result_overview = None

    def generate(self):
        pass

    def get_currency(self):
        """
        Returns:
            string - Currency listed in the request Object for the comparison
        """
        report = None
        for report in self.tables_list[0]["edw3_request_object"]:
            ro = json.loads(report)
            for ro_key in ro:
                for key in ro[ro_key]:
                    if key == "currency":
                        return ro[ro_key][key]

    def get_merchant(self):
        """
        Returns:
           string - Merchant listed for the comparison
        """
        return self.tables_list[0]["merchant"][0]
