"""
Script to convert CSV Q&A file to knowledge base format for BYOeB
"""
import pandas as pd
import os
from pathlib import Path

def csv_to_kb_files(csv_path, output_dir, question_col="Question", answer_col="Answer", category_col="Q_Type"):
    """
    Convert CSV Q&A file to individual text files for knowledge base
    
    Args:
        csv_path: Path to your CSV file
        output_dir: Directory to save the text files
        question_col: Column name containing questions
        answer_col: Column name containing answers
        category_col: Column name containing categories (optional)
    """
    
    # Read CSV file
    try:
        df = pd.read_csv(csv_path)
        print(f"Successfully loaded {len(df)} rows from {csv_path}")
        print(f"Columns: {list(df.columns)}")
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return
    
    # Check if columns exist
    if question_col not in df.columns:
        print(f"Question column '{question_col}' not found!")
        return
    
    if answer_col not in df.columns:
        print(f"Answer column '{answer_col}' not found!")
        return
    
    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Convert each Q&A pair to a text file
    created_files = 0
    for idx, row in df.iterrows():
        if pd.isna(row[question_col]) or pd.isna(row[answer_col]):
            print(f"Skipping row {idx} - missing question or answer")
            continue
            
        question = str(row[question_col]).strip()
        answer = str(row[answer_col]).strip()
        
        # Include category if available
        category = ""
        if category_col in df.columns and not pd.isna(row[category_col]):
            category = f"Category: {str(row[category_col]).strip()}\n\n"
        
        # Create content combining category, question and answer
        content = f"{category}Question: {question}\n\nAnswer: {answer}"
        
        # Create safe filename from question (first 50 chars)
        safe_filename = "".join(c for c in question[:50] if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"qa_{idx+1:03d}_{safe_filename}.txt"
        
        # Write to file
        file_path = os.path.join(output_dir, filename)
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Created: {filename}")
            created_files += 1
        except Exception as e:
            print(f"Error writing file {filename}: {e}")
    
    print(f"\nConversion complete! Created {created_files} files in: {output_dir}")

def csv_to_single_kb_file(csv_path, output_file, question_col="Question", answer_col="Answer", category_col="Q_Type"):
    """
    Convert CSV Q&A file to a single knowledge base file
    """
    try:
        df = pd.read_csv(csv_path)
        print(f"Successfully loaded {len(df)} rows from {csv_path}")
        print(f"Columns: {list(df.columns)}")
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return
    
    # Check if columns exist
    if question_col not in df.columns:
        print(f"Question column '{question_col}' not found!")
        return
    
    if answer_col not in df.columns:
        print(f"Answer column '{answer_col}' not found!")
        return
    
    content_parts = []
    processed_count = 0
    
    for idx, row in df.iterrows():
        if pd.isna(row[question_col]) or pd.isna(row[answer_col]):
            continue
            
        question = str(row[question_col]).strip()
        answer = str(row[answer_col]).strip()
        
        # Include category if available
        category_info = ""
        if category_col in df.columns and not pd.isna(row[category_col]):
            category_info = f" (Category: {str(row[category_col]).strip()})"
        
        content_parts.append(f"Q{idx+1}{category_info}: {question}")
        content_parts.append(f"A{idx+1}: {answer}")
        content_parts.append("")  # Empty line for separation
        processed_count += 1
    
    # Write all content to single file
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(content_parts))
        print(f"Knowledge base file created: {output_file}")
        print(f"Processed {processed_count} Q&A pairs")
    except Exception as e:
        print(f"Error writing file: {e}")

def inspect_csv_file(csv_path):
    """
    Inspect CSV file to see its structure and column names
    """
    print(f"Inspecting CSV file: {csv_path}")
    print("-" * 50)
    
    try:
        df = pd.read_csv(csv_path)
        print(f"✓ Successfully read CSV file")
        print(f"Shape: {df.shape} (rows, columns)")
        print(f"Columns: {list(df.columns)}")
        print("\nFirst few rows:")
        print(df.head())
        print(f"\nData types:")
        print(df.dtypes)
        print(f"\nMissing values:")
        print(df.isnull().sum())
        return df
    except Exception as e:
        print(f"✗ Failed to read CSV: {e}")
        return None

if __name__ == "__main__":
    # Path to your cleaned CSV file (now local)
    csv_file = "oncobot-kb-cleaned.csv"
    kb_output_dir = "knowledge_base_files"     # Directory for multiple files
    kb_single_file = "knowledge_base.txt"      # Single file option
    
    print("Choose an option:")
    print("0. Inspect CSV file (see structure and columns)")
    print("1. Multiple files (one per Q&A pair)")
    print("2. Single file (all Q&As together)")
    
    choice = input("Enter choice (0, 1, or 2): ").strip()
    
    if choice == "0":
        inspect_csv_file(csv_file)
    elif choice == "1":
        csv_to_kb_files(csv_file, kb_output_dir, 
                       question_col="Question", 
                       answer_col="Answer",
                       category_col="Q_Type")
    elif choice == "2":
        csv_to_single_kb_file(csv_file, kb_single_file,
                              question_col="Question", 
                              answer_col="Answer",
                              category_col="Q_Type")
    else:
        print("Invalid choice")
