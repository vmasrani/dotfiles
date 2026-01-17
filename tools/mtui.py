#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "textual>=0.47.0",
#     "pydantic>=2.0",
#     "loguru>=0.7.0",
# ]
# ///
"""mtui - Gmail TUI using Textual.

A lazygit-style terminal interface for Gmail.
Uses msearch, mview, mget, msend shell tools for email operations.
"""

import json
import subprocess
import time
from pathlib import Path

from loguru import logger
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Collapsible,
    DataTable,
    Footer,
    Header,
    Input,
    Markdown,
    Static,
    TabbedContent,
    TabPane,
    Tree,
)
from textual.widgets.tree import TreeNode

from mtui_models import (
    AttachmentList,
    EmailMessage,
    EmailThread,
    SearchResult,
)

# Configure logging
LOG_FILE = Path("/tmp/mtui.log")
logger.add(LOG_FILE, rotation="1 MB", retention="3 days", level="DEBUG")

TOOLS_DIR = Path(__file__).parent


class EmailTree(Tree):
    """Tree widget for displaying email threads with expandable messages."""

    def __init__(self, **kwargs):
        super().__init__("Emails", **kwargs)
        self.threads: dict[str, EmailThread] = {}
        self.selected_threads: set[str] = set()  # For bulk operations

    def populate(self, search_result: SearchResult) -> None:
        """Populate tree with search results."""
        self.clear()
        self.threads.clear()
        self.selected_threads.clear()

        for thread in search_result.threads:
            self.threads[thread.thread_id] = thread
            label = self._format_thread_label(thread)
            node = self.root.add(label, data=thread)

            if thread.total_messages > 1:
                node.allow_expand = True

    def _format_thread_label(self, thread: EmailThread, selected: bool = False) -> str:
        """Format a thread for display with visual indicators."""
        date = thread.date_relative[:12].ljust(12)
        author = thread.authors[:20].ljust(20)
        flags = thread.flags_display.ljust(3)
        subject = thread.subject[:45]

        # Selection indicator
        sel = "[x]" if selected else "[ ]" if self.selected_threads else ""
        if sel:
            sel = f"{sel} "

        label = f"{sel}{date} {author} {flags} {subject}"

        # Visual styling based on state
        if thread.is_unread:
            label = f"[bold $gum-yellow]{label}[/]"
        if selected:
            label = f"[reverse]{label}[/]"

        return label

    def toggle_selection(self, thread_id: str) -> None:
        """Toggle selection state of a thread."""
        if thread_id in self.selected_threads:
            self.selected_threads.discard(thread_id)
        else:
            self.selected_threads.add(thread_id)

    def select_all(self) -> None:
        """Select all visible threads."""
        self.selected_threads = set(self.threads.keys())

    def clear_selection(self) -> None:
        """Clear all selections."""
        self.selected_threads.clear()

    def refresh_node(self, thread_id: str) -> None:
        """Refresh display of a single node."""
        for node in self.root.children:
            if isinstance(node.data, EmailThread) and node.data.thread_id == thread_id:
                thread = self.threads.get(thread_id)
                if thread:
                    selected = thread_id in self.selected_threads
                    node.set_label(self._format_thread_label(thread, selected))
                break


class PreviewPanel(VerticalScroll):
    """Right panel for email preview."""

    def compose(self) -> ComposeResult:
        yield Static(id="preview-headers")
        yield Markdown(id="preview-body")
        with Collapsible(title="Attachments (0)", collapsed=True, id="attachment-panel"):
            yield DataTable(id="attachment-table")


