import os

import pandas as pd


class PrettyTableMaker:
    tables_list = []
    summary_tables = []
    dir_path = None

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

