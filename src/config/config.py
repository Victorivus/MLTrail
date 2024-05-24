import os
os.environ["PACKAGE_DIR_PATH"] = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
os.environ["DATA_DIR_PATH"] = os.path.join(os.environ["PACKAGE_DIR_PATH"], 'data')
print(f"INFO: PACKAGE_DIR_PATH = {os.environ['PACKAGE_DIR_PATH']}")
print(f"INFO: DATA_DIR_PATH = {os.environ['DATA_DIR_PATH']}")
