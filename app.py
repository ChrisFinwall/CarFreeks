import os
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm, CSRFProtect
from sqlalchemy import Numeric
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from wtforms import (
    DateField,
    DecimalField,
    FileField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    InputRequired,
    Length,
    NumberRange,
    Optional,
)


BASE_DIR = Path(__file__).resolve().parent
ALLOWED_RECEIPT_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".heic"}

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    nickname = db.Column(db.String(80), nullable=False)
    year = db.Column(db.Integer)
    make = db.Column(db.String(80))
    model = db.Column(db.String(80))
    vehicle_type = db.Column(db.String(32), nullable=False, default="Car")
    vin = db.Column(db.String(32))
    license_plate = db.Column(db.String(24))
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    odometer_entries = db.relationship(
        "OdometerEntry", backref="vehicle", cascade="all, delete-orphan"
    )
    service_records = db.relationship(
        "ServiceRecord", backref="vehicle", cascade="all, delete-orphan"
    )
    value_entries = db.relationship(
        "ValueEntry", backref="vehicle", cascade="all, delete-orphan"
    )
    reminders = db.relationship(
        "Reminder", backref="vehicle", cascade="all, delete-orphan"
    )

    @property
    def current_odometer(self):
        latest = max(
            self.odometer_entries,
            key=lambda entry: (entry.recorded_on, entry.id or 0),
            default=None,
        )
        return latest.reading if latest else None

    @property
    def latest_value(self):
        return max(
            self.value_entries,
            key=lambda entry: (entry.valued_on, entry.id or 0),
            default=None,
        )


class OdometerEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicle.id"), nullable=False)
    reading = db.Column(db.Integer, nullable=False)
    recorded_on = db.Column(db.Date, nullable=False, default=date.today)
    note = db.Column(db.String(250))


class ServiceRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicle.id"), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(24), nullable=False)
    completed_on = db.Column(db.Date, nullable=False, default=date.today)
    odometer = db.Column(db.Integer)
    cost = db.Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    notes = db.Column(db.Text)
    receipt_filename = db.Column(db.String(255))
    receipt_storage_name = db.Column(db.String(64))


class ValueEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicle.id"), nullable=False)
    amount = db.Column(Numeric(10, 2), nullable=False)
    valued_on = db.Column(db.Date, nullable=False, default=date.today)
    source = db.Column(db.String(120))
    notes = db.Column(db.Text)


class Reminder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicle.id"), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    due_date = db.Column(db.Date)
    due_odometer = db.Column(db.Integer)
    notes = db.Column(db.Text)
    completed = db.Column(db.Boolean, nullable=False, default=False)


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(max=64)])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Sign in")


class VehicleForm(FlaskForm):
    nickname = StringField("Vehicle name", validators=[DataRequired(), Length(max=80)])
    year = IntegerField("Year", validators=[Optional(), NumberRange(min=1886, max=2100)])
    make = StringField("Make", validators=[Optional(), Length(max=80)])
    model = StringField("Model", validators=[Optional(), Length(max=80)])
    vehicle_type = SelectField(
        "Type",
        choices=[
            ("Car", "Car"),
            ("SUV", "SUV"),
            ("Truck", "Truck"),
            ("Van", "Van"),
            ("Motorcycle", "Motorcycle"),
            ("Other", "Other"),
        ],
        validators=[DataRequired()],
    )
    vin = StringField("VIN", validators=[Optional(), Length(max=32)])
    license_plate = StringField("License plate", validators=[Optional(), Length(max=24)])
    submit = SubmitField("Save vehicle")


class OdometerForm(FlaskForm):
    reading = IntegerField(
        "Odometer reading", validators=[InputRequired(), NumberRange(min=0)]
    )
    recorded_on = DateField("Reading date", validators=[InputRequired()], default=date.today)
    note = StringField("Note", validators=[Optional(), Length(max=250)])
    submit = SubmitField("Add reading")


class ServiceForm(FlaskForm):
    title = StringField("Service or repair", validators=[DataRequired(), Length(max=120)])
    category = SelectField(
        "Category",
        choices=[("Maintenance", "Maintenance"), ("Repair", "Repair")],
        validators=[DataRequired()],
    )
    completed_on = DateField("Date completed", validators=[InputRequired()], default=date.today)
    odometer = IntegerField(
        "Odometer reading", validators=[Optional(), NumberRange(min=0)]
    )
    cost = DecimalField(
        "Cost", places=2, validators=[InputRequired(), NumberRange(min=Decimal("0"))]
    )
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=4000)])
    receipt = FileField("Receipt (PDF or image)")
    submit = SubmitField("Save record")


