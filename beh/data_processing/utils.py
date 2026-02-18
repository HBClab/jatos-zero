import os
import json
import pandas as pd
import numpy as np

from termcolor import cprint

class CONVERT_TO_CSV:
    def __init__(self, task, init_path='./data/raw'):
        self.init_path = init_path
        self.task = task

    def convert_to_csv(self, txt_dfs):
        new_dfs = []

        for txt_df in txt_dfs:
            file_content = txt_df["file_content"].values[0]
            records = self._extract_records(file_content)

            if not records:
                # If file is empty or has no valid records, skip
                continue

            normalized_records = [
                self._flatten_record(record) for record in records if isinstance(record, dict)
            ]
            if not normalized_records:
                continue

            flattened_df = pd.json_normalize(normalized_records, sep="_")
            flattened_df = self._harmonize_columns(flattened_df)
            flattened_df = self._normalize_semantics(flattened_df)
            new_dfs.append(flattened_df)

        return new_dfs

    def _extract_records(self, file_content):
        """
        Normalize different JSON payload shapes (newline-delimited objects vs array dumps)
        into a consistent list of trial dictionaries.
        """
        try:
            parsed_payload = json.loads(file_content)
        except json.JSONDecodeError:
            return self._extract_from_lines(file_content)

        return self._collect_records(parsed_payload)

    def _extract_from_lines(self, file_content):
        records = []
        for raw_line in file_content.splitlines():
            line = raw_line.strip()
            if not line or line in ("[", "]"):
                continue

            if line.startswith('['):
                line = line[1:]
            if line.endswith(']'):
                line = line[:-1]

            trimmed_line = line.rstrip(',').strip()
            if not trimmed_line:
                continue

            try:
                parsed_line = json.loads(trimmed_line)
            except json.JSONDecodeError as e:
                cprint(f"JSONDecodeError: {e} on line: {raw_line}", 'red')
                continue

            records.extend(self._collect_records(parsed_line))

        return records

    def _collect_records(self, payload):
        if isinstance(payload, dict):
            data_block = payload.get("data")
            if isinstance(data_block, list):
                return data_block
            if isinstance(data_block, dict):
                return [data_block]
            return [payload]

        if isinstance(payload, list):
            records = []
            for item in payload:
                records.extend(self._collect_records(item))
            return records

        return []

    def _flatten_record(self, record):
        """
        Recursively merge wrapper keys (``data``, ``trialdata``) into a flat dict so
        downstream QC modules see consistent column names like ``block`` and ``correct``.
        """
        flattened = {}
        for key, value in record.items():
            if isinstance(value, dict) and key.lower() in {"data", "trialdata"}:
                flattened.update(self._flatten_record(value))
            elif isinstance(value, dict):
                nested = self._flatten_record(value)
                for nested_key, nested_value in nested.items():
                    combined_key = f"{key}_{nested_key}"
                    flattened[combined_key] = nested_value
            else:
                flattened[key] = value
        return flattened

    def _harmonize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Strip known wrapper prefixes to restore historical column names and drop duplicates.
        """
        rename_map = {}
        for col in df.columns:
            new_col = col
            for prefix in ("trialdata_", "data_", "payload_", "TrialData_", "trialData_"):
                if new_col.startswith(prefix):
                    new_col = new_col[len(prefix):]
            rename_map[col] = new_col

        harmonized = df.rename(columns=rename_map)

        canonical_map = {
            "Block": "block",
            "BlockName": "block",
            "blockName": "block",
            "Block_Type": "block",
            "block_type": "block",
            "Condition": "condition",
            "Cond": "condition",
            "stim_condition": "condition",
            "Correct": "correct",
            "isCorrect": "correct",
            "Session": "session_number",
            "session": "session_number",
            "SessionID": "session_number",
            "Subject": "subject_id",
            "subject": "subject_id",
        }

        harmonized = harmonized.rename(columns=lambda col: canonical_map.get(col, col))

        # If both original and harmonized columns exist, keep the first non-null values.
        if harmonized.columns.duplicated().any():
            deduped = {}
            for col in harmonized.columns.unique():
                dupes = [c for c in harmonized.columns if c == col]
                if len(dupes) == 1:
                    deduped[col] = harmonized[dupes[0]]
                else:
                    stacked = harmonized[dupes].bfill(axis=1)
                    deduped[col] = stacked.iloc[:, 0]
            harmonized = pd.DataFrame(deduped)

        return harmonized

    def _normalize_semantics(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Coerce critical columns (block/condition/correct/session/subject_id) into their
        historical dtypes and label space so downstream QC and persistence stay stable.
        """
        normalized = df.copy()

        if "block" in normalized.columns:
            normalized["block"] = normalized["block"].map(self._standardize_block)

        if "condition" in normalized.columns:
            normalized["condition"] = normalized["condition"].apply(
                lambda val: val.strip() if isinstance(val, str) else val
            )

        if "correct" in normalized.columns:
            normalized["correct"] = pd.to_numeric(normalized["correct"], errors="coerce")

        if "session_number" in normalized.columns:
            normalized["session_number"] = pd.to_numeric(
                normalized["session_number"], errors="coerce"
            )

        if "subject_id" in normalized.columns:
            normalized["subject_id"] = normalized["subject_id"].apply(
                lambda val: str(val).strip() if pd.notna(val) else val
            )

        return normalized

    @staticmethod
    def _standardize_block(value):
        if isinstance(value, str):
            cleaned = value.strip().lower()
            if cleaned.startswith("test"):
                return "test"
            if cleaned.startswith(("prac", "practice")):
                return "prac"
            if cleaned in {"training", "train"}:
                return "prac"
            if cleaned == "":
                return np.nan
            return cleaned
        return value

    def save_csv(self):
        return None


