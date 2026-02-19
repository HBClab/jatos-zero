import pandas as pd

from data_processing.utils import QC_UTILS


class MEM_QC:
    def __init__(
        self,
        RT_COLUMN_NAME,
        ACC_COLUMN_NAME,
        CORRECT_SYMBOL,
        INCORRECT_SYMBOL,
        COND_COLUMN_NAME,
        MAXRT,
    ):
        self.MAXRT = MAXRT
        self.RT_COLUMN_NAME = RT_COLUMN_NAME
        self.ACC_COLUMN_NAME = ACC_COLUMN_NAME
        self.CORRECT_SYMBOL = CORRECT_SYMBOL
        self.INCORRECT_SYMBOL = INCORRECT_SYMBOL
        self.COND_COLUMN_NAME = COND_COLUMN_NAME

    def fn_sm_qc(self, df, threshold):
        """
        Perform quality control (QC) checks on the submission data.
        """
        CATEGORY = 1
        raw = pd.DataFrame(df)

        QC_UTILS.get_max_rt_info(raw, self.MAXRT, self.RT_COLUMN_NAME)

        accuracy = QC_UTILS.get_acc_by_block_cond(
            raw,
            self.COND_COLUMN_NAME,
            self.ACC_COLUMN_NAME,
            self.CORRECT_SYMBOL,
            self.INCORRECT_SYMBOL,
        )
        avg_acc = 0.0
        for _, acc in accuracy.items():
            avg_acc += acc
            if acc <= threshold:
                CATEGORY = 2
            elif acc == 0:
                CATEGORY = 3
        avg_acc /= len(accuracy)

        problematic_conditions = QC_UTILS.cond_block_not_reported(
            raw,
            self.ACC_COLUMN_NAME,
            self.COND_COLUMN_NAME,
            self.INCORRECT_SYMBOL,
        )

        if len(problematic_conditions) != 0:
            CATEGORY = 3

        return CATEGORY, accuracy
