import os
#from dotenv import load_dotenv

if os.getenv("DATA_DIR_PATH") is None or os.getenv("PACKAGE_DIR_PATH") is None:
    load_dotenv(override=True)
    # print(f"INFO: PACKAGE_DIR_PATH = {os.environ['PACKAGE_DIR_PATH']}")
    # print(f"INFO: DATA_DIR_PATH = {os.environ['DATA_DIR_PATH']}")
    print('INFO: Environemental variables were not set: PACKAGE_DIR_PATH, DATA_DIR_PATH')


print(f"INFO: PACKAGE_DIR_PATH = {os.environ['PACKAGE_DIR_PATH']}")
print(f"INFO: DATA_DIR_PATH = {os.environ['DATA_DIR_PATH']}")
