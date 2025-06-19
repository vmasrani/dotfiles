from imessage_tools import read_messages, print_messages, get_chat_mapping
from pathlib import Path
import json

def test_imessage_tools():
    # Path to the chat.db file
    db_path = Path.home() / "Library" / "Messages" / "chat.db"
    print(f"Testing with database: {db_path}")

    # Test reading messages
    print("\n=== Testing read_messages ===")
    messages = read_messages(str(db_path), n=5, self_number="Me", human_readable_date=True)

    print(f"Number of messages returned: {len(messages)}")

    if messages:
        print("\nFirst message structure:")
        first_message = messages[0]
        print(json.dumps(first_message, indent=2, default=str))

        print("\nAll message keys:")
        print(list(first_message.keys()))

    # Test chat mapping
    print("\n=== Testing get_chat_mapping ===")
    chat_mapping = get_chat_mapping(str(db_path))
    print(f"Chat mapping type: {type(chat_mapping)}")
    print(f"Number of chat mappings: {len(chat_mapping) if hasattr(chat_mapping, '__len__') else 'N/A'}")

    if chat_mapping:
        print("Sample chat mappings:")
        for i, (key, value) in enumerate(list(chat_mapping.items())[:3]):
            print(f"  {key}: {value}")

    # Test print_messages function
    print("\n=== Testing print_messages ===")
    print("Output from print_messages function:")
    print_messages(messages[:2])  # Just print first 2 messages

    return messages, chat_mapping

if __name__ == "__main__":
    messages, chat_mapping = test_imessage_tools()