class StatusBar(Static):
    """Status bar showing sync status and counts."""

    def __init__(self, **kwargs):
        super().__init__("", **kwargs)
        self.last_sync: float = 0
        self.is_syncing: bool = False
        self.error_count: int = 0
        self.loaded_count: int = 0
        self.total_count: int = 0
        self.selected_count: int = 0

    def update_status(
        self,
        loaded: int | None = None,
        total: int | None = None,
        selected: int | None = None,
        syncing: bool | None = None,
        error: bool = False,
    ) -> None:
        if loaded is not None:
            self.loaded_count = loaded
        if total is not None:
            self.total_count = total
        if selected is not None:
            self.selected_count = selected
        if syncing is not None:
            self.is_syncing = syncing
            if not syncing:
                self.last_sync = time.time()
        if error:
            self.error_count += 1

        self._render_status()

    def _render_status(self) -> None:
        parts = []

        # Sync status
        if self.is_syncing:
            parts.append("[yellow]↻ Syncing...[/]")
        elif self.last_sync:
            elapsed = int(time.time() - self.last_sync)
            if elapsed < 60:
                parts.append(f"[green]● Synced {elapsed}s ago[/]")
            else:
                mins = elapsed // 60
                parts.append(f"[dim]● Synced {mins}m ago[/]")

        # Counts
        if self.total_count:
            parts.append(f"{self.loaded_count}/{self.total_count} emails")

        # Selection
        if self.selected_count:
            parts.append(f"[cyan]{self.selected_count} selected[/]")

        # Errors
        if self.error_count:
            parts.append(f"[red]{self.error_count} errors[/]")

        self.update(" │ ".join(parts))


