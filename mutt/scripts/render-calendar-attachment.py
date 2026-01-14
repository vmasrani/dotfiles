#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["vobject"]
# ///
"""Render calendar attachment (ICS file) in a pretty format."""

import sys
import warnings

import vobject


def smart_truncate(content, length=100, suffix='...'):
    if len(content) <= length:
        return content
    return ' '.join(content[:length+1].split(' ')[0:-1]) + suffix


def get_invitation_from_path(path):
    with open(path) as f:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return vobject.readOne(f, ignoreUnreadable=True)


def person_string(c):
    cn = c.params.get('CN', ['Unknown'])[0]
    email = c.value.split(':')[1] if ':' in c.value else c.value
    return f"{cn} <{email}>"


def when_str_of_start_end(s, e):
    date_format = "%a, %d %b %Y at %H:%M"
    until_format = "%H:%M" if s.date() == e.date() else date_format
    return f"{s.strftime(date_format)} -- {e.strftime(until_format)}"


def pretty_print_invitation(invitation):
    event = invitation.vevent.contents

    if invitation.method.value == 'REPLY':
        print(event['summary'][0].value)
        return

    CONTENT_WIDTH = 70
    title = event['summary'][0].value
    org = event.get('organizer', [None])[0]
    invitees = event.get('attendee', [])
    start = event['dtstart'][0].value
    end = event['dtend'][0].value
    location = event.get('location', [None])[0]
    location_val = location.value if location else None
    description = event.get('description', [None])[0]
    description_val = description.value if description else None

    print()
    print("\033[48m", " " * CONTENT_WIDTH, "\033[0m")
    print("\033[48;1;37m", "Event Invitation".center(CONTENT_WIDTH), "\033[0m")
    print("\033[48;37m", smart_truncate(title.strip(), 68).center(CONTENT_WIDTH), "\033[0m")
    print("\033[48m", " " * CONTENT_WIDTH, "\033[0m")
    print()
    print(f"Date/Time:   {when_str_of_start_end(start, end)}")

    if location_val:
        print(f"Location:    {location_val}")
    elif description_val and 'Microsoft Teams meeting' in description_val:
        print("Location:    Microsoft Teams meeting")
    else:
        print("Location:    <None>")

    if org:
        print(f"Organiser:   {person_string(org)}")

    if description_val:
        print(f"\n{description_val}\n")

    if invitees:
        print("Invitees:")
        for i in invitees:
            if i:
                print(f"  {person_string(i)}")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1].startswith('-'):
        sys.stderr.write(f"Usage: {sys.argv[0]} <filename.ics>\n")
        sys.exit(2)

    inv = get_invitation_from_path(sys.argv[1])
    pretty_print_invitation(inv)
