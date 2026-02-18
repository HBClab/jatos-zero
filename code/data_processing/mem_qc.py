
import pandas as pd
from data_processing.utils import QC_UTILS

class MEM_QC:
    def __init__(self, RT_COLUMN_NAME, ACC_COLUMN_NAME, CORRECT_SYMBOL, INCORRECT_SYMBOL, COND_COLUMN_NAME, MAXRT):

        self.MAXRT = MAXRT
        self.RT_COLUMN_NAME = RT_COLUMN_NAME
        self.ACC_COLUMN_NAME = ACC_COLUMN_NAME
        self.CORRECT_SYMBOL = CORRECT_SYMBOL
        self.INCORRECT_SYMBOL = INCORRECT_SYMBOL
        self.COND_COLUMN_NAME = COND_COLUMN_NAME

    def fn_sm_qc(self, df, threshold):
        """
        Perform quality control (QC) checks on the submission data to validate its accuracy and completeness.

        Parameters:
            threshold (float): The minimum acceptable accuracy percentage for a condition.
                            Conditions with accuracy less than or equal to this value will trigger CATEGORY 2.
            TS (bool): Is this task switching?
        Returns:
            CATEGORY -> int: The category of data quality.
                - CATEGORY = 1: Data is within acceptable limits.
                - CATEGORY = 2: At least one condition has accuracy <= threshold.
                - CATEGORY = 3: At least one condition has accuracy == 0% or contains unreported data.
            accuracy -> dict: Accuracy by condition
                - Condition: The block or condition
                - Accuracy: float with accuracy for the block/condition
        Steps:
            1. Check if the number of rows in the submission is within 5% of the expected range (137-153 rows).
            - Raises ValueError if this condition is not met.
            2. Retrieve information on trials reaching the maximum response time (MAXRT), including:
            - The number of trials exceeding MAXRT.
            - The maximum number of consecutive trials exceeding MAXRT.
            - The ranges of consecutive trials exceeding MAXRT.
            3. Calculate accuracy for each condition in the data:
            - Set CATEGORY = 2 if any condition has accuracy <= threshold.
            - Set CATEGORY = 3 if any condition has accuracy == 0%.
            4. Identify problematic conditions where data is missing or incorrectly reported:
            - Set CATEGORY = 3 if any problematic conditions are found.
        """

        CATEGORY = 1

        raw = pd.DataFrame(df)

        # Call the get_max_rt_info method from QC_UTILS
        num_trials, max_consecutive, consecutive_ranges = QC_UTILS.get_max_rt_info(
            raw, self.MAXRT, self.RT_COLUMN_NAME
        )

        accuracy = QC_UTILS.get_acc_by_block_cond(raw, self.COND_COLUMN_NAME, self.ACC_COLUMN_NAME, self.CORRECT_SYMBOL, self.INCORRECT_SYMBOL)
        avg_acc = 0.0
        for condition, acc in accuracy.items():
            avg_acc += acc
            if acc <= threshold:
                CATEGORY = 2
            elif acc == 0:
                CATEGORY = 3
        avg_acc /= len(accuracy)

        problematic_conditions = QC_UTILS.cond_block_not_reported(raw, self.ACC_COLUMN_NAME, self.COND_COLUMN_NAME, self.INCORRECT_SYMBOL)

        if len(problematic_conditions) != 0:
            CATEGORY = 3

        return CATEGORY, accuracy











































