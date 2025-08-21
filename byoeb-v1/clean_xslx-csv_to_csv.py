import csv
import re

def clean_and_convert_to_csv(input_filepath, output_filepath):
    """
    Reads a text file with multi-line entries, cleans it, and converts it to a CSV.
    The script uses a regex-based approach to correctly identify full records,
    regardless of how many lines they span.

    Args:
        input_filepath (str): The path to the input file (e.g., 'oncobot-kb.csv').
        output_filepath (str): The path where the cleaned CSV will be saved.
    """
    print(f"Reading from: {input_filepath}")
    
    try:
        with open(input_filepath, 'r', encoding='utf-8') as infile:
            content = infile.read()
    except FileNotFoundError:
        print(f"Error: The file '{input_filepath}' was not found.")
        return
    except Exception as e:
        print(f"An error occurred while reading the file: {e}")
        return

    # Use a single, powerful regex to find all records.
    # A record starts with a number and a tab (\d+\t), followed by non-greedy content (.+?)
    # that stops just before the next record starts (positive lookahead: (?=\n\d+\t|\Z)).
    # The `re.DOTALL` flag allows '.' to match newlines, which is crucial here.
    records = re.findall(r'(\d+)\t(.+?)(?=\n\d+\t|\Z)', content, re.DOTALL)

    cleaned_rows = []
    entry_number = 1
    
    print(f"Found {len(records)} potential records.")
    
    for record_id, record_content in records:
        # The content part of the record is separated by tabs.
        # We need to handle the multi-line final column.
        columns = record_content.strip().split('\t')

        # The last column is the one that contains the multi-line text.
        # We join all subsequent items into the last column.
        if len(columns) > 3:
            columns = columns[:2] + [' '.join(columns[2:])]
        elif len(columns) < 3:
            columns.extend([''] * (3 - len(columns)))
        
        # Now, join the multi-line content into a single string by replacing
        # all newlines with a single space.
        columns = [col.replace('\n', ' ') for col in columns]

        # Add the new sequential ID and the cleaned columns to our list.
        cleaned_rows.append([entry_number] + [col.strip() for col in columns])
        entry_number += 1

    # Write the cleaned data to the new CSV file.
    try:
        with open(output_filepath, 'w', newline='', encoding='utf-8') as outfile:
            writer = csv.writer(outfile)
            
            # Write a header row.
            writer.writerow(['ID', 'Column 2', 'Column 3', 'Column 4'])
            
            # Write the cleaned data rows.
            writer.writerows(cleaned_rows)
            
        print(f"\nSuccessfully cleaned data and saved it to: {output_file_path}")
        print(f"Total rows written: {len(cleaned_rows)}")
    except Exception as e:
        print(f"An error occurred while writing the file: {e}")

# --- Main part of the script ---
if __name__ == '__main__':
    # Define your input and output file paths.
    input_file_path = r"C:\Users\t-asanghvi\OneDrive - Microsoft\Desktop\chatbots\OncoBot-KB\oncobot-kb.csv"
    output_file_path = r"C:\Users\t-asanghvi\OneDrive - Microsoft\Desktop\chatbots\OncoBot-KB\oncobot-kb-cleaned.csv"
    
    clean_and_convert_to_csv(input_file_path, output_file_path)