class QC_UTILS:

    @staticmethod
    def get_avg_rt(df, rt_column_name, conditon_column_name):
        """
        Helper function to calculate the average response time (RT) from for each condition for a dataframe.
        Args:
            df (pd.DataFrame): The DataFrame containing the trial data.
            rt_column_name (str): The column name for response times.
            conditon_column_name (str): The column name for conditions.
        Returns:
            dict: A dictionary where keys are unique conditions and values are average RTs for those conditions.
        """

        if rt_column_name not in df.columns:
            raise ValueError(f"Column '{rt_column_name}' does not exist in the DataFrame.")
        if conditon_column_name not in df.columns:
            raise ValueError(f"Column '{conditon_column_name}' does not exist in the DataFrame.")
        avg_rt_by_condition = {}
        for condition in df[conditon_column_name].unique():
            condition_data = df[df[conditon_column_name] == condition]
            avg_rt = condition_data[rt_column_name].mean()
            avg_rt_by_condition[condition] = avg_rt
        return avg_rt_by_condition

    @staticmethod
    def get_max_rt_info(df, max_rt, rt_column_name):
        """
        Helper function to calculate metrics related to trials reaching MAXRT.
        Args:
            df (pd.DataFrame): The DataFrame containing the trial data.
            max_rt (int): The maximum response time threshold (MAXRT).
            rt_column_name (str): The column name for response times.
        Returns:
            tuple:
                - Total number of trials reaching MAXRT.
                - Maximum count of consecutive trials reaching MAXRT.
                - List of tuples indicating the column ranges of consecutive trials.
        """


        if rt_column_name not in df.columns:
                raise ValueError(f"Column '{rt_column_name}' does not exist in the DataFrame.")
        # Filter trials that reach MAXRT
        max_rt_trials = df[df[rt_column_name] >= max_rt]
        # Number of trials reaching MAXRT
        num_trials_reaching_max_rt = len(max_rt_trials)
        # Find consecutive trials reaching MAXRT
        consecutive_ranges = []
        consecutive_count = 0
        max_consecutive = 0
        current_start = None
        for i, trial in enumerate(df[rt_column_name] >= max_rt):
            if trial:  # If current trial meets MAXRT
                if consecutive_count == 0:
                    current_start = i
                consecutive_count += 1
            else:  # If current trial doesn't meet MAXRT
                if consecutive_count > 0 and current_start is not None:
                    consecutive_ranges.append((current_start, current_start + consecutive_count - 1))
                    max_consecutive = max(max_consecutive, consecutive_count)
                    consecutive_count = 0

        # Add the last range if we end with a sequence of MAXRT trials
        if consecutive_count > 0 and current_start is not None:
            consecutive_ranges.append((current_start, current_start + consecutive_count - 1))
            max_consecutive = max(max_consecutive, consecutive_count)

        return num_trials_reaching_max_rt, max_consecutive, consecutive_ranges

    @staticmethod
    def get_count_correct(df, block_cond_column_name, acc_column_name, correct_symbol): 
        """
        Calculate the count of correct responses by block or condition based on a given column.
        Args:
            df (pd.DataFrame): The DataFrame containing the data.
            block_cond_column_name (str): The name of the column to group data by (e.g., blocks or conditions).
            acc_column_name (str): The name of the column containing the accuracy symbols.
            correct_symbol (str): The symbol representing correct responses.
        """
        if acc_column_name not in df.columns:
            raise ValueError(f"column '{acc_column_name}' does not exist in the dataframe.")
        if block_cond_column_name not in df.columns:
            raise ValueError(f"column '{block_cond_column_name}' does not exist in the dataframe.")
        correct_count_by_block_cond = {}
        for block_cond in df[block_cond_column_name].unique():
            block_data = df[df[block_cond_column_name] == block_cond]
            # count correct responses
            correct_count = (block_data[acc_column_name] == correct_symbol).sum()
            correct_count_by_block_cond[block_cond] = correct_count
        return correct_count_by_block_cond


    @staticmethod
    def get_acc_by_block_cond(df, block_cond_column_name, acc_column_name, correct_symbol, incorrect_symbol, domain=None):
        """
        Calculate the accuracy by block or condition based on a given column.

        Args:
            df (pd.DataFrame): The DataFrame containing the data.
            block_cond_column_name (str): The name of the column to group data by (e.g., blocks or conditions).
            acc_column_name (str): The name of the column containing the accuracy symbols.
            correct_symbol (str): The symbol representing correct responses.
            incorrect_symbol (str): The symbol representing incorrect responses.

        Returns:
            dict: A dictionary where keys are unique values of block_cond_column_name and values are accuracies as percentages (0-100).
        """
        if acc_column_name not in df.columns:
            raise ValueError(f"Column '{acc_column_name}' does not exist in the DataFrame.")
        if block_cond_column_name not in df.columns:
            raise ValueError(f"Column '{block_cond_column_name}' does not exist in the DataFrame.")

        accuracy_by_block_cond = {}

        for block_cond in df[block_cond_column_name].unique():
            block_data = df[df[block_cond_column_name] == block_cond]
            # Count correct and incorrect responses
            correct_count = (block_data[acc_column_name] == correct_symbol).sum()
            incorrect_count = (block_data[acc_column_name] == incorrect_symbol).sum()

            # Total responses
            total_responses = correct_count + incorrect_count

            if total_responses == 0:
                accuracy_by_block_cond[block_cond] = 0.0  # Avoid division by zero; return 0% accuracy if no responses
            else:
                # Calculate accuracy as a percentage
                accuracy_by_block_cond[block_cond] = (correct_count / total_responses) * 100


        return accuracy_by_block_cond

    @staticmethod
    def cond_block_not_reported(df, column_name, acc_name, incorrect_symbol):
        """
        Loops through unique values in column_name and checks if for any block,
        the values in acc_name are either incorrect or not reported.

        Args:
            df (pd.DataFrame): The DataFrame containing the data.
            column_name (str): The column to group data by (e.g., blocks).
            acc_name (str): The column containing accuracy symbols.
            incorrect_symbol (str): The symbol representing incorrect responses.

        Returns:
            list: A list of blocks where acc_name contains incorrect or no responses.
        """
        problematic_blocks = []

        for block in df[column_name].unique():
            block_data = df[df[column_name] == block]
            # Check if all responses are incorrect or missing
            if all((block_data[acc_name] == incorrect_symbol) | block_data[acc_name].isna()):
                problematic_blocks.append(block)

        return problematic_blocks


