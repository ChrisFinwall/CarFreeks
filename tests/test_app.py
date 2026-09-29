import io
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app import (
    Reminder,
    ServiceRecord,
    User,
    ValueEntry,
    Vehicle,
    create_app,
    db,
    reminder_status,
)


class CarFreeksTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        data_dir = Path(self.temp_dir.name)
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret-key-that-is-long-enough",
                "ADMIN_USERNAME": "owner",
                "ADMIN_PASSWORD": "test-password-long",
                "CARFREEKS_DATA_DIR": str(data_dir),
                "UPLOAD_FOLDER": str(data_dir / "receipts"),
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{(data_dir / 'test.db').as_posix()}",
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.temp_dir.cleanup()

    def login(self):
        return self.client.post(
            "/login",
            data={"username": "owner", "password": "test-password-long"},
            follow_redirects=True,
        )

    def add_vehicle(self):
        return self.client.post(
            "/vehicles/new",
            data={
                "nickname": "Bluebird",
                "year": "2020",
                "make": "Example",
                "model": "Commuter",
                "vehicle_type": "Car",
                "vin": "",
                "license_plate": "",
            },
        )

    def test_owner_login_and_vehicle_dashboard(self):
        self.assertEqual(self.client.get("/").status_code, 302)
        self.login()

        response = self.add_vehicle()

        self.assertEqual(response.status_code, 302)
        dashboard = self.client.get("/")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn(b"Bluebird", dashboard.data)
        self.assertIn(b"2020 Example Commuter", dashboard.data)

    def test_state_changes_require_csrf_tokens(self):
        self.login()
        self.app.config["WTF_CSRF_ENABLED"] = True

        response = self.add_vehicle()

        self.assertEqual(response.status_code, 400)
        with self.app.app_context():
            self.assertEqual(Vehicle.query.count(), 0)

    def test_vehicle_records_and_receipt_download(self):
        self.login()
        self.add_vehicle()
        with self.app.app_context():
            vehicle = Vehicle.query.one()
            vehicle_id = vehicle.id

        self.client.post(
            f"/vehicles/{vehicle_id}/odometer/new",
            data={"reading": "32500", "recorded_on": date.today().isoformat(), "note": ""},
        )
        self.client.post(
            f"/vehicles/{vehicle_id}/value/new",
            data={
                "amount": "18750.00",
                "valued_on": date.today().isoformat(),
                "source": "Owner estimate",
                "notes": "",
            },
        )
        response = self.client.post(
            f"/vehicles/{vehicle_id}/service/new",
            data={
                "title": "Oil change",
                "category": "Maintenance",
                "completed_on": date.today().isoformat(),
                "odometer": "32500",
                "cost": "64.95",
                "notes": "Synthetic oil",
                "receipt": (io.BytesIO(b"test receipt"), "receipt.pdf"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 302)

        detail = self.client.get(f"/vehicles/{vehicle_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertIn(b"32,500", detail.data)
        self.assertIn(b"$18,750.00", detail.data)
        self.assertIn(b"Oil change", detail.data)

        with self.app.app_context():
            record_id = Vehicle.query.one().service_records[0].id
        receipt = self.client.get(f"/receipts/{record_id}")
        try:
            self.assertEqual(receipt.status_code, 200)
            self.assertIn("attachment", receipt.headers["Content-Disposition"])
            self.assertEqual(receipt.data, b"test receipt")
        finally:
            receipt.close()

    def test_receipts_and_vehicle_records_are_owner_scoped(self):
        self.login()
        self.add_vehicle()
        with self.app.app_context():
            owner = User(username="different-owner")
            owner.set_password("different-password-long")
            db.session.add(owner)
            db.session.flush()
            vehicle = Vehicle(owner_id=owner.id, nickname="Private car")
            db.session.add(vehicle)
            db.session.commit()
            vehicle_id = vehicle.id
            record = ServiceRecord(
                vehicle_id=vehicle_id,
                title="Private repair",
                category="Repair",
                completed_on=date.today(),
                cost=0,
                receipt_filename="private.pdf",
                receipt_storage_name="private.pdf",
            )
            db.session.add(record)
            db.session.commit()
            record_id = record.id

        self.assertEqual(self.client.get(f"/vehicles/{vehicle_id}").status_code, 404)
        self.assertEqual(self.client.get(f"/receipts/{record_id}").status_code, 404)

    def test_vehicle_can_be_updated_and_deleted(self):
        self.login()
        self.add_vehicle()
        with self.app.app_context():
            vehicle_id = Vehicle.query.one().id

        update = self.client.post(
            f"/vehicles/{vehicle_id}/edit",
            data={
                "nickname": "Bluebird GT",
                "year": "2020",
                "make": "Example",
                "model": "Commuter",
                "vehicle_type": "Car",
                "vin": "",
                "license_plate": "ABC123",
            },
        )
        self.assertEqual(update.status_code, 302)
        self.assertIn(b"Bluebird GT", self.client.get("/").data)

        delete = self.client.post(f"/vehicles/{vehicle_id}/delete")
        self.assertEqual(delete.status_code, 302)
        dashboard = self.client.get("/")
        self.assertIn(b"0 in your garage", dashboard.data)
        self.assertIn(b"Start your garage", dashboard.data)

    def test_service_rejects_unsupported_receipt_types(self):
        self.login()
        self.add_vehicle()
        with self.app.app_context():
            vehicle_id = Vehicle.query.one().id

        response = self.client.post(
            f"/vehicles/{vehicle_id}/service/new",
            data={
                "title": "Oil change",
                "category": "Maintenance",
                "completed_on": date.today().isoformat(),
                "odometer": "",
                "cost": "40",
                "notes": "",
                "receipt": (io.BytesIO(b"not an image"), "receipt.exe"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Use a PDF or supported image", response.data)

    def test_reminders_require_a_date_or_mileage(self):
        self.login()
        self.add_vehicle()
        with self.app.app_context():
            vehicle_id = Vehicle.query.one().id

        invalid = self.client.post(
            f"/vehicles/{vehicle_id}/reminders/new",
            data={"title": "Tire rotation", "due_date": "", "due_odometer": ""},
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertIn(b"Enter a due date", invalid.data)

        valid = self.client.post(
            f"/vehicles/{vehicle_id}/reminders/new",
            data={
                "title": "Tire rotation",
                "due_date": (date.today() + timedelta(days=10)).isoformat(),
                "due_odometer": "35000",
                "notes": "",
            },
        )
        self.assertEqual(valid.status_code, 302)

    def test_reminder_status_and_latest_manual_value(self):
        today = date.today()
        overdue = Reminder(title="Oil", due_date=today - timedelta(days=1))
        due_soon = Reminder(title="Tires", due_date=today + timedelta(days=10))
        mileage_due = Reminder(title="Brakes", due_odometer=33500)
        upcoming = Reminder(title="Inspection", due_date=today + timedelta(days=60))

        self.assertEqual(reminder_status(overdue, 30000), "Overdue")
        self.assertEqual(reminder_status(due_soon, 30000), "Due soon")
        self.assertEqual(reminder_status(mileage_due, 33000), "Due soon")
        self.assertEqual(reminder_status(upcoming, 30000), "Upcoming")

        earlier = ValueEntry(amount=10000, valued_on=today - timedelta(days=30))
        latest = ValueEntry(amount=9000, valued_on=today)
        vehicle = Vehicle(value_entries=[earlier, latest])
        self.assertIs(vehicle.latest_value, latest)


if __name__ == "__main__":
    unittest.main()
