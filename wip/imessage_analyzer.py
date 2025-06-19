#!/usr/bin/env python3
"""
iMessage Analyzer - Comprehensive iMessage Database Analysis Tool

This script uses the imessage_tools library to extract, analyze, and export
iMessage data from macOS chat.db files.

Features:
- Extract all messages with proper text decoding (handles macOS Ventura+ issues)
- Extract contacts, chat threads, and attachments
- Create summary statistics and analytics
- Export to CSV files and individual conversations
- Search functionality
- Message analytics and visualizations

Usage:
    python imessage_analyzer.py

    # Or with custom database path:
    python imessage_analyzer.py --db-path /path/to/chat.db

    # Export only recent messages:
    python imessage_analyzer.py --limit 1000

Author: AI Assistant
Dependencies: pandas, imessage_tools
"""

import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import sqlite3
from imessage_tools import read_messages, get_chat_mapping
import json
from collections import defaultdict, Counter
import re
import subprocess
from mlh.hypers import Hypers
from dataclasses import dataclass
from typing import Optional


@dataclass
class Args(Hypers):
    db_path: Optional[str] = None
    output_dir: str = 'imessage_export'
    limit: Optional[int] = None
    search: Optional[str] = None
    contact: Optional[str] = None
    quiet: bool = False
    send_recipient: Optional[str] = None
    send_message: Optional[str] = None
    send_file: Optional[str] = None


def get_database_path(db_path: Optional[str]) -> Path:
    """Get the database path, using default if not provided."""
    if db_path is None:
        return Path.home() / "Library" / "Messages" / "chat.db"
    return Path(db_path)


def log_message(message: str, verbose: bool) -> None:
    """Print message if verbose mode is enabled."""
    if verbose:
        print(message)


def convert_timestamp(ts):
    """Convert Apple timestamp to datetime."""
    if pd.isna(ts) or ts == 0:
        return None
    epoch_offset = 978307200  # Seconds between 1970-01-01 and 2001-01-01
    seconds = ts / 1000000000 + epoch_offset
    return datetime.fromtimestamp(seconds)


def execute_query(db_path: Path, query: str) -> pd.DataFrame:
    """Execute SQL query and return DataFrame."""
    conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    result = pd.read_sql_query(query, conn)
    conn.close()
    return result


def get_contacts(db_path: Path, verbose: bool) -> pd.DataFrame:
    """Extract contact information from the handle table."""
    log_message("Extracting contacts...", verbose)

    query = """
    SELECT ROWID, id, country, service, person_centric_id
    FROM handle
    ORDER BY ROWID
    """

    contacts_df = execute_query(db_path, query)
    log_message(f"Found {len(contacts_df)} contacts", verbose)
    return contacts_df


def get_chat_threads(db_path: Path, verbose: bool) -> pd.DataFrame:
    """Extract chat thread information."""
    log_message("Extracting chat threads...", verbose)

    query = """
    SELECT
        ROWID,
        guid,
        chat_identifier,
        display_name,
        service_name,
        account_login,
        is_archived,
        group_id,
        last_read_message_timestamp,
        is_filtered
    FROM chat
    ORDER BY ROWID
    """

    chats_df = execute_query(db_path, query)
    chats_df['last_read_message_datetime'] = chats_df['last_read_message_timestamp'].apply(convert_timestamp)

    log_message(f"Found {len(chats_df)} chat threads", verbose)
    return chats_df


def get_attachments(db_path: Path, verbose: bool) -> pd.DataFrame:
    """Extract attachment information."""
    log_message("Extracting attachments...", verbose)

    query = """
    SELECT
        a.ROWID as attachment_id,
        a.filename,
        a.mime_type,
        a.transfer_state,
        a.is_outgoing,
        a.created_date,
        maj.message_id
    FROM attachment a
    LEFT JOIN message_attachment_join maj ON a.ROWID = maj.attachment_id
    ORDER BY a.ROWID
    """

    attachments_df = execute_query(db_path, query)
    attachments_df['created_datetime'] = attachments_df['created_date'].apply(convert_timestamp)

    log_message(f"Found {len(attachments_df)} attachments", verbose)
    return attachments_df


def get_all_messages(db_path: Path, limit: Optional[int], verbose: bool) -> list:
    """Extract all messages using the imessage_tools library."""
    log_message("Extracting messages using imessage_tools...", verbose)

    messages = read_messages(
        str(db_path),
        n=limit,
        self_number="Me",
        human_readable_date=True
    )

    log_message(f"Extracted {len(messages)} messages", verbose)
    return messages