import pandas as pd
from fuzzywuzzy import fuzz
from fuzzywuzzy import process

class WL_UTILS:
    """
    WL_UTILS: A utility class for data preprocessing, analysis, and fuzzy matching in response datasets.

    Inputs:
    - df: A Pandas DataFrame containing the dataset to process. The DataFrame is expected to have specific columns like 'block_c', 'response', 'multichar_response', 'block_dur', and 'condition'.

    Outputs:
    - A processed Pandas DataFrame containing fuzzy matching results, metadata, and trial indices.

    Methods:
    1. __init__(df):
    - Initializes the WL_UTILS object with the input DataFrame.
    - Stores the DataFrame as an instance variable.

    2. select_key(version):
    - Selects a predefined list of keys (A, B, or C) based on the version provided.
    - Input: A string ('A', 'B', or 'C').
    - Output: A list of word sets corresponding to the version.

    3. filter_data():
    - Filters the DataFrame to exclude practice blocks and removes the first row.
    - Output: A filtered DataFrame.

    4. find_word_ranges(data):
    - Identifies ranges of rows in the dataset where 'response' is delimited by 'enter'.
    - Input: A DataFrame subset.
    - Output: A list of ranges (start and end indices) for processing.

    5. add_metadata(data, ranges):
    - Adds metadata to the identified ranges, including:
        - The multi-character response (up to the last 5 characters).
        - A flag indicating the use of 'backspace'.
        - The time difference between the start and end of the range.
    - Inputs: DataFrame subset and list of ranges.
    - Output: A list of updated ranges with metadata.

    6. fuzzy_match(sub_list, word_list):
    - Performs fuzzy matching to compare words in a list to a predefined key list.
    - Classifies matches based on similarity ratio (>80) and flags for repeats and correctness.
    - Inputs: A list of words and a reference list.
    - Output: A list of matching results with metadata.

    7. create_dataframe(data, key, condition):
    - Creates a new DataFrame for the results of fuzzy matching.
    - Inputs: Data subset, a selected key, and a condition ('distraction' or 'immediate').
    - Output: A DataFrame with matching results and metadata.

    8. main(version):
    - Executes the complete workflow:
        - Selects the key based on the version.
        - Filters the data.
        - Processes conditions ('distraction' and 'immediate').
        - Combines results into a single DataFrame with trial indices.
    - Input: Version string ('A', 'B', or 'C').
    - Output: A consolidated DataFrame with all processed results.



    The `df_all` DataFrame is the final output of the `main()` method. It consolidates and organizes the results of fuzzy matching and metadata processing for all participants and conditions.

    Columns:
    1. word:
    - The original word provided by the participant during the task.

    2. best_match:
    - The closest match for the participant's word from the predefined key list based on fuzzy matching.

    3. ratio:
    - The similarity score (0-100) between the participant's word and the best match, calculated using fuzzy string matching.

    4. backspace:
    - A flag (1 or 0) indicating whether the participant used backspace during the task in the corresponding range.
    - 1: Backspace used.
    - 0: Backspace not used.

    5. repeat:
    - A flag (1 or 0) indicating whether the matched word was already used in the task.
    - 1: Word is a repeat.
    - 0: Word is not a repeat.

    6. correct:
    - A flag (1 or 0) indicating whether the fuzzy matching similarity score exceeded the threshold (e.g., >80).
    - 1: Word is considered correct.
    - 0: Word is considered incorrect.

    7. block:
    - Specifies the experimental condition of the task.
    - Possible values:
        - 'distraction': Indicates the distraction condition.
        - 'immediate': Indicates the immediate recall condition.
        - 'learn': Indicates the learning blocks.

    8. trial_index:
    - A unique identifier for each row in the DataFrame, representing the trial order.
    - Indexed sequentially across all conditions.

    Organization:
    - Rows:
    - Each row represents a single word or response from the participant, along with its corresponding metadata and fuzzy matching results.
    - Blocks:
    - The DataFrame contains three blocks of data:
        - 'distraction': Results from the distraction condition.
        - 'immediate': Results from the immediate recall condition.
        - 'learn': Results from the learning trials
    - These blocks are concatenated into a single DataFrame for unified analysis.
    - Sorting:
    - Rows are sorted by the trial order (trial_index), ensuring the data is organized sequentially for analysis.
    """
    def __init__(self):
        """
        Initialize the WL_UTILS class with a DataFrame.
        """
        self.CATEGORY = 1
        self.listA = [['book', 'flower', 'train', 'rug', 'meadow', 'harp', 'salt', 'finger', 'apple', 'log', 'button', 'key', 'gold', 'rattle'],['bowl', 'dawn', 'judge', 'grant', 'insect', 'plane', 'county', 'pool', 'seed', 'sheep', 'meal', 'coat', 'bottle', 'peach', 'chair']]
        self.listB = [['street', 'grass', 'door', 'arm', 'star', 'wife', 'window', 'city', 'pupil', 'cabin', 'lake', 'pipe', 'skin', 'fire', 'clock'],['baby', 'ocean', 'palace', 'lip', 'bar', 'dress', 'steam', 'coin', 'rock', 'army', 'building', 'friend', 'storm', 'village', 'cell']]
        self.listC = [['tower', 'wheat', 'queen', 'sugar', 'home', 'boy', 'doctor', 'camp', 'flag', 'letter', 'corn', 'nail', 'cattle', 'shore', 'body'],['sky', 'dollar', 'valley', 'butter', 'hall', 'diamond', 'winter', 'mother', 'christmas', 'meat', 'forest', 'tool', 'plant', 'money', 'hotel']]

    def select_key(self, version):
        keys = {'A': self.listA, 'B': self.listB, 'C': self.listC}
        if version not in keys:
            raise ValueError("Invalid version. Please choose 'A', 'B', or 'C'.")
        return keys[version]

    def filter_data(self, df):
        "Remove the first row"
        filtered = df.iloc[1:]
        return filtered.reset_index(drop=True) #reset index to 0

    @staticmethod
    def find_word_ranges(data):
        indices = data[data['response'] == 'enter'].index
        ranges = [[start, end] for start, end in zip(indices[:-1], indices[1:])]
        return ranges

    # 1) add block extraction to add_metadata
    @staticmethod
    def add_metadata(data, ranges):
        """
        Add metadata (multichar_response, backspace flag, time difference, block_c) to ranges.
        """
        updated_ranges = []
        for r in ranges:
            start, end = r[0], r[1]
            response_text = data.iloc[end]['multichar_response'][:-5]
            backspace_flag = 1 if any('backspace' in data.iloc[j]['response'] for j in range(start, end)) else 0
            time_diff = data.iloc[end]['block_dur'] - data.iloc[start]['block_dur']
            # derive the learn block from block_c within the range (mode is robust)
            blk_series = data.loc[start:end, 'block_c'].dropna()
            block_num = int(blk_series.mode().iat[0]) if not blk_series.empty else int(data.iloc[end]['block_c'])
            updated_ranges.append([response_text, start, end, backspace_flag, time_diff, block_num])
        return updated_ranges

    # 2) pass block through fuzzy_match
    @staticmethod
    def fuzzy_match(sub_list, word_list):
        """
        Perform fuzzy matching and classify words based on similarity ratios.
        """
        results = []
        used = []
        for sub in sub_list:
            first_item = str(sub[0]) if isinstance(sub, list) and len(sub) > 0 else None
            if first_item:
                best_match = process.extractOne(first_item, word_list, scorer=fuzz.ratio)
                if best_match:
                    matched_word, ratio = best_match
                    repeat_flag = '1' if matched_word in used else '0'
                    correct_flag = '1' if ratio > 80 else '0'
                    if ratio > 80:
                        used.append(matched_word)
                    # sub[5] is block_num from add_metadata
                    results.append([first_item, matched_word, ratio, sub[3], repeat_flag, correct_flag, sub[5]])
        return results

    # 3) expose 'block' from create_dataframe
    def create_dataframe(self, data, key, condition):
        """
        Create a DataFrame for the fuzzy matching results.
        """
        word_ranges = self.find_word_ranges(data)
        word_ranges = self.add_metadata(data, word_ranges)
        word_list = key[0] if condition in ['immediate', 'learn'] else key[1]
        fuzzy_results = self.fuzzy_match(word_ranges, word_list)
        # include 'block' as last column (learn block number)
        df = pd.DataFrame(
            fuzzy_results,
            columns=['word', 'best_match', 'ratio', 'backspace', 'repeat', 'correct', 'block']
        )
        return df

    # 4) in main(): preserve learn block number, and add a separate 'condition' column
    def main(self, df, version):
        key = self.select_key(version)
        filtered_data = self.filter_data(df).reset_index(drop=True)

        dist = filtered_data[filtered_data['condition'] == 'distr'].reset_index(drop=True)
        immed = filtered_data[filtered_data['condition'] == 'immed'].reset_index(drop=True)
        learn = filtered_data[filtered_data['condition'] == 'learn'].reset_index(drop=True)

        if dist.empty or immed.empty or learn.empty:
            self.CATEGORY = 3

        df_dist = self.create_dataframe(dist, key, 'distraction')
        df_immed = self.create_dataframe(immed, key, 'immediate')
        df_learn = self.create_dataframe(learn, key, 'learn')  # 'block' here is the learn block number 1..5

        # For non-learn, override 'block' to the label; keep numeric blocks for learn
        df_dist['block'] = 'distraction'
        df_immed['block'] = 'immediate'

        # Add explicit condition column so both things are available downstream
        df_dist['condition']  = 'distraction'
        df_immed['condition'] = 'immediate'
        df_learn['condition'] = 'learn'

        df_all = pd.concat([df_dist, df_immed, df_learn], ignore_index=True)
        df_all['trial_index'] = df_all.index
        return df_all, self.CATEGORY



