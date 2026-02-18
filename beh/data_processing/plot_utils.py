import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import matplotlib.patches as mpatches
from math import pi
import matplotlib

class CC_PLOTS:
    matplotlib.use('Agg')

    def __init__(self) -> None:
        pass


    def af_nf_plot(self, df):


        """
        Generates two plots: a count plot of correct responses by condition and a response time plot by condition.

        Parameters:
            df (pd.DataFrame): The input dataframe containing 'block', 'condition', 'correct', and 'response_time' columns.

        Returns:
            tuple: A tuple containing two Axes objects (count_plot, response_time_plot).
        """
        # Filter to drop practice data
        block_series = df['block'].astype(str).str.strip().str.lower()
        test_mask = block_series == 'test'
        test = df[test_mask].copy()

        if test.empty:
            subject_series = df.get('subject_id')
            if subject_series is not None:
                subjects = sorted(
                    {str(value).strip() for value in subject_series.dropna() if str(value).strip()}
                )
            else:
                subjects = []

            unique_blocks = sorted({value for value in block_series.unique() if value and value != 'nan'})
            raise ValueError(
                "No 'test' block rows available for plotting. "
                f"Observed block labels: {unique_blocks or '<none>'}. "
                f"Subjects in frame: {subjects or '<unknown>'}"
            )

        # Generate count plot
        plt.figure(figsize=(10, 6))
        count_ax = sns.countplot(x='condition', hue='correct', data=test)
        plt.title('Count Correct by Condition')

        # Add counts on top of each bar
        for p in count_ax.patches:
            height = p.get_height()
            if height > 0:
                count_ax.annotate(
                    f'{int(height)}',
                    (p.get_x() + p.get_width() / 2., height),
                    ha='center', va='bottom',
                    xytext=(0, 5), textcoords='offset points'
                )

        # Adjust y-axis limit
        max_height = max([p.get_height() for p in count_ax.patches if p.get_height() > 0])
        count_ax.set_ylim(0, max_height * 1.15)

        # Tighten layout
        plt.tight_layout()

        # Generate response time plot
        test['correct_label'] = test['correct'].map({0: 'Incorrect', 1: 'Correct'})

        plt.figure(figsize=(10, 6))
        rt_ax = sns.stripplot(
            x='condition',
            y='response_time',
            data=test,
            hue='correct_label',
            alpha=0.5,
            dodge=True,
            palette={'Correct': 'green', 'Incorrect': 'red'}
        )

        sns.boxplot(
            x='condition',
            y='response_time',
            data=test,
            whis=np.inf,
            linewidth=0.5,
            color='gray'
        )

        # Calculate means
        means = test.groupby('condition')['response_time'].mean()

        # Create legend labels and dummy handles
        labels = [f'Condition {cond}: Mean = {mean:.2f}' for cond, mean in means.items()]
        handles = [mpatches.Patch(color='white') for _ in labels]

        # Add legend
        plt.legend(
            handles=handles, labels=labels, title='Means by Condition',
            bbox_to_anchor=(1.05, 1), loc='upper left', borderaxespad=0., frameon=False
        )
        plt.title('Response Time by Condition')
        plt.tight_layout()

        # Return Axes objects
        return count_ax, rt_ax

    def ats_nts_plot(self, df):
        def filter(df):
            df = df[df['block']=='test'].reset_index(drop=True)
            return df

        def _percent_acc(df):
            # Calculate percent correct by block condition
            percent_corr = df['correct'].groupby(df['block_cond']).mean()

            # Create the bar plot
            plt.figure()
            ax1 = sns.barplot(x=percent_corr.index, y=percent_corr.values)
            plt.title('Percent Correct by Condition')
            plt.xlabel('Condition')
            plt.ylabel('Percent Correct')
            plt.tight_layout()


            return ax1
        def _rt(df):
            # Map the 'correct' column to more descriptive labels
            df['correct_label'] = df['correct'].map({0: 'Incorrect', 1: 'Correct'})

            # Create the scatter and box plot
            plt.figure(figsize=(10, 6))

            # Scatter plot
            ax2 = sns.stripplot(
                x='block_cond',
                y='response_time',
                data=df,
                hue='correct_label',
                alpha=0.5,
                dodge=True,
                palette={'Correct': 'green', 'Incorrect': 'red'}
            )

            # Overlay box plot
            sns.boxplot(
                x='block_cond',
                y='response_time',
                data=df,
                whis=np.inf,
                linewidth=0.5,
                color='gray'
            )

            # Calculate means
            means = df.groupby('block_cond')['response_time'].mean()
            mean_A_B = means[['A', 'B']].mean()
            mixing_cost = means['C'] - mean_A_B

            # Create labels for the legend
            labels = [f'block_cond {cond}: Mean = {mean:.2f}' for cond, mean in means.items()]
            labels.append(f'Mixing Cost = {mixing_cost:.2f}')

            # Create dummy handles for the legend entries
            handles = [mpatches.Patch(color='white') for _ in labels]

            # Add the legend
            plt.legend(
                handles=handles,
                labels=labels,
                title='Means and Mixing Cost by block_cond',
                bbox_to_anchor=(1.05, 1),
                loc='upper left',
                borderaxespad=0.,
                frameon=False
            )

            plt.title('Response Time by block_cond')
            plt.tight_layout()

            return ax2
        filtered = filter(df)
        acc = _percent_acc(filtered)
        rt = _rt(filtered)

        return acc, rt



    def nnb_vnb_plot(self,df):
        """
        Generates two plots from the given CSV file.

        Parameters:
        file_path (str): Path to the CSV file containing the data.

        Returns:
        tuple: A tuple of Axes objects (accuracy_plot, response_time_plot)
        """

        # Filter data for the 'test' block
        test = df[df['block'] == 'test']
        test['correct'] = pd.to_numeric(test['correct'], errors='coerce')
        test.dropna(subset=['correct'], inplace=True)
        # Group data by 'condition'
        grouped = test.groupby('condition')

        # Calculate accuracy for each condition
        acc_sum = grouped['correct'].sum()
        acc_len = grouped['correct'].count()
        acc = acc_sum / acc_len
        acc = acc.reset_index()
        acc.columns = ['condition', 'accuracy']

        # Plot accuracy by condition
        fig1, ax1 = plt.subplots()
        sns.barplot(x='condition', y='accuracy', data=acc, ax=ax1)
        ax1.set_title('Accuracy by Condition')
        ax1.text(0, 0.6, 'Chance', fontsize=12)
        ax1.axhline(0.5, color='black', linestyle='--')

        # Plot response time by condition with a boxplot and stripplot overlay
        fig2, ax2 = plt.subplots()
        sns.boxplot(
            x='condition', y='response_time', data=test,
            showfliers=False, palette='viridis', linewidth=1, ax=ax2
        )
        sns.stripplot(
            x='condition', y='response_time', data=test,
            jitter=True, color='black', alpha=0.5, ax=ax2
        )
        ax2.set_title('Response Time by Condition')

        acc = ax1
        rt = ax2
        # Return the Axes objects for both plots
        return acc, rt