def organize_messages_by_chat(messages: list, verbose: bool) -> dict:
    """Organize messages by chat/conversation."""
    log_message("Organizing messages by chat...", verbose)

    messages_df = pd.DataFrame(messages)

    chats = {}
    for phone_number, group in messages_df.groupby('phone_number'):
        chats[phone_number] = {
            'contact': phone_number,
            'message_count': len(group),
            'messages': group.to_dict('records'),
            'first_message_date': group['date'].min(),
            'last_message_date': group['date'].max(),
            'sent_count': len(group[group['is_from_me'] == 1]),
            'received_count': len(group[group['is_from_me'] == 0])
        }

    log_message(f"Organized into {len(chats)} conversations", verbose)
    return chats


def calculate_message_stats(df: pd.DataFrame) -> dict:
    """Calculate basic message statistics."""
    df['message_length'] = df['body'].astype(str).str.len()

    return {
        'total_messages': len(df),
        'messages_sent': len(df[df['is_from_me'] == 1]),
        'messages_received': len(df[df['is_from_me'] == 0]),
        'unique_contacts': df['phone_number'].nunique(),
        'group_chats': len(df[df['group_chat_name'] != ""]),
        'message_length_stats': {
            'mean': float(df['message_length'].mean()),
            'median': float(df['message_length'].median()),
            'max': int(df['message_length'].max()),
            'min': int(df['message_length'].min())
        }
    }


def calculate_temporal_stats(df: pd.DataFrame) -> dict:
    """Calculate time-based statistics."""
    df['date_parsed'] = pd.to_datetime(df['date'])
    df['year'] = df['date_parsed'].dt.year
    df['month'] = df['date_parsed'].dt.to_period('M').astype(str)
    df['hour'] = df['date_parsed'].dt.hour
    df['day_of_week'] = df['date_parsed'].dt.day_name()

    return {
        'date_range': {
            'earliest': df['date_parsed'].min().isoformat(),
            'latest': df['date_parsed'].max().isoformat(),
            'days_span': (df['date_parsed'].max() - df['date_parsed'].min()).days
        },
        'messages_by_year': {str(k): int(v) for k, v in df['year'].value_counts().sort_index().to_dict().items()},
        'messages_by_month': df['month'].value_counts().sort_index().to_dict(),
        'messages_by_hour': {str(k): int(v) for k, v in df['hour'].value_counts().sort_index().to_dict().items()},
        'messages_by_day_of_week': df['day_of_week'].value_counts().to_dict(),
        'busiest_day': {str(k): int(v) for k, v in df['date_parsed'].dt.date.value_counts().head(1).to_dict().items()}
    }


def analyze_response_patterns(df: pd.DataFrame) -> dict:
    """Analyze response patterns and conversation dynamics."""
    patterns = {}

    for contact, group in df.groupby('phone_number'):
        if len(group) < 2:
            continue

        group = group.sort_values('date_parsed')
        group['time_diff'] = group['date_parsed'].diff()

        sent = group[group['is_from_me'] == 1]
        received = group[group['is_from_me'] == 0]

        if len(sent) > 0 and len(received) > 0:
            patterns[contact] = {
                'avg_response_time_minutes': float(group['time_diff'].dt.total_seconds().mean() / 60) if not group['time_diff'].dt.total_seconds().isna().all() else 0.0,
                'conversation_count': int(len(group)),
                'sent_ratio': float(len(sent) / len(group)),
                'avg_message_length_sent': float(sent['message_length'].mean()),
                'avg_message_length_received': float(received['message_length'].mean())
            }

    return patterns


def create_summary_stats(messages: list, verbose: bool) -> dict:
    """Create comprehensive summary statistics about the messages."""
    log_message("Creating summary statistics...", verbose)

    df = pd.DataFrame(messages)

    if df.empty:
        return {'error': 'No messages found'}

    # Prepare dataframe for analysis
    df['date_parsed'] = pd.to_datetime(df['date'])
    df['message_length'] = df['body'].astype(str).str.len()

    # Combine all statistics
    stats = {}
    stats.update(calculate_message_stats(df))
    stats.update(calculate_temporal_stats(df))

    stats['messages_by_contact'] = df['phone_number'].value_counts().head(20).to_dict()
    stats['response_patterns'] = analyze_response_patterns(df)

    return stats


