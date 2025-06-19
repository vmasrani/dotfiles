import os
import sqlite3
import pandas as pd
from datetime import datetime
from pathlib import Path
import re
import binascii

def print_table_schema(cursor, table):
    print(f"\n--- Schema for table: {table} ---")
    cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}';")
    schema = cursor.fetchone()
    print(schema[0])

def print_table_preview(cursor, table, limit=5):
    print(f"\n--- Sample rows from table: {table} ---")
    cursor.execute(f"SELECT * FROM {table} LIMIT {limit};")
    col_names = [desc[0] for desc in cursor.description]
    print(" | ".join(col_names))
    for row in cursor.fetchall():
        print(" | ".join(str(r) if r is not None else "NULL" for r in row))

def convert_apple_time(timestamp):
    """Convert Apple's timestamp format to human-readable date/time."""
    if not timestamp:
        return None
    # Apple time is nanoseconds since 2001-01-01
    epoch_offset = 978307200  # Seconds between 1970-01-01 and 2001-01-01
    seconds = timestamp / 1000000000 + epoch_offset
    return datetime.fromtimestamp(seconds)

def extract_text_from_attributed_body(data):
    """Extract readable text from attributedBody BLOB using multiple methods."""
    if not data:
        return None

    try:
        # Method 1: Direct string search in binary data
        text_candidates = []

        # Look for readable ASCII text of reasonable length
        ascii_text = data.decode('ascii', errors='ignore')
        # Find sequences of printable characters (letters, numbers, spaces, common punctuation)
        text_pattern = re.compile(r'[A-Za-z0-9\s.,:;!?\'"@+\-(){}[\]/\\#$%^&*=_|<>~`]{10,}')
        matches = text_pattern.findall(ascii_text)
        text_candidates.extend(matches)

        # Method 2: UTF-8 decoding with error handling
        try:
            utf8_text = data.decode('utf-8', errors='ignore')
            utf8_matches = text_pattern.findall(utf8_text)
            text_candidates.extend(utf8_matches)
        except:
            pass

        # Method 3: Look for NSString content after binary markers
        hex_data = data.hex()

        # Common patterns in NSAttributedString that precede text content
        nsstring_patterns = [
            r'4e53537472696e67.{2,20}?([0-9a-f]{400,})',  # NSString marker
            r'4e534d757461626c65537472696e67.{2,20}?([0-9a-f]{400,})',  # NSMutableString
        ]

        for pattern in nsstring_patterns:
            matches = re.findall(pattern, hex_data, re.IGNORECASE)
            for match in matches:
                try:
                    # Try to decode hex to text
                    decoded_bytes = bytes.fromhex(match[:800])  # Limit to reasonable length
                    decoded_text = decoded_bytes.decode('utf-8', errors='ignore')
                    clean_text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', decoded_text)  # Remove control chars
                    if len(clean_text) > 5:
                        text_candidates.append(clean_text)
                except:
                    continue

        # Method 4: Search for text patterns with Unicode support
        try:
            # Some messages might have text directly embedded
            unicode_pattern = re.compile(r'[\u0020-\u007E\u00A0-\uFFFF]{5,}', re.UNICODE)
            unicode_text = data.decode('utf-8', errors='replace')
            unicode_matches = unicode_pattern.findall(unicode_text)
            text_candidates.extend(unicode_matches)
        except:
            pass

        # Filter and select best candidate
        valid_candidates = []
        for candidate in text_candidates:
            # Clean up the candidate
            cleaned = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', candidate)
            cleaned = cleaned.strip()

            # Skip candidates that are mostly non-alphanumeric or too short
            if len(cleaned) < 5:
                continue
            if len(re.sub(r'[^a-zA-Z0-9\s]', '', cleaned)) < 3:
                continue
            # Skip obvious technical strings
            if any(skip in cleaned for skip in ['NSString', 'NSMutable', 'NSObject', 'kIM', '__kIM']):
                continue

            valid_candidates.append(cleaned)

        if valid_candidates:
            # Return the longest reasonable candidate
            best_candidate = max(valid_candidates, key=len)
            # If it's extremely long, truncate it
            if len(best_candidate) > 500:
                best_candidate = best_candidate[:500] + "..."
            return best_candidate

    except Exception as e:
        return f"[Extraction error: {str(e)[:50]}]"

    return "[No readable text found]"

