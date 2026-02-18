import pandas as pd
from data_processing.utils import WL_UTILS, DWL_UTILS

class WL_QC:

    def __init__(self, WL=True):

        self.WL = WL
        self.CATEGORY = 1

    def wl_qc(self, submission, version):
        """

        calls WL_UTILS to get df_all

        parses df_all to categorize

        """
        df = submission

        wl_instance = WL_UTILS()
        df_all, self.CATEGORY = wl_instance.main(df, version)

        if self.CATEGORY == 3:
            return df_all, self.CATEGORY
        # Assuming df_all is the DataFrame and self.CATEGORY exists in the class context

        if (df_all['block'] == 'immediate').any():
            if df_all.loc[df_all['block'] == 'immediate', 'ratio'].iloc[0] < 0.3:
                self.CATEGORY = 2


        return df_all, self.CATEGORY

    def dwl_qc(self, submission, version):
        """

        Calls DWL_UTILS to return master df

        parses df to categorize

        """
        df = submission

        dwl_instance = DWL_UTILS()
        df_all, self.CATEGORY = dwl_instance.main(df, version)

        if self.CATEGORY == 3:
            return df_all, self.CATEGORY
        # Assuming df_all is the DataFrame and self.CATEGORY exists in the class context

        if (df_all['block'] == 'delay').any():
            if df_all.loc[df_all['block'] == 'delay', 'ratio'].iloc[0] < 0.3:
                self.CATEGORY = 2

        return df_all, self.CATEGORY

    @staticmethod
    def wl_count_correct(df_all):
        tmp = df_all.copy()

        # 1) coerce 'correct' to 0/1 ints
        tmp['correct'] = pd.to_numeric(tmp['correct'], errors='coerce').fillna(0).astype(int)

        # 2) normalize block labels: learn blocks => learn_1..learn_5; pass-through for strings
        def _lbl(b):
            s = str(b)
            return f"learn_{int(b)}" if s.isdigit() else s  # 'distraction', 'immediate' stay as-is
        tmp['block_label'] = tmp['block'].map(_lbl)

        # 3) sum and reshape to one row with a fixed column order
        wanted = ['learn_1','learn_2','learn_3','learn_4','learn_5','distraction','immediate']
        wide = (tmp.groupby('block_label')['correct'].sum()
                  .reindex(wanted, fill_value=0)
                  .to_frame().T)  # one row

        return wide  # columns are the block names above, single row of counts


    @staticmethod
    def dwl_count_correct(df_all):
        tmp = df_all.copy()
        tmp['correct'] = pd.to_numeric(tmp['correct'], errors='coerce').fillna(0).astype(int)

        # For delay QC, ensure block == 'delay'
        out = (tmp[tmp['block'] == 'delay']
               .groupby('block')['correct'].sum()
               .reindex(['delay'], fill_value=0)
               .to_frame().T)  # one row: column 'delay'
        return out
