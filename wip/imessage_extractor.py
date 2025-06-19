import pandas as pd
from pathlib import Path
from datetime import datetime
import sqlite3
from imessage_tools import read_messages, get_chat_mapping
import json

class iMessageExtractor:
    def __init__(self, db_path=None):
        """Initialize the iMessage extractor with optional database path."""
        if db_path is None:
            self.db_path = Path.home() / "Library" / "Messages" / "chat.db"
        else:
            self.db_path = Path(db_path)

        print(f"Using database: {self.db_path}")

        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found at {self.db_path}")

    def get_all_messages(self, limit=None):
        """Extract all messages using the imessage_tools library."""
        print("Extracting messages using imessage_tools...")

        # Get all messages (set limit to None for all messages)
        messages = read_messages(
            str(self.db_path),
            n=limit,
            self_number="Me",
            human_readable_date=True
        )

        print(f"Extracted {len(messages)} messages")
        return messages

    def get_contacts(self):
        """Extract contact information from the handle table."""
        print("Extracting contacts...")

        conn = sqlite3.connect(f'file:{self.db_path}?mode=ro', uri=True)

        query = """
        SELECT ROWID, id, country, service, person_centric_id
        FROM handle
        ORDER BY ROWID
        """

        contacts_df = pd.read_sql_query(query, conn)
        conn.close()

        print(f"Found {len(contacts_df)} contacts")
        return contacts_df

    def get_chat_threads(self):
        """Extract chat thread information."""
        print("Extracting chat threads...")

        conn = sqlite3.connect(f'file:{self.db_path}?mode=ro', uri=True)

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

        chats_df = pd.read_sql_query(query, conn)
        conn.close()

        # Convert timestamp to readable format
        def convert_timestamp(ts):
            if pd.isna(ts) or ts == 0:
                return None
            epoch_offset = 978307200  # Seconds between 1970-01-01 and 2001-01-01
            seconds = ts / 1000000000 + epoch_offset
            return datetime.fromtimestamp(seconds)

        chats_df['last_read_message_datetime'] = chats_df['last_read_message_timestamp'].apply(convert_timestamp)

        print(f"Found {len(chats_df)} chat threads")
        return chats_df

    def get_attachments(self):
        """Extract attachment information."""
        print("Extracting attachments...")

        conn = sqlite3.connect(f'file:{self.db_path}?mode=ro', uri=True)

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

        attachments_df = pd.read_sql_query(query, conn)
        conn.close()

        # Convert timestamp
        def convert_timestamp(ts):
            if pd.isna(ts) or ts == 0:
                return None
            epoch_offset = 978307200
            seconds = ts / 1000000000 + epoch_offset
            return datetime.fromtimestamp(seconds)

        attachments_df['created_datetime'] = attachments_df['created_date'].apply(convert_timestamp)

        print(f"Found {len(attachments_df)} attachments")
        return attachments_df

    def organize_messages_by_chat(self, messages):
        """Organize messages by chat/conversation."""
        print("Organizing messages by chat...")

        # Convert to DataFrame for easier manipulation
        messages_df = pd.DataFrame(messages)

        # Group by phone_number/chat identifier
        chats = {}
        for phone_number, group in messages_df.groupby('phone_number'):
            chats[phone_number] = {
                'contact': phone_number,
                'message_count': len(group),
                'messages': group.to_dict('records'),
                'first_message_date': group['date'].min(),
                'last_message_date': group['date'].max()
            }

        print(f"Organized into {len(chats)} conversations")
        return chats

    def create_summary_stats(self, messages):
        """Create summary statistics about the messages."""
        print("Creating summary statistics...")

        df = pd.DataFrame(messages)

        # Convert date strings to datetime for analysis
        df['date_parsed'] = pd.to_datetime(df['date'])

        stats = {
            'total_messages': len(df),
            'messages_sent': len(df[df['is_from_me'] == 1]),
            'messages_received': len(df[df['is_from_me'] == 0]),
            'unique_contacts': df['phone_number'].nunique(),
            'date_range': {
                'earliest': df['date_parsed'].min().isoformat() if not df.empty else None,
                'latest': df['date_parsed'].max().isoformat() if not df.empty else None
            },
            'messages_by_contact': df['phone_number'].value_counts().to_dict(),
            'messages_by_year': df['date_parsed'].dt.year.value_counts().sort_index().to_dict(),
            'group_chats': len(df[df['group_chat_name'] != ""])
        }

        return stats

    def export_to_csv(self, output_dir="imessage_export"):
        """Export all data to CSV files."""
        output_path = Path.home() / "Desktop" / output_dir
        output_path.mkdir(exist_ok=True)

        print(f"Exporting data to {output_path}")

        # Get all data
        messages = self.get_all_messages()
        contacts = self.get_contacts()
        chats = self.get_chat_threads()
        attachments = self.get_attachments()

        # Convert messages to DataFrame
        messages_df = pd.DataFrame(messages)

        # Save CSV files
        messages_df.to_csv(output_path / "messages.csv", index=False)
        contacts.to_csv(output_path / "contacts.csv", index=False)
        chats.to_csv(output_path / "chat_threads.csv", index=False)
        attachments.to_csv(output_path / "attachments.csv", index=False)

        # Save organized conversations
        conversations = self.organize_messages_by_chat(messages)
        conversations_dir = output_path / "conversations"
        conversations_dir.mkdir(exist_ok=True)

        for contact, data in conversations.items():
            safe_filename = "".join(c if c.isalnum() or c in ".-_@" else "_" for c in contact)
            convo_df = pd.DataFrame(data['messages'])
            convo_df.to_csv(conversations_dir / f"{safe_filename}.csv", index=False)

        # Save summary statistics
        stats = self.create_summary_stats(messages)
        with open(output_path / "summary_stats.json", 'w') as f:
            json.dump(stats, f, indent=2, default=str)

        print(f"Exported {len(messages)} messages to CSV files")
        print(f"Created {len(conversations)} individual conversation files")

        return {
            'messages': messages_df,
            'contacts': contacts,
            'chats': chats,
            'attachments': attachments,
            'conversations': conversations,
            'stats': stats,
            'output_path': output_path
        }

    def get_conversation(self, contact_identifier, limit=None):
        """Get messages for a specific contact or chat."""
        messages = self.get_all_messages()

        # Filter messages for the specific contact
        conversation = [
            msg for msg in messages
            if msg['phone_number'] == contact_identifier or msg['group_chat_name'] == contact_identifier
        ]

        if limit:
            conversation = conversation[:limit]

        return conversation

    def search_messages(self, search_term, case_sensitive=False):
        """Search for messages containing a specific term."""
        messages = self.get_all_messages()

        if not case_sensitive:
            search_term = search_term.lower()

        results = []
        for msg in messages:
            text = msg.get('body', '')
            if not case_sensitive:
                text = text.lower()

            if search_term in text:
                results.append(msg)

        return results

def main():
    """Main function to demonstrate usage."""
    try:
        # Initialize extractor
        extractor = iMessageExtractor()

        # Export all data
        data = extractor.export_to_csv()

        # Print summary
        print(f"\n=== EXPORT SUMMARY ===")
        print(f"Total messages: {data['stats']['total_messages']:,}")
        print(f"Messages sent: {data['stats']['messages_sent']:,}")
        print(f"Messages received: {data['stats']['messages_received']:,}")
        print(f"Unique contacts: {data['stats']['unique_contacts']:,}")
        print(f"Group chats: {data['stats']['group_chats']:,}")
        print(f"Date range: {data['stats']['date_range']['earliest']} to {data['stats']['date_range']['latest']}")
        print(f"\nFiles saved to: {data['output_path']}")

        # Show top contacts
        print(f"\n=== TOP CONTACTS ===")
        for contact, count in list(data['stats']['messages_by_contact'].items())[:10]:
            print(f"{contact}: {count:,} messages")

        return data

    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    data = main()