class ValueForm(FlaskForm):
    amount = DecimalField(
        "Estimated value",
        places=2,
        validators=[InputRequired(), NumberRange(min=Decimal("0.01"))],
    )
    valued_on = DateField("Value date", validators=[InputRequired()], default=date.today)
    source = StringField("Source", validators=[Optional(), Length(max=120)])
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=4000)])
    submit = SubmitField("Save value")


class ReminderForm(FlaskForm):
    title = StringField("Maintenance item", validators=[DataRequired(), Length(max=120)])
    due_date = DateField("Due date", validators=[Optional()])
    due_odometer = IntegerField(
        "Due at odometer reading", validators=[Optional(), NumberRange(min=0)]
    )
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=4000)])
    submit = SubmitField("Save reminder")

    def validate(self, extra_validators=None):
        valid = super().validate(extra_validators=extra_validators)
        if self.due_date.data is None and self.due_odometer.data is None:
            self.due_date.errors.append("Enter a due date, an odometer reading, or both.")
            return False
        return valid


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def create_app(test_config=None):
    app = Flask(__name__)
    data_dir = Path(os.environ.get("CARFREEKS_DATA_DIR", BASE_DIR / "data"))
    database_url = os.environ.get("CARFREEKS_DATABASE_URL")
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("CARFREEKS_SECRET_KEY"),
        SQLALCHEMY_DATABASE_URI=database_url or f"sqlite:///{data_dir / 'carfreeks.db'}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"connect_args": {"check_same_thread": False}},
        CARFREEKS_DATA_DIR=str(data_dir),
        UPLOAD_FOLDER=str(data_dir / "receipts"),
        ADMIN_USERNAME=os.environ.get("CARFREEKS_ADMIN_USERNAME", "owner").strip(),
        ADMIN_PASSWORD=os.environ.get("CARFREEKS_ADMIN_PASSWORD"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("CARFREEKS_COOKIE_SECURE", "").lower()
        in {"1", "true", "yes"},
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)

    if not app.config["SECRET_KEY"]:
        raise RuntimeError("Set CARFREEKS_SECRET_KEY to a long, random secret.")
    if not app.config["ADMIN_USERNAME"]:
        raise RuntimeError("CARFREEKS_ADMIN_USERNAME must not be empty.")
    if not app.config["ADMIN_PASSWORD"] or len(app.config["ADMIN_PASSWORD"]) < 12:
        raise RuntimeError(
            "Set CARFREEKS_ADMIN_PASSWORD to a password of at least 12 characters."
        )

    Path(app.config["CARFREEKS_DATA_DIR"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "login"
    login_manager.login_message = "Sign in to view your vehicles."
    login_manager.login_message_category = "info"
    csrf.init_app(app)

    with app.app_context():
        db.create_all()
        if db.session.query(User.id).first() is None:
            owner = User(username=app.config["ADMIN_USERNAME"])
            owner.set_password(app.config["ADMIN_PASSWORD"])
            db.session.add(owner)
            db.session.commit()

    register_routes(app)
    return app


def get_vehicle_or_404(vehicle_id):
    return Vehicle.query.filter_by(id=vehicle_id, owner_id=current_user.id).first_or_404()


def reminder_status(reminder, current_odometer):
    if reminder.completed:
        return "Completed"
    if reminder.due_date and reminder.due_date < date.today():
        return "Overdue"
    if (
        reminder.due_odometer is not None
        and current_odometer is not None
        and reminder.due_odometer < current_odometer
    ):
        return "Overdue"
    if reminder.due_date and reminder.due_date <= date.today() + timedelta(days=30):
        return "Due soon"
    if (
        reminder.due_odometer is not None
        and current_odometer is not None
        and reminder.due_odometer <= current_odometer + 500
    ):
        return "Due soon"
    return "Upcoming"


def register_routes(app):
    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(username=form.username.data.strip()).first()
            if user and user.check_password(form.password.data):
                login_user(user)
                return redirect(url_for("dashboard"))
            flash("The username or password was not recognized.", "error")
        return render_template("login.html", form=form)

    @app.post("/logout")
    @login_required
    def logout():
        logout_user()
        flash("You have signed out.", "info")
        return redirect(url_for("login"))

    @app.get("/")
    @login_required
    def dashboard():
        vehicles = Vehicle.query.filter_by(owner_id=current_user.id).order_by(
            Vehicle.nickname
        ).all()
        reminders = []
        for vehicle in vehicles:
            for reminder in vehicle.reminders:
                if not reminder.completed:
                    reminders.append(
                        (vehicle, reminder, reminder_status(reminder, vehicle.current_odometer))
                    )
        reminders.sort(
            key=lambda item: (
                item[1].due_date or date.max,
                item[1].due_odometer or 2**63,
                item[0].nickname.lower(),
            )
        )
        return render_template(
            "dashboard.html", vehicles=vehicles, reminders=reminders[:8]
        )

    @app.route("/vehicles/new", methods=["GET", "POST"])
    @login_required
    def vehicle_new():
        form = VehicleForm()
        if form.validate_on_submit():
            vehicle = Vehicle(owner_id=current_user.id)
            form.populate_obj(vehicle)
            db.session.add(vehicle)
            db.session.commit()
            flash(f"{vehicle.nickname} was added.", "success")
            return redirect(url_for("vehicle_detail", vehicle_id=vehicle.id))
        return render_template("vehicle_form.html", form=form, heading="Add a vehicle")

    @app.route("/vehicles/<int:vehicle_id>/edit", methods=["GET", "POST"])
    @login_required
    def vehicle_edit(vehicle_id):
        vehicle = get_vehicle_or_404(vehicle_id)
        form = VehicleForm(obj=vehicle)
        if form.validate_on_submit():
            form.populate_obj(vehicle)
            db.session.commit()
            flash(f"{vehicle.nickname} was updated.", "success")
            return redirect(url_for("vehicle_detail", vehicle_id=vehicle.id))
        return render_template("vehicle_form.html", form=form, heading="Edit vehicle")

    @app.post("/vehicles/<int:vehicle_id>/delete")
    @login_required
    def vehicle_delete(vehicle_id):
        vehicle = get_vehicle_or_404(vehicle_id)
        receipt_names = [
            record.receipt_storage_name
            for record in vehicle.service_records
            if record.receipt_storage_name
        ]
        name = vehicle.nickname
        db.session.delete(vehicle)
        db.session.commit()
        for stored_name in receipt_names:
            (Path(app.config["UPLOAD_FOLDER"]) / stored_name).unlink(missing_ok=True)
        flash(f"{name} and its records were deleted.", "success")
        return redirect(url_for("dashboard"))

    @app.get("/vehicles/<int:vehicle_id>")
    @login_required
    def vehicle_detail(vehicle_id):
        vehicle = get_vehicle_or_404(vehicle_id)
        records = sorted(
            vehicle.service_records,
            key=lambda item: (item.completed_on, item.id),
            reverse=True,
        )
        values = sorted(
            vehicle.value_entries,
            key=lambda item: (item.valued_on, item.id),
            reverse=True,
        )
        odometer_entries = sorted(
            vehicle.odometer_entries,
            key=lambda item: (item.recorded_on, item.id),
            reverse=True,
        )
        reminders = sorted(
            vehicle.reminders,
            key=lambda item: (
                item.completed,
                item.due_date or date.max,
                item.due_odometer or 2**63,
                item.id,
            ),
        )
        return render_template(
            "vehicle_detail.html",
            vehicle=vehicle,
            records=records,
            values=values,
            odometer_entries=odometer_entries,
            reminders=reminders,
            reminder_status=reminder_status,
        )

    @app.route("/vehicles/<int:vehicle_id>/odometer/new", methods=["GET", "POST"])
    @login_required
    def odometer_new(vehicle_id):
        vehicle = get_vehicle_or_404(vehicle_id)
        form = OdometerForm()
        if form.validate_on_submit():
            entry = OdometerEntry(vehicle_id=vehicle.id)
            form.populate_obj(entry)
            db.session.add(entry)
            db.session.commit()
            flash("Odometer reading saved.", "success")
            return redirect(url_for("vehicle_detail", vehicle_id=vehicle.id))
        return render_template(
            "simple_form.html",
            form=form,
            heading=f"Add mileage · {vehicle.nickname}",
            back_url=url_for("vehicle_detail", vehicle_id=vehicle.id),
        )

    @app.route("/vehicles/<int:vehicle_id>/service/new", methods=["GET", "POST"])
    @login_required
    def service_new(vehicle_id):
        vehicle = get_vehicle_or_404(vehicle_id)
        form = ServiceForm()
        if form.validate_on_submit():
            receipt = form.receipt.data
            original_name = secure_filename(receipt.filename) if receipt else ""
            if receipt and original_name:
                extension = Path(original_name).suffix.lower()
                if extension not in ALLOWED_RECEIPT_EXTENSIONS:
                    flash("Use a PDF or supported image file for a receipt.", "error")
                    return render_template(
                        "simple_form.html",
                        form=form,
                        heading=f"Add service or repair · {vehicle.nickname}",
                        back_url=url_for("vehicle_detail", vehicle_id=vehicle.id),
                    )
                stored_name = f"{uuid.uuid4().hex}{extension}"
                receipt.save(Path(app.config["UPLOAD_FOLDER"]) / stored_name)
            else:
                original_name = None
                stored_name = None

            record = ServiceRecord(vehicle_id=vehicle.id)
            form.populate_obj(record)
            record.receipt_filename = original_name
            record.receipt_storage_name = stored_name
            db.session.add(record)
            db.session.commit()
            flash("Service or repair record saved.", "success")
            return redirect(url_for("vehicle_detail", vehicle_id=vehicle.id))
        return render_template(
            "simple_form.html",
            form=form,
            heading=f"Add service or repair · {vehicle.nickname}",
            back_url=url_for("vehicle_detail", vehicle_id=vehicle.id),
        )

    @app.get("/receipts/<int:record_id>")
    @login_required
    def receipt_download(record_id):
        record = (
            ServiceRecord.query.join(Vehicle)
            .filter(
                ServiceRecord.id == record_id,
                Vehicle.owner_id == current_user.id,
            )
            .first_or_404()
        )
        if not record.receipt_storage_name:
            abort(404)
        return send_from_directory(
            app.config["UPLOAD_FOLDER"],
            record.receipt_storage_name,
            as_attachment=True,
            download_name=record.receipt_filename or "receipt",
        )

    @app.route("/vehicles/<int:vehicle_id>/value/new", methods=["GET", "POST"])
    @login_required
    def value_new(vehicle_id):
        vehicle = get_vehicle_or_404(vehicle_id)
        form = ValueForm()
        if form.validate_on_submit():
            entry = ValueEntry(vehicle_id=vehicle.id)
            form.populate_obj(entry)
            db.session.add(entry)
            db.session.commit()
            flash("Vehicle value saved to history.", "success")
            return redirect(url_for("vehicle_detail", vehicle_id=vehicle.id))
        return render_template(
            "simple_form.html",
            form=form,
            heading=f"Record estimated value · {vehicle.nickname}",
            back_url=url_for("vehicle_detail", vehicle_id=vehicle.id),
        )

    @app.route("/vehicles/<int:vehicle_id>/reminders/new", methods=["GET", "POST"])
    @login_required
    def reminder_new(vehicle_id):
        vehicle = get_vehicle_or_404(vehicle_id)
        form = ReminderForm()
        if form.validate_on_submit():
            reminder = Reminder(vehicle_id=vehicle.id)
            form.populate_obj(reminder)
            db.session.add(reminder)
            db.session.commit()
            flash("Maintenance reminder saved.", "success")
            return redirect(url_for("vehicle_detail", vehicle_id=vehicle.id))
        return render_template(
            "simple_form.html",
            form=form,
            heading=f"Add maintenance reminder · {vehicle.nickname}",
            back_url=url_for("vehicle_detail", vehicle_id=vehicle.id),
        )

    @app.post("/vehicles/<int:vehicle_id>/reminders/<int:reminder_id>/toggle")
    @login_required
    def reminder_toggle(vehicle_id, reminder_id):
        vehicle = get_vehicle_or_404(vehicle_id)
        reminder = Reminder.query.filter_by(
            id=reminder_id, vehicle_id=vehicle.id
        ).first_or_404()
        reminder.completed = not reminder.completed
        db.session.commit()
        flash(
            "Reminder marked complete." if reminder.completed else "Reminder reopened.",
            "success",
        )
        return redirect(url_for("vehicle_detail", vehicle_id=vehicle.id))

    @app.errorhandler(413)
    def upload_too_large(_error):
        flash("Receipt files must be 10 MB or smaller.", "error")
        return redirect(url_for("dashboard"))


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=8080)
