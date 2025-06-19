#!/usr/bin/env python3
"""
Example usage of the iMessage Analyzer

This script demonstrates various ways to use the iMessageAnalyzer class
for extracting and analyzing iMessage data.
"""

from imessage_analyzer import iMessageAnalyzer
import pandas as pd
import json
from pathlib import Path

def basic_usage_example():
    """Basic usage - export all data."""
    print("=== Basic Usage Example ===")

    # Initialize the analyzer
    analyzer = iMessageAnalyzer()

    # Export all data to CSV files
    data = analyzer.export_to_csv(output_dir="my_imessage_data")

    # Access the results
    messages_df = data['messages']
    contacts_df = data['contacts']
    stats = data['stats']

    print(f"Exported {len(messages_df)} messages")
    print(f"Found {len(contacts_df)} contacts")
    print(f"Date range: {stats['date_range']['earliest']} to {stats['date_range']['latest']}")

def search_example():
    """Example of searching through messages."""
    print("\n=== Search Example ===")

    analyzer = iMessageAnalyzer(verbose=False)

    # Search for messages containing "Clubhouse"
    clubhouse_messages = analyzer.search_messages("Clubhouse", case_sensitive=False)

    print(f"Found {len(clubhouse_messages)} messages about Clubhouse:")
    for msg in clubhouse_messages[:3]:  # Show first 3
        print(f"  [{msg['date']}] {msg['phone_number']}: {msg['body'][:100]}...")

def conversation_analysis_example():
    """Example of analyzing specific conversations."""
    print("\n=== Conversation Analysis Example ===")

    analyzer = iMessageAnalyzer(verbose=False)

    # Get all messages first to see what contacts we have
    messages = analyzer.get_all_messages(limit=100)

    if not messages:
        print("No messages found")
        return

    # Find the contact with the most messages
    message_counts = {}
    for msg in messages:
        contact = msg['phone_number']
        message_counts[contact] = message_counts.get(contact, 0) + 1

    top_contact = max(message_counts, key=message_counts.get)

    print(f"Top contact: {top_contact} with {message_counts[top_contact]} messages")

    # Get full conversation with this contact
    conversation = analyzer.get_conversation(top_contact)

    if conversation:
        # Convert to DataFrame for analysis
        df = pd.DataFrame(conversation)

        print(f"Conversation analysis for {top_contact}:")
        print(f"  Total messages: {len(df)}")
        print(f"  Messages sent: {len(df[df['is_from_me'] == 1])}")
        print(f"  Messages received: {len(df[df['is_from_me'] == 0])}")
        print(f"  First message: {df['date'].min()}")
        print(f"  Last message: {df['date'].max()}")

def statistics_example():
    """Example of generating detailed statistics."""
    print("\n=== Statistics Example ===")

    analyzer = iMessageAnalyzer(verbose=False)

    # Get messages and create statistics
    messages = analyzer.get_all_messages()
    stats = analyzer.create_summary_stats(messages)

    print(f"Message Statistics:")
    print(f"  Total messages: {stats['total_messages']:,}")
    print(f"  Messages sent: {stats['messages_sent']:,}")
    print(f"  Messages received: {stats['messages_received']:,}")
    print(f"  Unique contacts: {stats['unique_contacts']:,}")
    print(f"  Average message length: {stats['message_length_stats']['mean']:.1f} characters")

    print(f"\nTime-based patterns:")
    print(f"  Most active year: {max(stats['messages_by_year'], key=stats['messages_by_year'].get)}")
    print(f"  Most active hour: {max(stats['messages_by_hour'], key=stats['messages_by_hour'].get)}:00")
    print(f"  Most active day of week: {max(stats['messages_by_day_of_week'], key=stats['messages_by_day_of_week'].get)}")

def custom_analysis_example():
    """Example of custom analysis using the raw data."""
    print("\n=== Custom Analysis Example ===")

    analyzer = iMessageAnalyzer(verbose=False)

    # Get all messages
    messages = analyzer.get_all_messages()
    df = pd.DataFrame(messages)

    if df.empty:
        print("No messages to analyze")
        return

    # Custom analysis: Find conversations with emoji
    emoji_pattern = r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002600-\U000026FF\U00002700-\U000027BF]'

    import re
    emoji_messages = df[df['body'].astype(str).str.contains(emoji_pattern, regex=True, na=False)]

    print(f"Emoji usage:")
    print(f"  Messages with emoji: {len(emoji_messages)} ({len(emoji_messages)/len(df)*100:.1f}%)")

    if not emoji_messages.empty:
        # Find who uses emoji most
        emoji_by_contact = emoji_messages['phone_number'].value_counts()
        print(f"  Top emoji user: {emoji_by_contact.index[0]} ({emoji_by_contact.iloc[0]} messages)")

def attachments_example():
    """Example of analyzing attachments."""
    print("\n=== Attachments Example ===")

    analyzer = iMessageAnalyzer(verbose=False)

    # Get attachments data
    attachments = analyzer.get_attachments()

    if attachments.empty:
        print("No attachments found")
        return

    print(f"Attachment analysis:")
    print(f"  Total attachments: {len(attachments)}")

    # Group by MIME type
    if 'mime_type' in attachments.columns:
        mime_counts = attachments['mime_type'].value_counts()
        print(f"  File types:")
        for mime_type, count in mime_counts.head(5).items():
            print(f"    {mime_type}: {count}")

def save_custom_report():
    """Example of creating a custom report."""
    print("\n=== Custom Report Example ===")

    analyzer = iMessageAnalyzer(verbose=False)

    # Get data
    messages = analyzer.get_all_messages()
    stats = analyzer.create_summary_stats(messages)

    # Create custom report
    report = {
        'generated_at': pd.Timestamp.now().isoformat(),
        'summary': {
            'total_messages': stats['total_messages'],
            'unique_contacts': stats['unique_contacts'],
            'date_span_days': stats['date_range']['days_span']
        },
        'top_contacts': dict(list(stats['messages_by_contact'].items())[:5]),
        'activity_by_hour': stats['messages_by_hour']
    }

    # Save to file
    output_file = Path.home() / "Desktop" / "imessage_custom_report.json"
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)

    print(f"Custom report saved to: {output_file}")

def main():
    """Run all examples."""
    print("iMessage Analyzer - Usage Examples")
    print("=" * 50)

    try:
        basic_usage_example()
        search_example()
        conversation_analysis_example()
        statistics_example()
        custom_analysis_example()
        attachments_example()
        save_custom_report()

        print("\n" + "=" * 50)
        print("All examples completed successfully!")
        print("Check your Desktop for exported files.")

    except Exception as e:
        print(f"Error running examples: {e}")

if __name__ == "__main__":
    main()