class DWL_UTILS:
    """
    A class that processes a DataFrame that only has a 'delay' condition,
    applies fuzzy matching logic, and returns (df_all, CATEGORY).

    1) Takes in a DataFrame and a 'version' (A, B, or C).
    2) Filters data (removing first row, resetting index).
    3) Subsets the data where condition == 'delay'.
    4) If that subset is empty, sets self.CATEGORY=3.
    5) Else, performs fuzzy matching on that subset.
    6) Returns the final DataFrame (df_all) and self.CATEGORY.
    """

    def __init__(self):
        self.CATEGORY = 1  # Default category
        # Predefined keys (lists for versions 'A','B','C')
        self.listA = [
            ['book', 'flower', 'train', 'rug', 'meadow', 'harp', 'salt', 'finger', 'apple', 'log', 'button', 'key', 'gold', 'rattle'],
            ['bowl', 'dawn', 'judge', 'grant', 'insect', 'plane', 'county', 'pool', 'seed', 'sheep', 'meal', 'coat', 'bottle', 'peach', 'chair']
        ]
        self.listB = [
            ['street', 'grass', 'door', 'arm', 'star', 'wife', 'window', 'city', 'pupil', 'cabin', 'lake', 'pipe', 'skin', 'fire', 'clock'],
            ['baby', 'ocean', 'palace', 'lip', 'bar', 'dress', 'steam', 'coin', 'rock', 'army', 'building', 'friend', 'storm', 'village', 'cell']
        ]
        self.listC = [
            ['tower', 'wheat', 'queen', 'sugar', 'home', 'boy', 'doctor', 'camp', 'flag', 'letter', 'corn', 'nail', 'cattle', 'shore', 'body'],
            ['sky', 'dollar', 'valley', 'butter', 'hall', 'diamond', 'winter', 'mother', 'christmas', 'meat', 'forest', 'tool', 'plant', 'money', 'hotel']
        ]

    def select_key(self, version):
        """Select a predefined list of keys (A, B, or C) based on the version."""
        mapping = {'A': self.listA, 'B': self.listB, 'C': self.listC}
        if version not in mapping:
            raise ValueError("Invalid version. Please choose 'A', 'B', or 'C'.")
        return mapping[version]

    def filter_data(self, df):
        """
        Example filter step:
        - Removes the first row
        - Resets index
        """
        filtered = df.iloc[1:].reset_index(drop=True)
        return filtered

    def word_analysis_block(self, df_block, key_list):
        """
        1. Process each row's 'multichar_response' by trimming the last 5 characters.
        2. Check for 'backspace' usage.
        3. Fuzzy match each processed word against the relevant key list (key_list[0]).
           (We only have one condition, so no splitting between key_list[0] or key_list[1].)
        4. Return a DataFrame with columns:
           [word, best_match, ratio, backspace, repeat, correct, block, trial_index]
        """

        # ----------------
        # 1) Build word_list by trimming last 5 chars
        # ----------------
        word_list = df_block['multichar_response'].astype(str).apply(
            lambda x: x[:-5] if len(x) >= 5 else x
        ).tolist()

        # ----------------
        # 2) Detect 'backspace' usage
        # ----------------
        backspace_list = []
        for response in df_block['multichar_response']:
            backspace_list.append(1 if 'backspace' in response else 0)

        # ----------------
        # 3) Fuzzy match each word against key_list[0]
        #    (Only one sub-list is used since we have one condition)
        # ----------------
        match_list = key_list[0]
        used = []
        fuzzy_results = []

        for i, word in enumerate(word_list):
            if not word:
                # If empty or invalid
                fuzzy_results.append([word, '', 0, backspace_list[i], '0', '0'])
                continue

            best_match_data = process.extractOne(word, match_list, scorer=fuzz.ratio)
            if best_match_data:
                matched_word, ratio_score = best_match_data[0], best_match_data[1]
                repeat_flag = '1' if matched_word in used else '0'
                correct_flag = '1' if ratio_score > 80 else '0'
                if correct_flag == '1':
                    used.append(matched_word)
                fuzzy_results.append([word, matched_word, ratio_score, backspace_list[i], repeat_flag, correct_flag])
            else:
                fuzzy_results.append([word, '', 0, backspace_list[i], '0', '0'])

        # 4) Build a DataFrame with these columns
        df_out = pd.DataFrame(fuzzy_results, columns=['word', 'best_match', 'ratio', 'backspace', 'repeat', 'correct'])
        df_out['block'] = 'delay'               # Single condition
        df_out['trial_index'] = df_out.index
        return df_out

    def main(self, df, version):
        """
        1. Choose a key based on version.
        2. Filter data (remove first row, reset index).
        3. Subset data where condition == 'delay'.
        4. If empty, set self.CATEGORY=3.
        5. Else, process the 'delay' subset with word_analysis_block().
        6. Return df_all, self.CATEGORY.
        """

        # 1) Select key
        key_list = self.select_key(version)

        # 2) Filter data
        filtered_data = self.filter_data(df)

        # 3) Subset only rows where condition == 'delay'
        df_delay = filtered_data[filtered_data['condition'] == 'delay'].reset_index(drop=True)

        # 4) If empty => self.CATEGORY=3
        if df_delay.empty:
            self.CATEGORY = 3
            # You can return an empty DataFrame or handle differently
            df_all = pd.DataFrame(columns=[
                'word','best_match','ratio','backspace','repeat','correct','block','trial_index'
            ])
            return df_all, self.CATEGORY

        # 5) Otherwise, process this single block
        df_out_delay = self.word_analysis_block(df_delay, key_list)

        # 6) That's our final DataFrame
        df_all = df_out_delay.reset_index(drop=True)
        return df_all, self.CATEGORY