class GmailTUI(App):
    """Gmail TUI Application."""

    TITLE = "mtui"
    CSS_PATH = "mtui_styles.tcss"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("g", "go_top", "Top", show=False),
        Binding("G", "go_bottom", "Bottom", show=False),
        Binding("enter", "select_email", "View"),
        Binding("tab", "toggle_expand", "Expand"),
        Binding("r", "reply", "Reply"),
        Binding("f", "forward", "Forward"),
        Binding("c", "compose", "Compose"),
        Binding("d", "delete", "Delete"),
        Binding("a", "archive", "Archive"),
        Binding("s", "toggle_star", "Star"),
        Binding("m", "toggle_read", "Read"),
        Binding("t", "manage_tags", "Tags"),
        Binding("x", "toggle_select", "Select"),
        Binding("X", "select_all", "All", show=False),
        Binding("escape", "clear_selection", "Clear", show=False),
        Binding("n", "next_unread", "Next", show=False),
        Binding("N", "prev_unread", "Prev", show=False),
        Binding("D", "download", "Download"),
        Binding("slash", "focus_search", "Search"),
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("1", "tab_inbox", "Inbox", show=False),
        Binding("2", "tab_sent", "Sent", show=False),
        Binding("3", "tab_drafts", "Drafts", show=False),
        Binding("4", "tab_search", "Search", show=False),
        Binding("question_mark", "show_help", "Help"),
        Binding("E", "show_errors", "Errors", show=False),
        Binding("up", "search_history_prev", show=False),
        Binding("down", "search_history_next", show=False),
    ]

    SYNC_INTERVAL = 120  # Increased from 60s for less aggressive syncing

    PAGE_SIZE = 25

    def __init__(self):
        super().__init__()
        self.current_query = "tag:inbox"
        self.current_email: EmailMessage | None = None
        self.selected_thread_id: str | None = None
        self.current_offset = 0
        self.total_count = 0

        # Preview cache for performance
        self.preview_cache: dict[str, EmailMessage] = {}
        self.cache_max_size = 50

        # Search history
        self.search_history: list[str] = []
        self.search_history_index = -1
        self.max_search_history = 50

        # Error log
        self.recent_errors: list[str] = []
        self.max_errors = 20

        # Cursor position preservation
        self.saved_cursor_thread_id: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            with TabbedContent(initial="inbox", id="folder-tabs"):
                with TabPane("Inbox", id="inbox"):
                    yield Static("", classes="tab-placeholder")
                with TabPane("Sent", id="sent"):
                    yield Static("", classes="tab-placeholder")
                with TabPane("Drafts", id="drafts"):
                    yield Static("", classes="tab-placeholder")
                with TabPane("Search", id="search"):
                    yield Input(
                        placeholder="from:sender subject:topic tag:unread",
                        id="search-input",
                    )
            with Horizontal(classes="mail-view"):
                with Vertical(classes="list-panel"):
                    yield EmailTree(id="email-tree")
                    yield StatusBar(id="status-bar")
                with Vertical(classes="preview-panel", id="preview-container"):
                    yield PreviewPanel()
        yield Footer()

    def on_mount(self) -> None:
        """Initialize app on mount."""
        for table in self.query(DataTable):
            if table.id == "attachment-table":
                table.add_columns("Filename", "Size", "Type")
                table.cursor_type = "row"

        self.load_emails("tag:inbox")
        self.set_interval(self.SYNC_INTERVAL, self._periodic_sync)
        logger.info("mtui started")

    def _log_error(self, message: str, exc: Exception | None = None) -> None:
        """Log error and store for display."""
        timestamp = time.strftime("%H:%M:%S")
        error_entry = f"[{timestamp}] {message}"
        if exc:
            error_entry += f": {exc}"
            logger.exception(message)
        else:
            logger.error(message)

        self.recent_errors.append(error_entry)
        if len(self.recent_errors) > self.max_errors:
            self.recent_errors.pop(0)

        try:
            status = self.query_one("#status-bar", StatusBar)
            status.update_status(error=True)
        except Exception:
            pass

    def _update_status(self, **kwargs) -> None:
        """Update status bar."""
        try:
            status = self.query_one("#status-bar", StatusBar)
            status.update_status(**kwargs)
        except Exception:
            pass

    @work(exclusive=True, thread=True)
    def load_emails(self, query: str, limit: int | None = None) -> None:
        """Background worker to fetch email list."""
        self.current_query = query
        self.current_offset = 0
        limit = limit or self.PAGE_SIZE

        # Add to search history if it's a custom search
        if query not in ["tag:inbox", "tag:sent", "tag:draft"]:
            if query not in self.search_history:
                self.search_history.append(query)
                if len(self.search_history) > self.max_search_history:
                    self.search_history.pop(0)
            self.search_history_index = -1

        result = subprocess.run(
            [
                str(TOOLS_DIR / "msearch"),
                query,
                "--output",
                "json-full",
                "-n",
                str(limit),
                "--offset",
                "0",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0 and result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                search_result = SearchResult.model_validate(data)
                self.total_count = search_result.total_count
                self.call_from_thread(self._populate_tree, search_result, False)
                self.call_from_thread(
                    self._update_status,
                    loaded=len(search_result.threads),
                    total=search_result.total_count,
                )
            except json.JSONDecodeError as e:
                self._log_error("Failed to parse search results", e)
                self.call_from_thread(self._show_error, "Failed to parse search results")
        elif result.returncode != 0:
            self._log_error(f"msearch failed: {result.stderr or 'Unknown error'}")

    @work(exclusive=True, thread=True)
    def load_email_preview(self, thread_id: str) -> None:
        """Background worker to fetch email content."""
        self.selected_thread_id = thread_id

        # Check cache first
        if thread_id in self.preview_cache:
            logger.debug(f"Cache hit for thread {thread_id}")
            self.call_from_thread(self._display_preview, self.preview_cache[thread_id])
            return

        # Get first message ID from thread
        result = subprocess.run(
            ["notmuch", "search", "--output=messages", f"thread:{thread_id}"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0 or not result.stdout.strip():
            self._log_error(f"Failed to get messages for thread {thread_id}")
            return

        msg_id = result.stdout.strip().split("\n")[0]
        msg_id = msg_id.replace("id:", "")

        # Fetch email content
        result = subprocess.run(
            [str(TOOLS_DIR / "mview"), f"id:{msg_id}", "--json"],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0 and result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                email = EmailMessage.model_validate(data)

                # Add to cache
                self.preview_cache[thread_id] = email
                if len(self.preview_cache) > self.cache_max_size:
                    oldest = next(iter(self.preview_cache))
                    del self.preview_cache[oldest]

                self.call_from_thread(self._display_preview, email)
            except json.JSONDecodeError as e:
                self._log_error(f"Failed to parse email {msg_id}", e)
        elif result.returncode != 0:
            self._log_error(f"mview failed: {result.stderr or 'Unknown error'}")

    def _populate_tree(self, search_result: SearchResult, append: bool = False) -> None:
        """Update tree with search results."""
        tree = self.query_one("#email-tree", EmailTree)

        if append:
            self._remove_load_more_node(tree)
            for thread in search_result.threads:
                tree.threads[thread.thread_id] = thread
                label = tree._format_thread_label(thread)
                node = tree.root.add(label, data=thread)
                if thread.total_messages > 1:
                    node.allow_expand = True
        else:
            tree.populate(search_result)
            tree.root.expand()
            if search_result.threads:
                tree.select_node(tree.root.children[0])
                self.load_email_preview(search_result.threads[0].thread_id)

        loaded_count = self.current_offset + len(search_result.threads)

        if loaded_count < self.total_count:
            remaining = self.total_count - loaded_count
            tree.root.add(
                f"[dim]── Load more ({remaining} remaining) ──[/dim]",
                data={"action": "load_more"},
            )

        self._update_status(loaded=loaded_count, selected=len(tree.selected_threads))

    def _remove_load_more_node(self, tree: EmailTree) -> None:
        """Remove the 'Load More' sentinel node if it exists."""
        for node in tree.root.children:
            if isinstance(node.data, dict) and node.data.get("action") == "load_more":
                node.remove()
                break

    @work(exclusive=True, thread=True)
    def _load_more_emails(self) -> None:
        """Load the next page of emails."""
        self.current_offset += self.PAGE_SIZE

        result = subprocess.run(
            [
                str(TOOLS_DIR / "msearch"),
                self.current_query,
                "--output",
                "json-full",
                "-n",
                str(self.PAGE_SIZE),
                "--offset",
                str(self.current_offset),
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0 and result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                search_result = SearchResult.model_validate(data)
                self.call_from_thread(self._populate_tree, search_result, True)
            except json.JSONDecodeError as e:
                self._log_error("Failed to load more emails", e)
                self.call_from_thread(self._show_error, "Failed to load more emails")

    def _display_preview(self, email: EmailMessage) -> None:
        """Update preview panel with email content."""
        self.current_email = email

        # Extract display name from email address
        from_display = email.headers.from_ or "Unknown"
        if "<" in from_display:
            name_part = from_display.split("<")[0].strip()
            if name_part:
                from_display = f"{name_part} ({from_display.split('<')[1].rstrip('>')})"

        headers = self.query_one("#preview-headers", Static)
        header_lines = [
            f"[bold magenta]Subject:[/] {email.headers.subject or '(no subject)'}",
            f"[bold cyan]From:[/] {from_display}",
            f"[bold]To:[/] {email.headers.to or 'Unknown'}",
            f"[bold]Date:[/] {email.headers.date or 'Unknown'}",
        ]
        if email.headers.cc:
            header_lines.append(f"[bold]CC:[/] {email.headers.cc}")

        # Show tags
        if email.tags:
            tags_display = " ".join(f"[{t}]" for t in email.tags if t not in ["inbox", "sent"])
            if tags_display:
                header_lines.append(f"[bold yellow]Tags:[/] {tags_display}")

        headers.update("\n".join(header_lines))

        body = self.query_one("#preview-body", Markdown)
        body.update(email.display_body)

        collapsible = self.query_one("#attachment-panel", Collapsible)
        table = self.query_one("#attachment-table", DataTable)
        table.clear()

        if email.attachments:
            collapsible.title = f"Attachments ({len(email.attachments)})"
            collapsible.collapsed = False
            for att in email.attachments:
                table.add_row(
                    att.filename,
                    att.size_display,
                    att.content_type,
                    key=f"{att.message_id}:{att.part_id}",
                )
        else:
            collapsible.title = "Attachments (0)"
            collapsible.collapsed = True

    def _show_error(self, message: str) -> None:
        """Show error in status."""
        self.notify(message, severity="error")

    def _save_cursor_position(self) -> None:
        """Save current cursor position for restoration."""
        tree = self.query_one("#email-tree", EmailTree)
        if tree.cursor_node and isinstance(tree.cursor_node.data, EmailThread):
            self.saved_cursor_thread_id = tree.cursor_node.data.thread_id

    def _restore_cursor_position(self) -> None:
        """Restore cursor to saved position."""
        if not self.saved_cursor_thread_id:
            return

        tree = self.query_one("#email-tree", EmailTree)
        for node in tree.root.children:
            if isinstance(node.data, EmailThread) and node.data.thread_id == self.saved_cursor_thread_id:
                tree.select_node(node)
                break

        self.saved_cursor_thread_id = None

    @work(thread=True)
    def _periodic_sync(self) -> None:
        """Periodically sync mail."""
        self.call_from_thread(self._update_status, syncing=True)

        # Run mbsync
        result = subprocess.run(["mbsync", "-a"], capture_output=True, text=True)
        if result.returncode != 0:
            self._log_error(f"mbsync failed: {result.stderr or 'Unknown error'}")

        # Refresh notmuch
        result = subprocess.run(["notmuch", "new"], capture_output=True, text=True)
        if result.returncode != 0:
            self._log_error(f"notmuch new failed: {result.stderr or 'Unknown error'}")

        self.call_from_thread(self._update_status, syncing=False)
        self.call_from_thread(self._save_cursor_position)
        self.call_from_thread(self._refresh_current_view)
        self.call_from_thread(self._restore_cursor_position)

    def _refresh_current_view(self) -> None:
        """Refresh the current tab's email list."""
        # Invalidate cache on refresh
        self.preview_cache.clear()
        self.load_emails(self.current_query)

    # Tree selection handler
    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle tree node selection."""
        data = event.node.data
        if isinstance(data, dict) and data.get("action") == "load_more":
            self._load_more_emails()
            return
        if data and isinstance(data, EmailThread):
            self.load_email_preview(data.thread_id)

    # Input handlers
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle search submission."""
        if event.input.id == "search-input":
            query = event.value.strip()
            if query:
                self.load_emails(query)
                self.query_one(TabbedContent).active = "search"

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes for search history."""
        pass  # Placeholder for future autocomplete

    # Tab change handler
    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """Handle tab changes."""
        if event.tabbed_content.id != "folder-tabs":
            return
        tab_queries = {
            "inbox": "tag:inbox",
            "sent": "tag:sent",
            "drafts": "tag:draft",
        }
        if event.pane.id in tab_queries:
            self.load_emails(tab_queries[event.pane.id])

    # Navigation actions
    def action_cursor_down(self) -> None:
        tree = self.query_one("#email-tree", EmailTree)
        tree.action_cursor_down()

    def action_cursor_up(self) -> None:
        tree = self.query_one("#email-tree", EmailTree)
        tree.action_cursor_up()

    def action_go_top(self) -> None:
        tree = self.query_one("#email-tree", EmailTree)
        if tree.root.children:
            tree.select_node(tree.root.children[0])

    def action_go_bottom(self) -> None:
        tree = self.query_one("#email-tree", EmailTree)
        if tree.root.children:
            tree.select_node(tree.root.children[-1])

    def action_select_email(self) -> None:
        tree = self.query_one("#email-tree", EmailTree)
        if tree.cursor_node and tree.cursor_node.data:
            thread = tree.cursor_node.data
            if isinstance(thread, EmailThread):
                self.load_email_preview(thread.thread_id)

    def action_toggle_expand(self) -> None:
        tree = self.query_one("#email-tree", EmailTree)
        if tree.cursor_node:
            tree.cursor_node.toggle()

    def action_next_unread(self) -> None:
        """Jump to next unread email."""
        tree = self.query_one("#email-tree", EmailTree)
        current_found = False
        for node in tree.root.children:
            if node == tree.cursor_node:
                current_found = True
                continue
            if current_found and isinstance(node.data, EmailThread) and node.data.is_unread:
                tree.select_node(node)
                self.load_email_preview(node.data.thread_id)
                return
        self.notify("No more unread emails", severity="warning")

    def action_prev_unread(self) -> None:
        """Jump to previous unread email."""
        tree = self.query_one("#email-tree", EmailTree)
        nodes = list(tree.root.children)
        current_idx = None
        for i, node in enumerate(nodes):
            if node == tree.cursor_node:
                current_idx = i
                break

        if current_idx is None:
            return

        for i in range(current_idx - 1, -1, -1):
            node = nodes[i]
            if isinstance(node.data, EmailThread) and node.data.is_unread:
                tree.select_node(node)
                self.load_email_preview(node.data.thread_id)
                return
        self.notify("No previous unread emails", severity="warning")

    # Selection actions
    def action_toggle_select(self) -> None:
        """Toggle selection of current email."""
        tree = self.query_one("#email-tree", EmailTree)
        if tree.cursor_node and isinstance(tree.cursor_node.data, EmailThread):
            thread_id = tree.cursor_node.data.thread_id
            tree.toggle_selection(thread_id)
            tree.refresh_node(thread_id)
            self._update_status(selected=len(tree.selected_threads))
            tree.action_cursor_down()

    def action_select_all(self) -> None:
        """Select all visible emails."""
        tree = self.query_one("#email-tree", EmailTree)
        tree.select_all()
        # Refresh all nodes
        for node in tree.root.children:
            if isinstance(node.data, EmailThread):
                node.set_label(tree._format_thread_label(node.data, True))
        self._update_status(selected=len(tree.selected_threads))
        self.notify(f"Selected {len(tree.selected_threads)} emails")

    def action_clear_selection(self) -> None:
        """Clear all selections."""
        tree = self.query_one("#email-tree", EmailTree)
        tree.clear_selection()
        # Refresh all nodes
        for node in tree.root.children:
            if isinstance(node.data, EmailThread):
                node.set_label(tree._format_thread_label(node.data, False))
        self._update_status(selected=0)

    # Email actions
    def action_reply(self) -> None:
        if self.current_email and self.current_email.message_id:
            subprocess.Popen(
                [
                    "neomutt",
                    "-f",
                    f"notmuch://?query=id:{self.current_email.message_id}",
                    "-e",
                    "push <reply>",
                ]
            )

    def action_forward(self) -> None:
        if self.current_email and self.current_email.message_id:
            subprocess.Popen(
                [
                    "neomutt",
                    "-f",
                    f"notmuch://?query=id:{self.current_email.message_id}",
                    "-e",
                    "push <forward>",
                ]
            )

    def action_compose(self) -> None:
        subprocess.Popen([str(TOOLS_DIR / "msend")])

    def _get_target_threads(self) -> list[str]:
        """Get thread IDs to act on (selected or current)."""
        tree = self.query_one("#email-tree", EmailTree)
        if tree.selected_threads:
            return list(tree.selected_threads)
        elif self.selected_thread_id:
            return [self.selected_thread_id]
        return []

    def action_delete(self) -> None:
        """Delete/trash selected email(s)."""
        targets = self._get_target_threads()
        if not targets:
            return

        self._save_cursor_position()

        for thread_id in targets:
            subprocess.run(
                ["notmuch", "tag", "+deleted", "-inbox", f"thread:{thread_id}"],
                capture_output=True,
            )
            # Invalidate cache
            self.preview_cache.pop(thread_id, None)

        count = len(targets)
        self.notify(f"Moved {count} email{'s' if count > 1 else ''} to trash")

        tree = self.query_one("#email-tree", EmailTree)
        tree.clear_selection()
        self._refresh_current_view()
        self._restore_cursor_position()

    def action_archive(self) -> None:
        """Archive selected email(s)."""
        targets = self._get_target_threads()
        if not targets:
            return

        self._save_cursor_position()

        for thread_id in targets:
            subprocess.run(
                ["notmuch", "tag", "-inbox", f"thread:{thread_id}"],
                capture_output=True,
            )
            self.preview_cache.pop(thread_id, None)

        count = len(targets)
        self.notify(f"Archived {count} email{'s' if count > 1 else ''}")

        tree = self.query_one("#email-tree", EmailTree)
        tree.clear_selection()
        self._refresh_current_view()
        self._restore_cursor_position()

    def action_toggle_star(self) -> None:
        """Toggle star/flag on selected email(s)."""
        targets = self._get_target_threads()
        if not targets:
            return

        tree = self.query_one("#email-tree", EmailTree)

        for thread_id in targets:
            thread = tree.threads.get(thread_id)
            if thread:
                tag_op = "-flagged" if thread.is_flagged else "+flagged"
                subprocess.run(
                    ["notmuch", "tag", tag_op, f"thread:{thread_id}"],
                    capture_output=True,
                )
                self.preview_cache.pop(thread_id, None)

        self._save_cursor_position()
        self._refresh_current_view()
        self._restore_cursor_position()

    def action_toggle_read(self) -> None:
        """Toggle read/unread on selected email(s)."""
        targets = self._get_target_threads()
        if not targets:
            return

        tree = self.query_one("#email-tree", EmailTree)

        for thread_id in targets:
            thread = tree.threads.get(thread_id)
            if thread:
                tag_op = "+unread" if not thread.is_unread else "-unread"
                subprocess.run(
                    ["notmuch", "tag", tag_op, f"thread:{thread_id}"],
                    capture_output=True,
                )
                self.preview_cache.pop(thread_id, None)

        count = len(targets)
        self.notify(f"Toggled read status for {count} email{'s' if count > 1 else ''}")

        self._save_cursor_position()
        self._refresh_current_view()
        self._restore_cursor_position()

    def action_manage_tags(self) -> None:
        """Add or remove tags from selected email(s)."""
        targets = self._get_target_threads()
        if not targets:
            self.notify("No email selected", severity="warning")
            return

        # For now, use a simple prompt via neomutt for tag management
        # In future, could add an inline tag editor
        if self.current_email:
            current_tags = ", ".join(self.current_email.tags)
            self.notify(f"Current tags: {current_tags}\nUse notmuch tag command to modify", timeout=5)

    def action_download(self) -> None:
        """Download selected attachment."""
        table = self.query_one("#attachment-table", DataTable)
        if table.cursor_row is not None and self.current_email:
            row_key = table.get_row_at(table.cursor_row)
            if row_key:
                key_str = str(table.get_row_key(row_key))
                if ":" in key_str:
                    msg_id, part_id = key_str.rsplit(":", 1)
                    self._download_attachment(msg_id, int(part_id))

    @work(thread=True)
    def _download_attachment(self, msg_id: str, part_id: int) -> None:
        """Download attachment in background."""
        result = subprocess.run(
            [str(TOOLS_DIR / "mget"), f"id:{msg_id}", "-o", str(Path.home() / "Downloads")],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            self.call_from_thread(self.notify, "Downloaded to ~/Downloads")
        else:
            self._log_error(f"Download failed: {result.stderr or 'Unknown error'}")
            self.call_from_thread(self.notify, "Download failed", severity="error")

    def action_focus_search(self) -> None:
        """Focus the search input."""
        self.query_one(TabbedContent).active = "search"
        search_input = self.query_one("#search-input", Input)
        search_input.focus()

    def action_search_history_prev(self) -> None:
        """Navigate to previous search in history."""
        if not self.search_history:
            return

        search_input = self.query_one("#search-input", Input)
        if not search_input.has_focus:
            return

        if self.search_history_index < len(self.search_history) - 1:
            self.search_history_index += 1
            search_input.value = self.search_history[-(self.search_history_index + 1)]

    def action_search_history_next(self) -> None:
        """Navigate to next search in history."""
        search_input = self.query_one("#search-input", Input)
        if not search_input.has_focus:
            return

        if self.search_history_index > 0:
            self.search_history_index -= 1
            search_input.value = self.search_history[-(self.search_history_index + 1)]
        elif self.search_history_index == 0:
            self.search_history_index = -1
            search_input.value = ""

    def action_refresh(self) -> None:
        """Manual refresh."""
        self.notify("Syncing...")
        self._periodic_sync()

    def action_tab_inbox(self) -> None:
        self.query_one(TabbedContent).active = "inbox"

    def action_tab_sent(self) -> None:
        self.query_one(TabbedContent).active = "sent"

    def action_tab_drafts(self) -> None:
        self.query_one(TabbedContent).active = "drafts"

    def action_tab_search(self) -> None:
        self.query_one(TabbedContent).active = "search"

    def action_show_errors(self) -> None:
        """Show recent errors."""
        if not self.recent_errors:
            self.notify("No recent errors")
            return

        error_text = "\n".join(self.recent_errors[-10:])
        self.notify(f"Recent Errors:\n{error_text}", timeout=15)

    def action_show_help(self) -> None:
        """Show help screen."""
        help_text = """[bold magenta]mtui - Gmail TUI[/]

[bold cyan]Navigation[/]
  j/k     Move up/down
  g/G     Go to top/bottom
  n/N     Next/prev unread
  Enter   View email
  Tab     Expand thread
  1-4     Switch tabs

[bold cyan]Actions[/]
  r       Reply
  f       Forward
  c       Compose
  d       Delete
  a       Archive
  s       Star/flag
  m       Mark read/unread
  t       Manage tags
  D       Download attachment

[bold cyan]Selection[/]
  x       Toggle select
  X       Select all
  Esc     Clear selection

[bold cyan]Other[/]
  /       Search
  ↑/↓     Search history
  Ctrl+R  Refresh
  E       Show errors
  q       Quit
"""
        self.notify(help_text, timeout=15)


if __name__ == "__main__":
    app = GmailTUI()
    app.run()
