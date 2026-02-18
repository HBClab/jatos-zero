from logging import raiseExceptions
import os
import sys
import json
import requests
import pandas as pd
from termcolor import colored, cprint
import zipfile
import io
from io import BytesIO


class Pull:
    def __init__(self, taskIds, tease, token, taskName, proxy=True):
        if not isinstance(taskIds, list):
            raise ValueError("task IDs is not a valid list, must be of type list (e.g. [123, 123, 123, ..., 123])")
            sys.exit()
        elif len(taskIds) != 6:
            raise ValueError(f"Not all IDs are in the list. Missing {6 - len(taskIds)} tasks")
        else:
            self.IDs = taskIds
        self.tease = tease
        self.token = token
        self.taskName = taskName
        self.proxy = proxy

    def load(self, days_ago=1):

        from datetime import datetime, timedelta

        proxies = {
        'http': f'http:zjgilliam:{self.tease}@proxy.divms.uiowa.edu:8888',
        'https': f'http://zjgilliam:{self.tease}@proxy.divms.uiowa.edu:8888',
        }

        url = 'https://jatos.psychology.uiowa.edu/jatos/api/v1/results/metadata'
        headers = {
            'accept': 'application/json',
            'Authorization': f"Bearer {self.token}" ,
            'Content-Type': 'application/json',
        }
        data = {
            'studyIds': self.IDs
        }

        # Calculate the timestamp for filtering
        cutoff_time = (datetime.now() - timedelta(days=days_ago)).timestamp() * 1000  # milliseconds

        # API request payload
        data = {"studyIds": self.IDs}
        if self.proxy:
            try:
                # Make the API request
                cprint("requesting data from Jatos...", 'green')
                response = requests.post(url, headers=headers, json=data, proxies=proxies)
                response.raise_for_status()  # Raise HTTP errors if any
                response_json = response.json()

                # Extract and filter study results
                study_result_ids = [
                    study_result["id"]
                    for study in response_json.get("data", [])
                    for study_result in study.get("studyResults", [])
                    if study_result["studyState"] == "FINISHED" and study_result["endDate"] >= cutoff_time
                ]

                return self.return_data(study_result_ids)

            except requests.RequestException as e:
                cprint(f"Error during API request: {e}", 'red')
                return []

            except KeyError as e:
                cprint(f"Unexpected response format: Missing key {e}", 'red')
                return []
        else:
            try:
                # Make the API request
                cprint("requesting data from Jatos...", 'green')
                response = requests.post(url, headers=headers, json=data) #proxies=proxies) DONT USE THAT THANG
                response.raise_for_status()  # Raise HTTP errors if any
                response_json = response.json()

                # Extract and filter study results
                study_result_ids = [
                    study_result["id"]
                    for study in response_json.get("data", [])
                    for study_result in study.get("studyResults", [])
                    if study_result["studyState"] == "FINISHED" and study_result["endDate"] >= cutoff_time
                ]

                return self.return_data(study_result_ids)

            except requests.RequestException as e:
                cprint(f"Error during API request: {e}", 'red')
                return []

            except KeyError as e:
                cprint(f"Unexpected response format: Missing key {e}", 'red')
                return []



    def return_data(self, study_result_ids):
        proxies = {
            'http': f'http://zjgilliam:{self.tease}@proxy.divms.uiowa.edu:8888',
            'https': f'http://zjgilliam:{self.tease}@proxy.divms.uiowa.edu:8888',
        }
        headers = {
            'accept': 'application/octet-stream',
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
        }
        data = {
            'studyIds': self.IDs,
            'studyResultIds': study_result_ids
        }
        url = 'https://jatos.psychology.uiowa.edu/jatos/api/v1/results/data'

        if self.proxy:

            try:
                response = requests.post(url, headers=headers, json=data, proxies=proxies)
                response.raise_for_status()
            except requests.RequestException:
                return []

            if not zipfile.is_zipfile(BytesIO(response.content)):
                return []
        else:
            try:
                response = requests.post(url, headers=headers, json=data) #proxies=proxies)
                response.raise_for_status()
            except requests.RequestException:
                return []

            if not zipfile.is_zipfile(BytesIO(response.content)):
                return []


        # Process the zip file
        return self._extract_txt_files(response.content, study_result_ids)


    def _extract_txt_files(self, zip_content, study_result_ids):
        data_frames = []

        # Open the zip content from memory
        with zipfile.ZipFile(io.BytesIO(zip_content), 'r') as zip_ref:
            for zip_info in zip_ref.infolist():
                # Check if the filename matches any of the study_result_ids
                if any(str(study_id) in zip_info.filename for study_id in study_result_ids):
                    # Read the file content directly into memory if it is a .txt file
                    if zip_info.filename.endswith(".txt"):
                        with zip_ref.open(zip_info) as file:
                            file_data = file.read().decode('utf-8')  # Decode byte content
                            df = pd.DataFrame({"file_content": [file_data]})  # Create a DataFrame for this file
                            data_frames.append(df)

        return data_frames  # List of DataFrames