class PS_PLOTS:
    def __init__(self):
        pass

    def lc_plot(self, df):
        """
        Generates plots for LC (Learning Condition) data.

        Parameters:
            df (pd.DataFrame): Input data containing 'condition', 'block_c', 'response', and 'correct'.

        Returns:
            dict: Contains two plot objects:
                  - 'bar_plot': Bar plot showing total and correct responses.
                  - 'response_time_plot': Scatter and box plot for response time.
        """
        test = df[df['condition'] == 'test']
        block1 = test[test['block_c'] == 1]
        block2 = test[test['block_c'] == 2]

        total_responses = [
            [block1['response'].apply(lambda x: x != 'None').sum(), len(block1)],
            [block2['response'].apply(lambda x: x != 'None').sum(), len(block2)],
        ]
        correct = [
            [block1['correct'].sum(), len(block1)],
            [block2['correct'].sum(), len(block2)],
        ]

        blocks = ['Block 1', 'Block 2']
        data = []
        for i in range(len(blocks)):
            total_resp = total_responses[i][0]
            total_trial = total_responses[i][1]
            correct_resp = correct[i][0]
            accuracy = correct_resp / total_trial * 100
            data.append({
                'Block': blocks[i],
                'Total Trials': total_trial,
                'Total Responses': total_resp,
                'Correct Responses': correct_resp,
                'Accuracy': accuracy
            })

        lc_df = pd.DataFrame(data)
        lc_melted = lc_df.melt(id_vars=['Block'], value_vars=['Total Responses', 'Correct Responses'],
                               var_name='Response Type', value_name='Count')

        # Create bar plot
        plt.figure(figsize=(8, 6))
        bar_ax = sns.barplot(x='Block', y='Count', hue='Response Type', data=lc_melted, palette='muted')
        for p in bar_ax.patches:
            height = p.get_height()
            if height > 0:
                bar_ax.annotate(f'{int(height)}', (p.get_x() + p.get_width() / 2., height + 0.5),
                                ha='center', fontsize=9)
        plt.title('Total and Correct Responses by Block')
        plt.tight_layout()

        # Response time plot
        plt.figure(figsize=(10, 6))
        test['correct_label'] = test['correct'].map({0: 'Incorrect', 1: 'Correct'})
        resp_time_ax = sns.stripplot(
            x='block_c', y='response_time', data=test, hue='correct_label', alpha=0.5, dodge=True,
            palette={'Correct': 'green', 'Incorrect': 'red'}
        )
        sns.boxplot(
            x='block_c', y='response_time', data=test, whis=np.inf, linewidth=0.5, color='gray'
        )
        plt.legend(title='Correctness', loc='upper left', bbox_to_anchor=(1.05, 1))
        plt.title('Response Time by Block')
        plt.tight_layout()

        return bar_ax, resp_time_ax

    def pc_plot(self, df):
        """
        Generates plots for PC (Performance Condition) data.

        Parameters:
            df (pd.DataFrame): Input data containing 'condition', 'correct', and 'block_c'.

        Returns:
            dict: Contains a count plot for correctness.
        """
        test = df[df['condition'] == 'test']

        # Create count plot
        plt.figure(figsize=(10, 6))
        count_ax = sns.countplot(x='condition', hue='correct', data=test)
        for p in count_ax.patches:
            height = p.get_height()
            if height > 0:
                count_ax.annotate(f'{int(height)}', (p.get_x() + p.get_width() / 2., height + 0.5),
                                  ha='center', fontsize=9)
        plt.title('Count Correct by Condition')
        plt.tight_layout()

        return count_ax


    def dsst_plot(self, df):
        """
        Generates plots for DSST (Digit Symbol Substitution Test) data.

        Parameters:
            df (pd.DataFrame): Input data containing 'acc_sum', 'correct', and 'countdown'.

        Returns:
            matplotlib.axes.Axes: The response time plot with percentage correct.
        """
        test = df[df['condition'] =='test']
        total = test['acc_sum'].max() + 1
        total_correct = test['correct'].sum()
        percent_correct = (total_correct / total) * 100  # Convert to percentage

        # Response time plot
        test['response_time'] = test['countdown'].diff(-1).abs()
        plt.figure(figsize=(10, 6))
        test['correct_label'] = test['correct'].map({0: 'Incorrect', 1: 'Correct'})

        # Main plot
        resp_time_ax = sns.stripplot(
            x='correct', y='response_time', data=test, hue='correct_label', alpha=0.5,
            palette={'Correct': 'green', 'Incorrect': 'red'}
        )
        sns.boxplot(
            x='correct', y='response_time', data=test, whis=np.inf, linewidth=0.5, color='gray'
        )
        plt.legend(title='Correctness', loc='upper left', bbox_to_anchor=(1.05, 1))
        plt.title('Response Time by Correctness')
        plt.xlabel('Correctness')
        plt.ylabel('Response Time (ms)')
        
        # Generate count plot
        plt.figure(figsize=(10, 6))
        count_ax = sns.countplot(x='condition', hue='correct', data=test)
        plt.title('Count Correct for Testing Block')

        # Add counts on top of each bar
        for p in count_ax.patches:
            height = p.get_height()
            if height > 0:
                count_ax.annotate(
                    f'{int(height)}',
                    (p.get_x() + p.get_width() / 2., height),
                    ha='center', va='bottom',
                    xytext=(0, 5), textcoords='offset points'
                )

        # Adjust y-axis limit
        max_height = max([p.get_height() for p in count_ax.patches if p.get_height() > 0])
        count_ax.set_ylim(0, max_height * 1.15)


        plt.tight_layout()
        return resp_time_ax, count_ax