def extract_messages():
    # Connect to the Messages database
    db_path = Path.home() / "Library" / "Messages" / "chat.db"
    print(f"Connecting to: {db_path}")

    # Connect in read-only mode
    conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)

    # Query to get all message data including potential text sources
    query = """
    SELECT
        c.display_name,
        c.chat_identifier,
        h.id as contact_id,
        m.ROWID as message_id,
        m.is_from_me,
        m.text,
        m.attributedBody,
        m.date as timestamp,
        m.service,
        m.account,
        m.cache_has_attachments,
        m.is_audio_message,
        m.balloon_bundle_id
    FROM chat c
    JOIN chat_message_join cmj ON c.ROWID = cmj.chat_id
    JOIN message m ON cmj.message_id = m.ROWID
    LEFT JOIN handle h ON m.handle_id = h.ROWID
    ORDER BY c.ROWID, m.date
    """

    # Convert to DataFrame for easy manipulation
    df = pd.read_sql_query(query, conn)

    # Process timestamps
    df['datetime'] = df['timestamp'].apply(convert_apple_time)

    # Add a sender column for clarity
    df['sender'] = df.apply(
        lambda row: 'Me' if row['is_from_me'] == 1 else (row['contact_id'] or 'Unknown'),
        axis=1
    )

    # Extract message content with priority: text field first, then attributedBody
    def get_message_content(row):
        # First check if there's plain text
        if row['text'] and len(str(row['text']).strip()) > 0:
            return str(row['text']).strip()

        # Check for special message types
        if row['cache_has_attachments']:
            attachment_note = "[Has attachments] "
        else:
            attachment_note = ""

        if row['is_audio_message']:
            return f"{attachment_note}[Audio message]"

        if row['balloon_bundle_id'] and 'URL' in str(row['balloon_bundle_id']):
            extracted = extract_text_from_attributed_body(row['attributedBody'])
            return f"{attachment_note}[Link] {extracted}" if extracted and extracted != "[No readable text found]" else f"{attachment_note}[Link message]"

        # Try to extract from attributedBody
        if row['attributedBody']:
            extracted = extract_text_from_attributed_body(row['attributedBody'])
            return f"{attachment_note}{extracted}" if extracted else f"{attachment_note}[Binary message content]"

        return f"{attachment_note}[Empty message]"

    df['message'] = df.apply(get_message_content, axis=1)

    # Create a more readable dataframe
    readable_df = df[['chat_identifier', 'sender', 'message', 'datetime', 'service']].copy()

    # Clean up chat identifiers for better readability
    readable_df['chat_name'] = readable_df['chat_identifier'].apply(
        lambda x: x.split('@')[0] if '@' in str(x) else str(x)
    )

    # Organize chats into separate DataFrames
    chat_groups = {name: group for name, group in readable_df.groupby('chat_identifier')}

    # Print a summary of the chats
    print(f"\nFound {len(chat_groups)} conversations")

    return readable_df, chat_groups

def main():
    readable_df, chat_groups = extract_messages()

    # Save to CSV
    output_path = Path.home() / "Desktop" / "messages_export.csv"
    readable_df.to_csv(output_path, index=False)
    print(f"Saved all messages to: {output_path}")

    # Print sample from each conversation
    for chat_id, chat_df in chat_groups.items():
        print(f"\n=== Conversation with {chat_id} ===")
        # Get a sample of messages from this chat
        sample = chat_df[['sender', 'message', 'datetime']].head(5)
        for _, row in sample.iterrows():
            print(f"{row['sender']}: {row['message'][:100]}{'...' if len(row['message']) > 100 else ''}")
            print(f"  -> {row['datetime']}")
        print()

    # Save each conversation to a separate file
    output_dir = Path.home() / "Desktop" / "message_conversations"
    output_dir.mkdir(exist_ok=True)

    for chat_id, chat_df in chat_groups.items():
        # Create a safe filename
        safe_filename = "".join(c if c.isalnum() or c in ".-_" else "_" for c in str(chat_id))
        chat_path = output_dir / f"{safe_filename}.csv"

        # Save conversation data
        chat_df[['sender', 'message', 'datetime', 'service']].to_csv(
            chat_path,
            index=False
        )

    print(f"\nSaved individual conversations to: {output_dir}")
    print(f"Total messages processed: {len(readable_df)}")

if __name__ == "__main__":
    main()
