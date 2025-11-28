import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ================== CONFIG ==================

# Ticket categories (for reference)
TICKET_CATEGORIES = [
    "New Order",
    "Order Issue",
    "Refund Request",
    "General Support",
    "Check Referral"
]

# Category where ticket channels are created
TICKET_CATEGORY_NAME = "Tickets"

# Data files
TICKETS_FILE = "tickets.json"
STATUS_FILE = "status.json"

# Status channel name
STATUS_CHANNEL_NAME = "order-status"

# ============================================

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ========== DATA HELPERS ==========

def load_tickets():
    if os.path.exists(TICKETS_FILE):
        try:
            with open(TICKETS_FILE, "r") as f:
                content = f.read().strip()
                if not content:
                    return {}
                return json.loads(content)
        except json.JSONDecodeError:
            print("⚠️ Warning: tickets.json is corrupted. Starting fresh.")
            return {}
    return {}


def save_tickets(data):
    with open(TICKETS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_status():
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r") as f:
                content = f.read().strip()
                if not content:
                    return {}
                return json.loads(content)
        except json.JSONDecodeError:
            return {}
    return {}


def save_status(data):
    with open(STATUS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_server_status(guild_id: int):
    status_data = load_status()
    guild_id_str = str(guild_id)
    return status_data.get(
        guild_id_str,
        {"is_open": False, "message_id": None, "channel_id": None},
    )


def set_server_status(guild_id: int, is_open: bool, message_id=None, channel_id=None):
    status_data = load_status()
    guild_id_str = str(guild_id)
    status_data[guild_id_str] = {
        "is_open": is_open,
        "message_id": message_id,
        "channel_id": channel_id,
    }
    save_status(status_data)
    return status_data[guild_id_str]


def get_ticket_data_for_guild(guild_id: int):
    tickets = load_tickets()
    guild_id_str = str(guild_id)
    if guild_id_str not in tickets:
        tickets[guild_id_str] = {}
        save_tickets(tickets)
    return tickets[guild_id_str]


def get_ticket_record(guild_id: int, channel_id: int):
    tickets = load_tickets()
    g = tickets.get(str(guild_id), {})
    return g.get(str(channel_id))


def create_ticket_record(guild_id: int, channel_id: int, user_id: int,
                         ticket_type: str, order_link: str | None = None):
    tickets = load_tickets()
    guild_id_str = str(guild_id)
    channel_id_str = str(channel_id)

    if guild_id_str not in tickets:
        tickets[guild_id_str] = {}

    tickets[guild_id_str][channel_id_str] = {
        "user_id": user_id,
        "type": ticket_type,
        "order_link": order_link,
        "created_at": datetime.now().isoformat(),
        "status": "open",
        # message id for the preview embed
        "preview_message_id": None,
        # order form fields
        "order_details": {
            "account_name": "Not set",
            "payment_methods": "Not set (chef will confirm in ticket)",
            "tip": "$0",
            "delivery_type": "Leave at my door",
            "delivery_notes": "N/A",
        },
    }

    save_tickets(tickets)


def set_ticket_preview_message_id(guild_id: int, channel_id: int, message_id: int):
    tickets = load_tickets()
    g = tickets.get(str(guild_id))
    if not g:
        return
    c = g.get(str(channel_id))
    if not c:
        return
    c["preview_message_id"] = message_id
    save_tickets(tickets)


def close_ticket_record(guild_id: int, channel_id: int):
    tickets = load_tickets()
    guild_id_str = str(guild_id)
    channel_id_str = str(channel_id)

    if guild_id_str in tickets and channel_id_str in tickets[guild_id_str]:
        tickets[guild_id_str][channel_id_str]["status"] = "closed"
        tickets[guild_id_str][channel_id_str]["closed_at"] = datetime.now().isoformat()
        save_tickets(tickets)


def update_order_field(guild_id: int, channel_id: int, field: str, value: str):
    tickets = load_tickets()
    g = tickets.get(str(guild_id))
    if not g:
        return
    c = g.get(str(channel_id))
    if not c:
        return
    details = c.setdefault("order_details", {})
    details[field] = value
    save_tickets(tickets)


def build_order_preview_embed(guild_id: int, channel_id: int):
    tickets = load_tickets()
    guild_data = tickets.get(str(guild_id), {})
    ticket = guild_data.get(str(channel_id))

    if not ticket:
        # Fallback embed if something goes wrong
        embed = discord.Embed(
            title="Philly Eats • Preview",
            description="Unable to load order preview.",
            color=0x00AEFF,
        )
        return embed

    details = ticket.get("order_details", {})
    order_link = ticket.get("order_link")

    account_name = details.get("account_name", "Not set")
    payment_methods = details.get(
        "payment_methods", "Not set (chef will confirm in ticket)"
    )
    tip = details.get("tip", "$0")
    delivery_type = details.get("delivery_type", "Leave at my door")
    delivery_notes = details.get("delivery_notes", "N/A")

    embed = discord.Embed(
        title="Philly Eats – Helper",
        description="**Before you order...**\nReview your info before submitting your ticket.",
        color=0x00AEFF,
    )

    # Group link
    if order_link:
        embed.add_field(
            name="📎 Group Link:",
            value=f"[Open Cart]({order_link})",
            inline=False,
        )
    else:
        embed.add_field(
            name="📎 Group Link:",
            value="Not set",
            inline=False,
        )

    embed.add_field(name="🪪 Account Name:", value=account_name or "Not set", inline=False)
    embed.add_field(
        name="💳 Preferred Payment Methods:",
        value=payment_methods or "Not set (chef will confirm in ticket)",
        inline=False,
    )
    embed.add_field(name="💰 Tip:", value=tip or "$0", inline=False)
    embed.add_field(name="📦 Delivery Type:", value=delivery_type or "Leave at my door", inline=False)
    embed.add_field(name="📝 Delivery Notes:", value=delivery_notes or "N/A", inline=False)

    embed.set_footer(text="Philly Eats • Preview")
    embed.timestamp = datetime.now()
    return embed


# ========== EVENTS ==========

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"🎫 {bot.user} is online!")
    print("📋 Ticket system ready")


# ========== ORDER FORM MODALS ==========

class NameModal(discord.ui.Modal, title="Set Account Name"):
    def __init__(self, guild_id: int, channel_id: int, preview_message_id: int):
        super().__init__()
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.preview_message_id = preview_message_id

        self.account_name = discord.ui.TextInput(
            label="Account name for this order",
            placeholder="e.g. random",
            style=discord.TextStyle.short,
            required=True,
        )
        self.add_item(self.account_name)

    async def on_submit(self, interaction: discord.Interaction):
        update_order_field(
            self.guild_id, self.channel_id, "account_name", str(self.account_name.value)
        )

        channel = interaction.guild.get_channel(self.channel_id)
        if channel:
            message = await channel.fetch_message(self.preview_message_id)
            embed = build_order_preview_embed(self.guild_id, self.channel_id)
            view = OrderFormView(self.guild_id, self.channel_id)
            await message.edit(embed=embed, view=view)

        await interaction.response.send_message("✅ Account name updated.", ephemeral=True)


class PaymentModal(discord.ui.Modal, title="Set Payment Methods"):
    def __init__(self, guild_id: int, channel_id: int, preview_message_id: int):
        super().__init__()
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.preview_message_id = preview_message_id

        self.methods = discord.ui.TextInput(
            label="Payment methods (e.g. Cash App, Zelle)",
            placeholder="Not set (chef will confirm in ticket)",
            style=discord.TextStyle.paragraph,
            required=False,
        )
        self.add_item(self.methods)

    async def on_submit(self, interaction: discord.Interaction):
        value = self.methods.value.strip() or "Not set (chef will confirm in ticket)"
        update_order_field(
            self.guild_id, self.channel_id, "payment_methods", value
        )

        channel = interaction.guild.get_channel(self.channel_id)
        if channel:
            message = await channel.fetch_message(self.preview_message_id)
            embed = build_order_preview_embed(self.guild_id, self.channel_id)
            view = OrderFormView(self.guild_id, self.channel_id)
            await message.edit(embed=embed, view=view)

        await interaction.response.send_message("✅ Payment methods updated.", ephemeral=True)


class TipModal(discord.ui.Modal, title="Set Tip"):
    def __init__(self, guild_id: int, channel_id: int, preview_message_id: int):
        super().__init__()
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.preview_message_id = preview_message_id

        self.tip_amount = discord.ui.TextInput(
            label="Tip amount (e.g. $3, 10%)",
            placeholder="$0",
            style=discord.TextStyle.short,
            required=False,
        )
        self.add_item(self.tip_amount)

    async def on_submit(self, interaction: discord.Interaction):
        value = self.tip_amount.value.strip() or "$0"
        if not value.startswith("$") and not value.endswith("%"):
            value = f"${value}"
        update_order_field(self.guild_id, self.channel_id, "tip", value)

        channel = interaction.guild.get_channel(self.channel_id)
        if channel:
            message = await channel.fetch_message(self.preview_message_id)
            embed = build_order_preview_embed(self.guild_id, self.channel_id)
            view = OrderFormView(self.guild_id, self.channel_id)
            await message.edit(embed=embed, view=view)

        await interaction.response.send_message("✅ Tip updated.", ephemeral=True)


class NotesModal(discord.ui.Modal, title="Set Delivery Notes"):
    def __init__(self, guild_id: int, channel_id: int, preview_message_id: int):
        super().__init__()
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.preview_message_id = preview_message_id

        self.notes = discord.ui.TextInput(
            label="Delivery notes for courier",
            placeholder="N/A",
            style=discord.TextStyle.paragraph,
            required=False,
        )
        self.add_item(self.notes)

    async def on_submit(self, interaction: discord.Interaction):
        value = self.notes.value.strip() or "N/A"
        update_order_field(self.guild_id, self.channel_id, "delivery_notes", value)

        channel = interaction.guild.get_channel(self.channel_id)
        if channel:
            message = await channel.fetch_message(self.preview_message_id)
            embed = build_order_preview_embed(self.guild_id, self.channel_id)
            view = OrderFormView(self.guild_id, self.channel_id)
            await message.edit(embed=embed, view=view)

        await interaction.response.send_message("✅ Delivery notes updated.", ephemeral=True)


# ========== ORDER FORM VIEW ==========

class OrderFormView(discord.ui.View):
    def __init__(self, guild_id: int, channel_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.channel_id = channel_id

    @discord.ui.button(label="Submit", style=discord.ButtonStyle.green, custom_id="order_submit_btn")
    async def submit(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket = get_ticket_record(self.guild_id, self.channel_id)
        if not ticket:
            await interaction.response.send_message("❌ This is not a valid ticket.", ephemeral=True)
            return

        # Only ticket creator or staff can submit
        if interaction.user.id != ticket["user_id"] and not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message(
                "❌ Only the ticket owner or staff can submit this order.",
                ephemeral=True,
            )
            return

        # Mark as submitted (optional flag)
        tickets = load_tickets()
        tickets[str(self.guild_id)][str(self.channel_id)]["order_submitted"] = True
        save_tickets(tickets)

        # Disable all components
        for item in self.children:
            item.disabled = True

        embed = build_order_preview_embed(self.guild_id, self.channel_id)
        embed.title = "Philly Eats – Order Submitted"
        embed.set_footer(text="Order submitted • Philly Eats")

        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.channel.send(
            f"📥 New order submitted by {interaction.user.mention}.",
            allowed_mentions=discord.AllowedMentions(users=True),
        )

    @discord.ui.button(label="Name", style=discord.ButtonStyle.secondary, custom_id="order_name_btn")
    async def set_name(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket = get_ticket_record(self.guild_id, self.channel_id)
        if not ticket:
            await interaction.response.send_message("❌ This is not a valid ticket.", ephemeral=True)
            return

        modal = NameModal(self.guild_id, self.channel_id, ticket["preview_message_id"])
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Payment", style=discord.ButtonStyle.secondary, custom_id="order_payment_btn")
    async def set_payment(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket = get_ticket_record(self.guild_id, self.channel_id)
        if not ticket:
            await interaction.response.send_message("❌ This is not a valid ticket.", ephemeral=True)
            return

        modal = PaymentModal(self.guild_id, self.channel_id, ticket["preview_message_id"])
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Tip", style=discord.ButtonStyle.secondary, custom_id="order_tip_btn")
    async def set_tip(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket = get_ticket_record(self.guild_id, self.channel_id)
        if not ticket:
            await interaction.response.send_message("❌ This is not a valid ticket.", ephemeral=True)
            return

        modal = TipModal(self.guild_id, self.channel_id, ticket["preview_message_id"])
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Notes", style=discord.ButtonStyle.secondary, custom_id="order_notes_btn")
    async def set_notes(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket = get_ticket_record(self.guild_id, self.channel_id)
        if not ticket:
            await interaction.response.send_message("❌ This is not a valid ticket.", ephemeral=True)
            return

        modal = NotesModal(self.guild_id, self.channel_id, ticket["preview_message_id"])
        await interaction.response.send_modal(modal)

    @discord.ui.select(
        placeholder="Delivery type (Leave / Meet)...",
        custom_id="order_delivery_select",
        options=[
            discord.SelectOption(
                label="Leave at my door",
                description="Default – courier leaves it at your door",
            ),
            discord.SelectOption(
                label="Meet at my door",
                description="Meet the courier at the door / outside",
            ),
        ],
    )
    async def delivery_type_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        choice = select.values[0]
        update_order_field(self.guild_id, self.channel_id, "delivery_type", choice)

        # Update preview embed in place
        embed = build_order_preview_embed(self.guild_id, self.channel_id)
        await interaction.response.edit_message(embed=embed, view=self)


# ========== TICKET CREATION VIEW (PANEL) ==========

class TicketPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📝 New Order", style=discord.ButtonStyle.green, custom_id="ticket_new_order")
    async def new_order(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "New Order", requires_link=True)

    @discord.ui.button(label="⚠️ Order Issue", style=discord.ButtonStyle.red, custom_id="ticket_order_issue")
    async def order_issue(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Order Issue", requires_link=True)

    @discord.ui.button(label="💰 Refund Request", style=discord.ButtonStyle.red, custom_id="ticket_refund")
    async def refund_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Refund Request", requires_link=True)

    @discord.ui.button(label="🔗 Check Referral", style=discord.ButtonStyle.primary, custom_id="ticket_referral")
    async def check_referral(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Check Referral", requires_link=False)

    @discord.ui.button(label="❓ General Support", style=discord.ButtonStyle.gray, custom_id="ticket_support")
    async def general_support(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "General Support", requires_link=False)

    async def create_ticket(self, interaction: discord.Interaction, ticket_type: str, requires_link: bool):
        if requires_link:
            modal = OrderLinkModal(ticket_type=ticket_type)
            await interaction.response.send_modal(modal)
        else:
            await self.create_ticket_channel(interaction, ticket_type, order_link=None)

    async def create_ticket_channel(self, interaction: discord.Interaction, ticket_type: str, order_link: str | None = None):
        guild = interaction.guild
        user = interaction.user

        # Find or create Tickets category
        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)
        if not category:
            category = await guild.create_category(TICKET_CATEGORY_NAME)

        # Channel naming
        if ticket_type == "New Order":
            channel_name = f"order-{user.name.lower()}-{datetime.now().strftime('%m-%d')}"
        elif ticket_type == "Check Referral":
            channel_name = "check-referral"
        else:
            channel_name = f"{ticket_type.lower().replace(' ', '-')}-{user.name.lower()}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }

        channel = await category.create_text_channel(
            name=channel_name,
            overwrites=overwrites,
        )

        # Create ticket record
        create_ticket_record(guild.id, channel.id, user.id, ticket_type, order_link)

        # Welcome embed
        embed = discord.Embed(
            title=f"🎫 {ticket_type}",
            description=f"Welcome {user.mention}! A staff member will assist you shortly.",
            color=0x00FF00 if ticket_type == "New Order" else 0x3498DB,
        )
        embed.add_field(name="Ticket Type", value=ticket_type, inline=True)
        embed.add_field(name="Created By", value=user.mention, inline=True)
        if order_link:
            embed.add_field(name="🔗 Order Link", value=f"[Open Cart]({order_link})", inline=False)
        embed.set_footer(text="Use /close to close this ticket")
        embed.timestamp = datetime.now()

        close_view = TicketCloseView()
        await channel.send(embed=embed, view=close_view)

        # Order preview (for New Order tickets mainly, but nice for all that have a link)
        if ticket_type == "New Order" or order_link:
            preview_embed = build_order_preview_embed(guild.id, channel.id)
            order_view = OrderFormView(guild.id, channel.id)
            preview_message = await channel.send(embed=preview_embed, view=order_view)
            set_ticket_preview_message_id(guild.id, channel.id, preview_message.id)

        # Confirmation to the user
        try:
            await interaction.response.send_message(
                f"✅ Ticket created! {channel.mention}", ephemeral=True
            )
        except discord.InteractionResponded:
            await interaction.followup.send(
                f"✅ Ticket created! {channel.mention}", ephemeral=True
            )


# ========== ORDER LINK MODAL (FOR NEW ORDER / ISSUE / REFUND) ==========

class OrderLinkModal(discord.ui.Modal):
    def __init__(self, ticket_type: str):
        super().__init__(title=f"Create {ticket_type} Ticket")
        self.ticket_type = ticket_type

        self.order_link = discord.ui.TextInput(
            label="Group Order Link",
            placeholder="https://eats.uber.com/group-orders/.../join",
            style=discord.TextStyle.short,
            required=True,
        )
        self.add_item(self.order_link)

    async def on_submit(self, interaction: discord.Interaction):
        view = TicketPanel()
        await view.create_ticket_channel(interaction, self.ticket_type, self.order_link.value)


# ========== CLOSE TICKET VIEW ==========

class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Close Ticket", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel

        tickets = load_tickets()
        guild_id_str = str(interaction.guild_id)
        channel_id_str = str(channel.id)

        if guild_id_str in tickets and channel_id_str in tickets[guild_id_str]:
            ticket_data = tickets[guild_id_str][channel_id_str]
            ticket_creator = ticket_data["user_id"]

            if interaction.user.id == ticket_creator or interaction.user.guild_permissions.manage_channels:
                close_ticket_record(interaction.guild_id, channel.id)

                embed = discord.Embed(
                    title="🔒 Ticket Closed",
                    description=f"This ticket has been closed by {interaction.user.mention}.\nChannel will be deleted in 10 seconds.",
                    color=0xE74C3C,
                )

                await interaction.response.send_message(embed=embed)

                import asyncio
                await asyncio.sleep(10)
                await channel.delete()
            else:
                await interaction.response.send_message(
                    "❌ Only the ticket creator or staff can close this ticket.",
                    ephemeral=True,
                )
        else:
            await interaction.response.send_message(
                "❌ This doesn't appear to be a valid ticket channel.",
                ephemeral=True,
            )


# ========== SLASH COMMANDS ==========

@bot.tree.command(name="panel", description="Create the ticket panel (Admin only)")
async def panel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ You need Administrator permission.", ephemeral=True
        )
        return

    embed = discord.Embed(
        title="🎫 Philly Eats - Support Tickets",
        description=(
            "Need help? Create a ticket by clicking one of the buttons below!\n\n"
            "**📝 New Order** - Submit a new group order\n"
            "**⚠️ Order Issue** - Report a problem with your order\n"
            "**💰 Refund Request** - Request a refund\n"
            "**🔗 Check Referral** - Verify referral status\n"
            "**❓ General Support** - Other questions"
        ),
        color=0x00AEFF,
    )
    embed.set_footer(text="We're open! Tap a button to get started.")

    view = TicketPanel()
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("✅ Ticket panel created!", ephemeral=True)


@bot.tree.command(name="close", description="Close the current ticket")
async def close(interaction: discord.Interaction):
    channel = interaction.channel

    tickets = load_tickets()
    guild_id_str = str(interaction.guild_id)
    channel_id_str = str(channel.id)

    if guild_id_str in tickets and channel_id_str in tickets[guild_id_str]:
        ticket_data = tickets[guild_id_str][channel_id_str]
        ticket_creator = ticket_data["user_id"]

        if interaction.user.id == ticket_creator or interaction.user.guild_permissions.manage_channels:
            close_ticket_record(interaction.guild_id, channel.id)

            embed = discord.Embed(
                title="🔒 Ticket Closed",
                description=f"This ticket has been closed by {interaction.user.mention}.\nChannel will be deleted in 10 seconds.",
                color=0xE74C3C,
            )

            await interaction.response.send_message(embed=embed)

            import asyncio
            await asyncio.sleep(10)
            await channel.delete()
        else:
            await interaction.response.send_message(
                "❌ Only the ticket creator or staff can close this ticket.",
                ephemeral=True,
            )
    else:
        await interaction.response.send_message(
            "❌ This command can only be used in ticket channels.",
            ephemeral=True,
        )


@bot.tree.command(name="add", description="Add a user to the current ticket")
@app_commands.describe(user="The user to add to the ticket")
async def add_user(interaction: discord.Interaction, user: discord.Member):
    channel = interaction.channel

    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message(
            "❌ You need 'Manage Channels' permission.", ephemeral=True
        )
        return

    tickets = load_tickets()
    guild_id_str = str(interaction.guild_id)
    channel_id_str = str(channel.id)

    if guild_id_str in tickets and channel_id_str in tickets[guild_id_str]:
        await channel.set_permissions(user, read_messages=True, send_messages=True)
        await interaction.response.send_message(
            f"✅ Added {user.mention} to this ticket."
        )
    else:
        await interaction.response.send_message(
            "❌ This command can only be used in ticket channels.",
            ephemeral=True,
        )


@bot.tree.command(name="remove", description="Remove a user from the current ticket")
@app_commands.describe(user="The user to remove from the ticket")
async def remove_user(interaction: discord.Interaction, user: discord.Member):
    channel = interaction.channel

    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message(
            "❌ You need 'Manage Channels' permission.", ephemeral=True
        )
        return

    tickets = load_tickets()
    guild_id_str = str(interaction.guild_id)
    channel_id_str = str(channel.id)

    if guild_id_str in tickets and channel_id_str in tickets[guild_id_str]:
        await channel.set_permissions(user, read_messages=False)
        await interaction.response.send_message(
            f"✅ Removed {user.mention} from this ticket."
        )
    else:
        await interaction.response.send_message(
            "❌ This command can only be used in ticket channels.",
            ephemeral=True,
        )


@bot.tree.command(name="status", description="Set server open/closed status")
@app_commands.describe(state="Open or closed?")
@app_commands.choices(
    state=[
        app_commands.Choice(name="🟢 Open", value="open"),
        app_commands.Choice(name="🔴 Closed", value="closed"),
    ]
)
async def status(interaction: discord.Interaction, state: app_commands.Choice[str]):
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message(
            "❌ You need 'Manage Messages' permission.", ephemeral=True
        )
        return

    is_open = state.value == "open"

    status_channel = discord.utils.get(
        interaction.guild.channels, name=STATUS_CHANNEL_NAME
    )
    if not status_channel:
        for channel in interaction.guild.text_channels:
            if "order" in channel.name.lower() or "status" in channel.name.lower():
                status_channel = channel
                break

    if not status_channel:
        await interaction.response.send_message(
            f"❌ Couldn't find status channel. Please create a channel named `{STATUS_CHANNEL_NAME}` or use this command in the channel where you want status updates.",
            ephemeral=True,
        )
        return

    current_status = get_server_status(interaction.guild_id)

    if current_status.get("message_id") and current_status.get("channel_id"):
        try:
            old_channel = interaction.guild.get_channel(
                int(current_status["channel_id"])
            )
            if old_channel:
                old_message = await old_channel.fetch_message(
                    int(current_status["message_id"])
                )
                await old_message.delete()
        except Exception:
            pass

    if is_open:
        embed = discord.Embed(
            title="🟢 We're Open!",
            description="Tap **Order** below to send us your details.\n\nReady to take your orders now! 🍽️",
            color=0x00FF00,
        )
        embed.add_field(name="Status", value="✅ Taking Orders", inline=True)
        embed.set_footer(text="Philly Eats")
        view = TicketPanel()
        message = await status_channel.send(embed=embed, view=view)
    else:
        embed = discord.Embed(
            title="🔴 We're Closed",
            description="Sorry, we're not taking orders right now.\n\nCheck back later! 😊",
            color=0xFF0000,
        )
        embed.add_field(name="Status", value="❌ Closed", inline=True)
        embed.set_footer(text="Philly Eats")
        message = await status_channel.send(embed=embed)

    embed.timestamp = datetime.now()

    set_server_status(interaction.guild_id, is_open, message.id, status_channel.id)

    await interaction.response.send_message(
        f"✅ Status updated to: **{'🟢 OPEN' if is_open else '🔴 CLOSED'}**\nMessage sent in {status_channel.mention}",
        ephemeral=True,
    )


# ========== RUN BOT ==========

if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_BOT_TOKEN_TICKETS")
    if not TOKEN:
        print("❌ Error: DISCORD_BOT_TOKEN_TICKETS not found in .env file")
    else:
        bot.run(TOKEN)
