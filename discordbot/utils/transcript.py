'''
MCLabs Discord Bot - Help Ticket HTML Transcript Generator

Author: Chris Hinkson @cmh02
'''

import re
import html
import datetime
from datetime import timezone
from typing import Dict, Optional, Any, List
from jinja2 import Template

from mcl_common.datatypes import HelpTicket, Message

# Gradient options for user avatars to give a premium aesthetic
AVATAR_GRADIENTS = [
	"linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)",  # Indigo
	"linear-gradient(135deg, #10b981 0%, #059669 100%)",  # Emerald
	"linear-gradient(135deg, #f59e0b 0%, #d97706 100%)",  # Amber
	"linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)",  # Blue
	"linear-gradient(135deg, #ec4899 0%, #db2777 100%)",  # Pink
	"linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)",  # Violet
	"linear-gradient(135deg, #f43f5e 0%, #e11d48 100%)",  # Rose
	"linear-gradient(135deg, #06b6d4 0%, #0891b2 100%)",  # Cyan
	"linear-gradient(135deg, #14b8a6 0%, #0d9488 100%)",  # Teal
	"linear-gradient(135deg, #a855f7 0%, #9333ea 100%)"   # Purple
]

def get_avatar_color(username: str) -> str:
	'''
	Deterministically assign a beautiful gradient based on the username.
	'''
	char_sum = sum(ord(c) for c in username)
	return AVATAR_GRADIENTS[char_sum % len(AVATAR_GRADIENTS)]

def format_markdown(content: str) -> str:
	'''
	Escape HTML and render basic Discord markdown structures into HTML tags.
	'''
	# 1. Escape HTML first to prevent code execution
	content = html.escape(content)

	# 2. Triple backtick code blocks (```python ... ```)
	content = re.sub(r'```(?:[a-zA-Z0-9]+)?\n?(.*?)\n?```', r'<pre><code>\1</code></pre>', content, flags=re.DOTALL)

	# 3. Single backtick inline code (`code`)
	content = re.sub(r'`([^`]+)`', r'<code>\1</code>', content)

	# 4. Bold (**text**)
	content = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', content)

	# 5. Italics (*text* or _text_)
	content = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', content)
	content = re.sub(r'_([^_]+)_', r'<em>\1</em>', content)

	# 6. Newlines to HTML line breaks
	content = content.replace('\n', '<br>')

	return content

def format_timestamp(ts: Optional[float]) -> str:
	'''
	Format timestamp to a readable string in UTC.
	'''
	if not ts:
		return "N/A"
	dt = datetime.datetime.fromtimestamp(ts, tz=timezone.utc)
	return dt.strftime("%Y-%m-%d %H:%M:%S UTC")

HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
	<meta charset="UTF-8">
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<title>MCLabs Help Ticket #{{ ticket.ticketId }} Transcript</title>
	<style>
		:root {
			--bg-color: #0d0f12;
			--container-bg: #15181e;
			--message-bg: #1c202a;
			--message-hover: #232835;
			--text-color: #f1f5f9;
			--text-muted: #94a3b8;
			--border: #2d3139;
			
			--bot-bg: rgba(59, 130, 246, 0.2);
			--bot-color: #60a5fa;
			--creator-bg: rgba(16, 185, 129, 0.2);
			--creator-color: #34d399;
			--staff-bg: rgba(245, 158, 11, 0.2);
			--staff-color: #fbbf24;
		}
		
		body {
			font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
			background-color: var(--bg-color);
			color: var(--text-color);
			margin: 0;
			padding: 24px;
			display: flex;
			justify-content: center;
		}
		
		.wrapper {
			width: 100%;
			max-width: 900px;
			background-color: var(--container-bg);
			border: 1px solid var(--border);
			border-radius: 16px;
			padding: 32px;
			box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
		}
		
		.header {
			border-bottom: 2px solid var(--border);
			padding-bottom: 24px;
			margin-bottom: 32px;
		}
		
		.header-title {
			font-size: 28px;
			font-weight: 800;
			margin: 0 0 16px 0;
			display: flex;
			align-items: center;
			gap: 12px;
		}
		
		.badge-status {
			font-size: 13px;
			padding: 6px 14px;
			border-radius: 9999px;
			font-weight: 700;
			text-transform: uppercase;
			letter-spacing: 0.05em;
		}
		
		.status-closed {
			background-color: rgba(239, 68, 68, 0.2);
			color: #f87171;
			border: 1px solid rgba(239, 68, 68, 0.4);
		}
		
		.grid-metadata {
			display: grid;
			grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
			gap: 20px;
		}
		
		.meta-item {
			display: flex;
			flex-direction: column;
			gap: 6px;
		}
		
		.meta-label {
			font-size: 11px;
			color: var(--text-muted);
			text-transform: uppercase;
			letter-spacing: 0.1em;
			font-weight: 700;
		}
		
		.meta-value {
			font-size: 15px;
			font-weight: 600;
		}
		
		.chat-container {
			display: flex;
			flex-direction: column;
			gap: 8px;
		}
		
		.message-row {
			display: flex;
			gap: 16px;
			padding: 12px 16px;
			border-radius: 10px;
			transition: background-color 0.15s ease;
		}
		
		.message-row:hover {
			background-color: var(--message-hover);
		}
		
		.avatar-circle {
			width: 44px;
			height: 44px;
			border-radius: 50%;
			display: flex;
			align-items: center;
			justify-content: center;
			font-weight: 700;
			font-size: 18px;
			color: #ffffff;
			flex-shrink: 0;
			text-transform: uppercase;
			box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
		}
		
		.message-content-wrapper {
			display: flex;
			flex-direction: column;
			gap: 6px;
			width: 100%;
		}
		
		.message-header {
			display: flex;
			align-items: center;
			gap: 10px;
			flex-wrap: wrap;
		}
		
		.username {
			font-weight: 700;
			font-size: 15px;
			color: #ffffff;
		}
		
		.user-badge {
			font-size: 10px;
			font-weight: 800;
			padding: 2px 8px;
			border-radius: 6px;
			text-transform: uppercase;
			letter-spacing: 0.05em;
		}
		
		.badge-bot {
			background-color: var(--bot-bg);
			color: var(--bot-color);
			border: 1px solid rgba(59, 130, 246, 0.3);
		}
		
		.badge-creator {
			background-color: var(--creator-bg);
			color: var(--creator-color);
			border: 1px solid rgba(16, 185, 129, 0.3);
		}
		
		.badge-staff {
			background-color: var(--staff-bg);
			color: var(--staff-color);
			border: 1px solid rgba(245, 158, 11, 0.3);
		}
		
		.timestamp {
			font-size: 12px;
			color: var(--text-muted);
		}
		
		.message-text {
			font-size: 14.5px;
			line-height: 1.6;
			word-break: break-word;
			color: #e2e8f0;
		}
		
		pre {
			background-color: #0b0d11;
			padding: 14px;
			border-radius: 8px;
			overflow-x: auto;
			margin: 10px 0;
			border: 1px solid var(--border);
		}
		
		code {
			font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
			background-color: #0b0d11;
			padding: 3px 6px;
			border-radius: 6px;
			font-size: 13px;
			color: #f1f5f9;
		}
		
		pre code {
			padding: 0;
			background-color: transparent;
			font-size: 13px;
		}
		
		.footer {
			margin-top: 48px;
			border-top: 1px solid var(--border);
			padding-top: 20px;
			text-align: center;
			font-size: 12px;
			color: var(--text-muted);
			font-weight: 500;
		}
	</style>