def search_messages(db_path: Path, search_term: str, case_sensitive: bool = False, regex: bool = False, verbose: bool = True) -> list:
    """Search for messages containing a specific term or pattern."""
    log_message(f"Searching for: '{search_term}'", verbose)

    messages = get_all_messages(db_path, None, verbose)

    results = []
    for msg in messages:
        text = msg.get('body', '')

        if regex:
            pattern = re.compile(search_term, re.IGNORECASE if not case_sensitive else 0)
            if pattern.search(text):
                results.append(msg)
        else:
            if not case_sensitive:
                text = text.lower()
                search_term = search_term.lower()

            if search_term in text:
                results.append(msg)

    log_message(f"Found {len(results)} matching messages", verbose)
    return results


def get_conversation(db_path: Path, contact_identifier: str, limit: Optional[int], verbose: bool) -> list:
    """Get messages for a specific contact or chat."""
    messages = get_all_messages(db_path, None, verbose)

    conversation = [
        msg for msg in messages
        if msg['phone_number'] == contact_identifier or msg['group_chat_name'] == contact_identifier
    ]

    if limit:
        conversation = conversation[:limit]

    return conversation


def save_dataframes_to_csv(output_path: Path, messages_df: pd.DataFrame, contacts: pd.DataFrame,
                          chats: pd.DataFrame, attachments: pd.DataFrame) -> None:
    """Save all DataFrames to CSV files."""
    messages_df.to_csv(output_path / "messages.csv", index=False)
    contacts.to_csv(output_path / "contacts.csv", index=False)
    chats.to_csv(output_path / "chat_threads.csv", index=False)
    attachments.to_csv(output_path / "attachments.csv", index=False)


def save_individual_conversations(output_path: Path, conversations: dict) -> None:
    """Save individual conversation files."""
    conversations_dir = output_path / "conversations"
    conversations_dir.mkdir(exist_ok=True)

    for contact, data in conversations.items():
        safe_filename = "".join(c if c.isalnum() or c in ".-_@" else "_" for c in str(contact))
        convo_df = pd.DataFrame(data['messages'])
        convo_df.to_csv(conversations_dir / f"{safe_filename}.csv", index=False)


def export_to_csv(db_path: Path, output_dir: str, limit: Optional[int], verbose: bool) -> dict:
    """Export all data to CSV files."""
    output_path = Path.home() / "Desktop" / output_dir
    output_path.mkdir(exist_ok=True)

    log_message(f"Exporting data to {output_path}", verbose)

    # Get all data
    messages = get_all_messages(db_path, limit, verbose)
    contacts = get_contacts(db_path, verbose)
    chats = get_chat_threads(db_path, verbose)
    attachments = get_attachments(db_path, verbose)

    # Convert messages to DataFrame
    messages_df = pd.DataFrame(messages)

    # Save CSV files
    save_dataframes_to_csv(output_path, messages_df, contacts, chats, attachments)

    # Save organized conversations
    conversations = organize_messages_by_chat(messages, verbose)
    save_individual_conversations(output_path, conversations)

    # Save summary statistics
    stats = create_summary_stats(messages, verbose)
    with open(output_path / "summary_stats.json", 'w') as f:
        json.dump(stats, f, indent=2, default=str)

    log_message(f"Exported {len(messages)} messages to CSV files", verbose)
    log_message(f"Created {len(conversations)} individual conversation files", verbose)

    return {
        'messages': messages_df,
        'contacts': contacts,
        'chats': chats,
        'attachments': attachments,
        'conversations': conversations,
        'stats': stats,
        'output_path': output_path
    }


def escape_applescript_string(text: str) -> str:
    """Properly escape strings for AppleScript to prevent injection."""
    return text.replace('\\', '\\\\').replace('"', '\\"')


def send_message(recipient: str, message: str, verbose: bool) -> dict:
    """Send an iMessage using AppleScript with proper error handling and escaping."""
    escaped_recipient = escape_applescript_string(recipient)
    escaped_message = escape_applescript_string(message)

    apple_script = f'''
    tell application "Messages"
        activate
        delay 0.5

        try
            set targetService to 1st service whose service type = iMessage
            set targetBuddy to buddy "{escaped_recipient}" of targetService
            send "{escaped_message}" to targetBuddy
            return "success"
        on error errorMessage
            return "error: " & errorMessage
        end try
    end tell
    '''

    result = subprocess.run(
        ["osascript", "-e", apple_script],
        capture_output=True,
        text=True,
        timeout=30
    )

    if result.returncode == 0:
        output = result.stdout.strip()
        if output == "success":
            log_message(f"Message sent successfully to {recipient}", verbose)
            return {
                'success': True,
                'recipient': recipient,
                'message': message,
                'timestamp': datetime.now().isoformat()
            }
        else:
            log_message(f"AppleScript error: {output}", verbose)
            return {
                'success': False,
                'error': output,
                'recipient': recipient
            }
    else:
        error_msg = result.stderr.strip() or "Unknown AppleScript error"
        log_message(f"Failed to send message: {error_msg}", verbose)
        return {
            'success': False,
            'error': error_msg,
            'recipient': recipient
        }


