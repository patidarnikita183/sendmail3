import pandas as pd
import re
from werkzeug.utils import secure_filename
from .tracking import add_email_tracking

def process_dataframe(df):
    """Process pandas DataFrame to extract name and email columns"""
    recipients = []
    df.columns = df.columns.str.strip().str.lower()
    
    name_column = None
    email_column = None
    name_patterns = ['name', 'full_name', 'fullname', 'first_name', 'firstname', 'recipient', 'contact']
    email_patterns = ['email', 'e-mail', 'mail', 'email_address', 'emailaddress']
    
    for col in df.columns:
        if any(pattern in col for pattern in name_patterns) and not name_column:
            name_column = col
        if any(pattern in col for pattern in email_patterns) and not email_column:
            email_column = col
    
    if not email_column:
        for col in df.columns:
            if df[col].astype(str).str.contains('@').any():
                email_column = col
                break
        if not email_column and len(df.columns) >= 1:
            email_column = df.columns[-1]
    
    if not name_column and len(df.columns) >= 2:
        for col in df.columns:
            if col != email_column:
                name_column = col
                break
    
    if not email_column:
        raise ValueError("Could not find email column in the file.")
    
    for index, row in df.iterrows():
        try:
            email = str(row[email_column]).strip() if pd.notna(row[email_column]) else ''
            name = str(row[name_column]).strip() if name_column and pd.notna(row[name_column]) else ''
            if email and '@' in email:
                if not name or name.lower() in ['nan', 'none', '']:
                    name = email.split('@')[0]
                recipients.append({'name': name, 'email': email.lower()})
        except Exception as e:
            print(f"Error processing row {index}: {e}")
            continue
    
    if not recipients:
        raise ValueError("No valid email addresses found in the file.")
    
    return recipients

def parse_email_addresses(text):
    """Extract email addresses from text"""
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    return re.findall(pattern, text)

def process_uploaded_file(file):
    """Process uploaded file and extract recipient data"""
    filename = secure_filename(file.filename)
    file_extension = filename.lower().split('.')[-1]
    recipients = []
    
    try:
        if file_extension in ['xlsx', 'xls']:
            df = pd.read_excel(file.stream)
            recipients = process_dataframe(df)
        elif file_extension == 'csv':
            file.stream.seek(0)
            df = pd.read_csv(file.stream)
            recipients = process_dataframe(df)
        elif file_extension == 'txt':
            file.stream.seek(0)
            content = file.stream.read().decode('utf-8')
            emails = parse_email_addresses(content)
            recipients = [{'name': email.split('@')[0], 'email': email} for email in emails]
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")
    except Exception as e:
        raise Exception(f"Error processing {file_extension.upper()} file: {str(e)}")
    
    return recipients

def validate_email(email):
    """Validate email address format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None