</head>
<body>
	<div class="wrapper">
		<div class="header">
			<h1 class="header-title">
				🎫 Ticket #{{ ticket.ticketId }}
				<span class="badge-status status-closed">Closed</span>
			</h1>
			<div class="grid-metadata">
				<div class="meta-item">
					<span class="meta-label">Created By</span>
					<span class="meta-value">
						{{ creator_name }}
						{% if ticket.playerInfo.minecraftUsername %}
							({{ ticket.playerInfo.minecraftUsername }})
						{% endif %}
					</span>
				</div>
				<div class="meta-item">
					<span class="meta-label">Claimed By</span>
					<span class="meta-value">
						{% if claimed_by_name %}
							@{{ claimed_by_name }}
						{% else %}
							Not Claimed
						{% endif %}
					</span>
				</div>
				<div class="meta-item">
					<span class="meta-label">Closed By</span>
					<span class="meta-value">
						{% if closed_by_name %}
							@{{ closed_by_name }}
						{% else %}
							Unknown
						{% endif %}
					</span>
				</div>
				<div class="meta-item">
					<span class="meta-label">Opened At</span>
					<span class="meta-value">{{ opened_time }}</span>
				</div>
				<div class="meta-item">
					<span class="meta-label">Closed At</span>
					<span class="meta-value">{{ closed_time }}</span>
				</div>
				<div class="meta-item">
					<span class="meta-label">Feedback</span>
					<span class="meta-value">
						{% if ticket.feedback.value != "None" %}
							{{ ticket.feedback.value }}
						{% else %}
							No Feedback Submitted
						{% endif %}
					</span>
				</div>
			</div>
		</div>
		
		<div class="chat-container">
			{% for msg in messages %}
			<div class="message-row">
				<div class="avatar-circle" style="background: {{ msg.avatar_color }};">
					{{ msg.avatar_char }}
				</div>
				<div class="message-content-wrapper">
					<div class="message-header">
						<span class="username">{{ msg.username }}</span>
						{% for badge in msg.badges %}
							<span class="user-badge {{ badge.class }}">{{ badge.label }}</span>
						{% endfor %}
						<span class="timestamp">{{ msg.timestamp_str }}</span>
					</div>
					<div class="message-text">
						{{ msg.formatted_content }}
					</div>
				</div>
			</div>
			{% endfor %}
		</div>
		
		<div class="footer">
			Transcript generated by MCLabs Help System on {{ current_time }}
		</div>
	</div>
</body>
</html>
'''

def generate_html_transcript(
	ticket: HelpTicket,
	resolved_names: Dict[str, str]
) -> str:
	'''
	# Generate HTML Transcript

	Builds a beautiful standalone HTML string from a HelpTicket history.

	## Parameters
		ticket (HelpTicket): The help ticket object.
		resolved_names (Dict[str, str]): A mapping of Discord IDs to display names.
	'''
	# Formatted dates
	opened_time = format_timestamp(ticket.time_create)
	closed_time = format_timestamp(ticket.time_close)
	current_time = format_timestamp(datetime.datetime.now(timezone.utc).timestamp())

	# Creator name resolution
	creator_discord_id = ticket.playerInfo.discordId
	creator_name = resolved_names.get(creator_discord_id) if creator_discord_id else None
	if not creator_name:
		creator_name = ticket.playerInfo.discordUsername or "Unknown"

	# Closed by and claimed by names
	closed_by_name = resolved_names.get(ticket.closedBy) if ticket.closedBy else None
	if not closed_by_name and ticket.closedBy:
		closed_by_name = ticket.closedBy
	
	claimed_by_name = resolved_names.get(ticket.claimedBy) if ticket.claimedBy else None

	# Process message logs
	processed_messages: List[Dict[str, Any]] = []
	for message in ticket.conversation.messages:
		# Determine sender name
		sender_id = message.sender.discordId
		sender_name = message.sender.discordUsername or "Unknown"
		
		# If it's a known discord ID, use resolved names
		if sender_id and sender_id in resolved_names:
			sender_name = resolved_names[sender_id]
		elif message.sender.minecraftUsername == "WikiGPT":
			sender_name = "WikiGPT"

		# Create initials avatar
		avatar_char = sender_name[0] if sender_name else "?"
		avatar_color = get_avatar_color(sender_name)

		# Build badges
		badges = []
		
		# Check if WikiGPT bot
		if message.sender.minecraftUsername == "WikiGPT" or sender_id == "000000000000000000":
			badges.append({"class": "badge-bot", "label": "Bot"})
		else:
			# Check if creator
			if sender_id and creator_discord_id and sender_id == creator_discord_id:
				badges.append({"class": "badge-creator", "label": "Creator"})
			
			# Check if claimed helper/staff
			if sender_id and ticket.claimedBy and sender_id == ticket.claimedBy:
				badges.append({"class": "badge-staff", "label": "Staff"})

		# Process content and date
		formatted_content = format_markdown(message.content)
		timestamp_str = format_timestamp(message.timestamp)

		processed_messages.append({
			"username": sender_name,
			"avatar_char": avatar_char,
			"avatar_color": avatar_color,
			"badges": badges,
			"timestamp_str": timestamp_str,
			"formatted_content": formatted_content
		})

	# Setup Jinja2 template and render
	template = Template(HTML_TEMPLATE)
	return template.render(
		ticket=ticket,
		creator_name=creator_name,
		claimed_by_name=claimed_by_name,
		closed_by_name=closed_by_name,
		opened_time=opened_time,
		closed_time=closed_time,
		current_time=current_time,
		messages=processed_messages
	)