class MEM_PLOTS:
    def __init__(self) -> None:
        pass

    def fn_plot(self, df):
        """
        Generate a scatter and box plot for response times by condition, and a bar chart
        showing counts of correct/incorrect responses.

        Parameters:
            df (pd.DataFrame): Input data containing 'block', 'correct', 'response_time', and 'target_congruent'.

        Returns:
            tuple: The scatter/box plot and bar chart plot objects.
        """
        block_series = df['block'].astype(str).str.strip().str.lower()
        test_mask = block_series == 'test'
        test = df[test_mask].copy()

        if test.empty:
            subject_series = df.get('subject_id')
            if subject_series is not None:
                subjects = sorted(
                    {str(value).strip() for value in subject_series.dropna() if str(value).strip()}
                )
            else:
                subjects = []

            unique_blocks = sorted({value for value in block_series.unique() if value and value != 'nan'})
            raise ValueError(
                "No 'test' block rows available for MEM plotting. "
                f"Observed block labels: {unique_blocks or '<none>'}. "
                f"Subjects in frame: {subjects or '<unknown>'}"
            )

        test['block'] = test['block'].astype(str).str.strip()
        test['correct_label'] = test['correct'].map({0: 'Incorrect', 1: 'Correct'})

        # Scatter and box plot
        plt.figure(figsize=(10, 6))
        fn_rt_ax = sns.stripplot(
            x='block', y='response_time', data=test, hue='correct_label', alpha=0.5, dodge=True,
            palette={'Correct': 'green', 'Incorrect': 'red'}
        )
        sns.boxplot(
            x='block', y='response_time', data=test, whis=np.inf, linewidth=0.5, color='gray'
        )
        plt.legend(title='Correctness', loc='upper left', bbox_to_anchor=(1.05, 1))
        plt.title('Response Time for Testing Block')
        plt.ylabel('Response Time (ms)')
        plt.xlabel('Block')
        plt.tight_layout()

        # Bar chart for correct/incorrect counts
        plt.figure(figsize=(10, 6))
        count_ax = sns.countplot(
            x='block', hue='correct', data=test,
            order=test['block'].unique(),  # Ensure 'block' categories are ordered correctly
            hue_order=[0, 1]  # Ensure 'correct' categories are ordered
        )
        plt.title('Count Correct for Testing Block')

        # Annotate bars
        for p in count_ax.patches:
            if hasattr(p, "get_height"):  # Ensure it's a bar
                height = p.get_height()
                if height > 0:  # Only annotate bars with height > 0
                    count_ax.annotate(
                        f'{int(height)}',
                        (p.get_x() + p.get_width() / 2., height),
                        ha='center', va='bottom',
                        xytext=(0, 5), textcoords='offset points'
                    )

        # Adjust y-axis limit
        max_height = max([p.get_height() for p in count_ax.patches if hasattr(p, "get_height") and p.get_height() > 0])
        count_ax.set_ylim(0, max_height * 1.15)
        plt.ylabel('Count')
        plt.xlabel('Testing Block')

        return fn_rt_ax, count_ax

    def sm_plot(self, df):
        """
        Generate a bar plot and scatter plot for response times by condition.

        Parameters:
            df (pd.DataFrame): Input data containing 'block', 'correct', and 'target_congruent'.

        Returns:
            The scatter and box plot object.
        """
        block_series = df['block'].astype(str).str.strip().str.lower()
        test_mask = block_series == 'test'
        test = df[test_mask].copy()

        if test.empty:
            subject_series = df.get('subject_id')
            if subject_series is not None:
                subjects = sorted(
                    {str(value).strip() for value in subject_series.dropna() if str(value).strip()}
                )
            else:
                subjects = []

            unique_blocks = sorted({value for value in block_series.unique() if value and value != 'nan'})
            raise ValueError(
                "No 'test' block rows available for MEM plotting. "
                f"Observed block labels: {unique_blocks or '<none>'}. "
                f"Subjects in frame: {subjects or '<unknown>'}"
            )

        test['block'] = test['block'].astype(str).str.strip()
        mapping = {'no': 'Incongruent', 'yes': 'Congruent'}
        test['target_congruent'] = test['target_congruent'].map(mapping)
        test['correct_label'] = test['correct'].map({0: 'Incorrect', 1: 'Correct'})

        # Scatter and box plot
        plt.figure(figsize=(10, 6))
        sm_ax = sns.stripplot(
            x='target_congruent', y='response_time', data=test, hue='correct_label', alpha=0.5, dodge=True,
            palette={'Correct': 'green', 'Incorrect': 'red'}
        )
        sns.boxplot(
            x='target_congruent', y='response_time', data=test, whis=np.inf, linewidth=0.5, color='gray'
        )
        #plt.xlabel
        plt.legend(title='Correctness', loc='upper left', bbox_to_anchor=(1.05, 1))
        plt.title('Response Time by Target Congruence')
        plt.tight_layout()

        return sm_ax

    def wl_plot(self, df):
        """
        Generate a scatter plot for immediate condition.

        Parameters:
            df (pd.DataFrame): Input data containing 'block', 'ratio', and 'backspace'.

        Returns:
            The scatter plot object.
        """
        df_immediate = df[df['block'] == 'immediate']

        plt.figure(figsize=(20, 7.5))
        wl_ax = sns.scatterplot(
            x='best_match', y='ratio', data=df_immediate, hue='backspace', s=75
        )
        plt.xticks(rotation=90)
        for i in range(len(df_immediate)):
            if df_immediate.iloc[i]['ratio'] < 75:
                plt.text(
                    x=df_immediate.iloc[i]['best_match'], y=df_immediate.iloc[i]['ratio'],
                    s=df_immediate.iloc[i]['word'], fontsize=9, color='black',
                    horizontalalignment='right', verticalalignment='bottom'
                )
        plt.axhline(y=75, color='r', linestyle='--')
        plt.title('Immediate Condition: Ratio vs. Best Match')
        plt.xlabel('Best Match')
        plt.ylabel('Ratio')
        plt.legend(title='Backspace Used')
        plt.tight_layout()

        return wl_ax

    def dwl_plot(self, df):
        """
        Generate a scatter plot for distraction condition.

        Parameters:
            df (pd.DataFrame): Input data containing 'block', 'ratio', and 'backspace'.

        Returns:
            The scatter plot object.
        """
        df_delay = df[df['block'] == 'delay']

        plt.figure(figsize=(20, 7.5))
        dwl_ax = sns.scatterplot(
            x='word', y='ratio', data=df_delay, hue='backspace', s=75
        )
        plt.xticks(rotation=90)
        for i in range(len(df_delay)):
            if df_delay.iloc[i]['ratio'] < 75:
                plt.text(
                    x=df_delay.iloc[i]['word'], y=df_delay.iloc[i]['ratio'],
                    s=df_delay.iloc[i]['word'], fontsize=9, color='black',
                    horizontalalignment='right', verticalalignment='bottom'
                )
        plt.axhline(y=75, color='r', linestyle='--')
        plt.title('Delay Condition: Ratio vs. Word')
        plt.xlabel('Word')
        plt.ylabel('Ratio')
        plt.legend(title='Backspace Used')
        plt.tight_layout()

        return dwl_ax





















