def send_bulk_messages(messages: list, delay_seconds: float = 1.0, verbose: bool = True) -> list:
    """Send multiple messages with optional delay between sends."""
    import time
    results = []

    for i, msg_data in enumerate(messages):
        if isinstance(msg_data, dict):
            recipient = msg_data.get('recipient')
            message = msg_data.get('message')
        elif isinstance(msg_data, (list, tuple)) and len(msg_data) == 2:
            recipient, message = msg_data
        else:
            results.append({
                'success': False,
                'error': f"Invalid message format at index {i}",
                'recipient': None
            })
            continue

        if not recipient or not message:
            results.append({
                'success': False,
                'error': "Missing recipient or message",
                'recipient': recipient
            })
            continue

        result = send_message(recipient, message, verbose)
        results.append(result)

        # Add delay between messages (except for the last one)
        if i < len(messages) - 1 and delay_seconds > 0:
            time.sleep(delay_seconds)

    return results


def print_summary(stats: dict) -> None:
    """Print export summary statistics."""
    print(f"\n=== EXPORT SUMMARY ===")
    print(f"Total messages: {stats['total_messages']:,}")
    print(f"Messages sent: {stats['messages_sent']:,}")
    print(f"Messages received: {stats['messages_received']:,}")
    print(f"Unique contacts: {stats['unique_contacts']:,}")
    print(f"Group chats: {stats['group_chats']:,}")
    print(f"Date range: {stats['date_range']['earliest']} to {stats['date_range']['latest']}")

    print(f"\n=== TOP CONTACTS ===")
    for contact, count in list(stats['messages_by_contact'].items())[:10]:
        print(f"{contact}: {count:,} messages")


def handle_search(args: Args) -> None:
    """Handle search functionality."""
    db_path = get_database_path(args.db_path)
    results = search_messages(db_path, args.search, verbose=not args.quiet)
    print(f"Found {len(results)} messages containing '{args.search}':")
    for msg in results[:10]:  # Show first 10 results
        print(f"[{msg['date']}] {msg['phone_number']}: {msg['body'][:100]}...")


def handle_contact_export(args: Args) -> None:
    """Handle specific contact export."""
    db_path = get_database_path(args.db_path)
    conversation = get_conversation(db_path, args.contact, None, not args.quiet)
    df = pd.DataFrame(conversation)
    output_file = Path.home() / "Desktop" / f"conversation_{args.contact}.csv"
    df.to_csv(output_file, index=False)
    print(f"Exported {len(conversation)} messages to {output_file}")


def handle_send_message(args: Args) -> None:
    """Handle sending a single message."""
    result = send_message(args.send_recipient, args.send_message, not args.quiet)
    if result['success']:
        print(f"✓ Message sent to {args.send_recipient}")
    else:
        print(f"✗ Failed to send message: {result.get('error', 'Unknown error')}")


def handle_send_file(args: Args) -> None:
    """Handle sending messages from file."""
    with open(args.send_file, 'r') as f:
        messages_to_send = json.load(f)

    results = send_bulk_messages(messages_to_send, verbose=not args.quiet)
    successful = sum(1 for r in results if r['success'])
    print(f"Sent {successful}/{len(results)} messages successfully")

    # Show any failures
    for result in results:
        if not result['success']:
            print(f"✗ Failed to send to {result.get('recipient', 'unknown')}: {result.get('error')}")


def main():
    """Main function with command-line interface."""
    args = Args()

    # Validate database path
    db_path = get_database_path(args.db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found at {db_path}")

    # Handle different modes
    if args.search:
        handle_search(args)
        return

    if args.contact:
        handle_contact_export(args)
        return

    if args.send_recipient and args.send_message:
        handle_send_message(args)
        return

    if args.send_file:
        handle_send_file(args)
        return

    # Full export
    data = export_to_csv(db_path, args.output_dir, args.limit, not args.quiet)

    # Print summary
    if not args.quiet:
        print_summary(data['stats'])
        print(f"\nFiles saved to: {data['output_path']}")

    return data


if __name__ == "__main__":
    data = main()
