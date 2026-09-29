import json
import logging
import os
import ssl
import time
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from app import (
    Household,
    Reminder,
    User,
    Vehicle,
    create_app,
    db,
    reminder_status,
    utc_now,
    valid_discord_webhook_url,
)


logger = logging.getLogger(__name__)


def build_reminder_message(vehicle, reminder):
    date_due = reminder.due_date.isoformat() if reminder.due_date else None
    mileage_due = reminder.due_odometer
    due_parts = []
    if date_due:
        due_parts.append(f"date {date_due}")
    if mileage_due is not None:
        due_parts.append(f"{mileage_due:,} miles")
    due_text = " and ".join(due_parts) or "now"
    repeat_parts = []
    if reminder.recurrence_days:
        repeat_parts.append(f"every {reminder.recurrence_days} days")
    if reminder.recurrence_miles:
        repeat_parts.append(f"every {reminder.recurrence_miles:,} miles")
    repeat_text = f" (repeats {' and '.join(repeat_parts)})" if repeat_parts else ""
    return (
        f"CarFreeks: {reminder_status(reminder, vehicle.current_odometer)} service due "
        f"for {vehicle.nickname}: {reminder.title}. Due {due_text}{repeat_text}."
    )


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def send_discord_message(webhook_url, message):
    if not valid_discord_webhook_url(webhook_url):
        raise ValueError("Refusing to send to an invalid Discord webhook URL.")
    body = json.dumps(
        {
            "content": message,
            "allowed_mentions": {"parse": []},
        }
    ).encode("utf-8")
    request = Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    opener = build_opener(
        NoRedirectHandler(),
        HTTPSHandler(context=ssl.create_default_context()),
    )
    try:
        with opener.open(request, timeout=10) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError("Discord returned a non-success status.")
    except HTTPError as error:
        if 300 <= error.code < 400:
            raise ValueError("Discord webhook redirects are not followed.") from None
        raise


def is_due(reminder, vehicle, today):
    return (
        reminder.due_date is not None
        and reminder.due_date <= today
    ) or (
        reminder.due_odometer is not None
        and vehicle.current_odometer is not None
        and reminder.due_odometer <= vehicle.current_odometer
    )


def process_due_reminders(app):
    with app.app_context():
        pending = (
            db.session.query(Reminder, Vehicle, Household)
            .join(Vehicle, Reminder.vehicle_id == Vehicle.id)
            .join(User, Vehicle.owner_id == User.id)
            .join(Household, User.household_id == Household.id)
            .filter(
                Reminder.completed.is_(False),
                Reminder.last_notified_at.is_(None),
                Household.discord_webhook_url.isnot(None),
            )
            .order_by(Reminder.id)
            .all()
        )
        today = utc_now().date()
        delivered = 0
        for reminder, vehicle, household in pending:
            if not is_due(reminder, vehicle, today):
                continue
            if not valid_discord_webhook_url(household.discord_webhook_url):
                logger.error(
                    "Skipping reminder %s: stored Discord webhook URL is invalid.",
                    reminder.id,
                )
                continue
            try:
                send_discord_message(
                    household.discord_webhook_url,
                    build_reminder_message(vehicle, reminder),
                )
            except Exception as error:
                logger.error(
                    "Discord notification failed for reminder %s (%s).",
                    reminder.id,
                    type(error).__name__,
                )
                continue
            reminder.last_notified_at = utc_now()
            db.session.commit()
            delivered += 1
        return delivered


def main():
    logging.basicConfig(
        level=os.environ.get("CARFREEKS_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app = create_app()
    interval = max(
        30, int(os.environ.get("CARFREEKS_NOTIFICATION_INTERVAL_SECONDS", "300"))
    )
    logger.info("Reminder notification worker started.")
    while True:
        process_due_reminders(app)
        time.sleep(interval)


if __name__ == "__main__":
    main()
