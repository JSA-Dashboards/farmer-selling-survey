"""Rebuild data/*.csv from the survey workbook:  py build_data.py "<path to xlsx>" """
import sys, shutil, tempfile, os
from loader import load_workbook_tables

src = sys.argv[1]
tmp = os.path.join(tempfile.mkdtemp(), "fss.xlsx")
shutil.copy(src, tmp)  # the synced file is often locked by Excel/OneDrive
surveys, monthly = load_workbook_tables(tmp)
surveys.to_csv("data/surveys.csv", index=False)
monthly.to_csv("data/monthly.csv", index=False)
print(len(surveys), "survey points;", len(monthly), "monthly points; latest", surveys.date.max().date())
