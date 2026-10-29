import os
import sqlite3
from datetime import date, datetime, time, timedelta

from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, g
)

# --------------------------------------------------
# APPLICATION CONFIGURATION
# --------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "shifts.db")

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY", "local-development-key"
)


# --------------------------------------------------
# DATABASE CONNECTION
# --------------------------------------------------

def get_db():

    if "db" not in g:

        g.db = sqlite3.connect(DATABASE)

        g.db.row_factory = sqlite3.Row

        g.db.execute("PRAGMA foreign_keys = ON")

    return g.db


@app.teardown_appcontext
def close_db(error=None):

    db = g.pop("db", None)

    if db is not None:
        db.close()


# --------------------------------------------------
# DATABASE INITIALIZATION
# --------------------------------------------------

def init_db():

    db = sqlite3.connect(DATABASE)

    db.execute("PRAGMA foreign_keys = ON")

    db.executescript("""

        CREATE TABLE IF NOT EXISTS employees (

            employee_id TEXT PRIMARY KEY,
            name TEXT NOT NULL

        );


        CREATE TABLE IF NOT EXISTS shifts (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            shift_date TEXT NOT NULL,

            start_time TEXT NOT NULL,

            end_time TEXT NOT NULL,

            starts_at TEXT NOT NULL,

            ends_at TEXT NOT NULL,

            is_overnight INTEGER NOT NULL DEFAULT 0

        );


        CREATE TABLE IF NOT EXISTS assignments (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            employee_id TEXT NOT NULL,

            shift_id INTEGER NOT NULL,

            UNIQUE(employee_id, shift_id),

            FOREIGN KEY(employee_id)
                REFERENCES employees(employee_id)
                ON DELETE CASCADE,

            FOREIGN KEY(shift_id)
                REFERENCES shifts(id)
                ON DELETE CASCADE

        );

    """)

    db.commit()
    db.close()


# --------------------------------------------------
# SHIFT TIME VALIDATION
# --------------------------------------------------

def parse_shift_times(
    shift_date,
    start_time,
    end_time,
    overnight
):

    try:

        shift_day = date.fromisoformat(shift_date)

        start = time.fromisoformat(start_time)

        end = time.fromisoformat(end_time)

    except (ValueError, TypeError):

        raise ValueError(
            "Please enter a valid date and time."
        )

    if start == end:

        raise ValueError(
            "Start time and end time cannot be the same."
        )

    if overnight and end > start:

        raise ValueError(
            "For overnight shifts, end time must be earlier than start time."
        )

    if not overnight and end < start:

        raise ValueError(
            "End time must be after start time. Select overnight for next-day shifts."
        )

    starts_at = datetime.combine(
        shift_day, start
    )

    ends_at = datetime.combine(
        shift_day, end
    )

    if overnight:

        ends_at += timedelta(days=1)

    return (
        starts_at.isoformat(timespec="seconds"),
        ends_at.isoformat(timespec="seconds")
    )


# --------------------------------------------------
# SCHEDULING CONFLICT DETECTION
# --------------------------------------------------

def has_conflict(
    db,
    employee_id,
    new_start,
    new_end
):

    result = db.execute("""

        SELECT 1

        FROM assignments a

        JOIN shifts s
        ON s.id = a.shift_id

        WHERE a.employee_id = ?

        AND s.starts_at < ?

        AND ? < s.ends_at

        LIMIT 1

    """, (

        employee_id,
        new_end,
        new_start

    )).fetchone()

    return result is not None


# --------------------------------------------------
# LOAD DASHBOARD DATA
# --------------------------------------------------

def load_page_data(db, selected_date=None):

    employees = db.execute("""

        SELECT
            e.employee_id,
            e.name,
            COUNT(a.id) AS shift_count

        FROM employees e

        LEFT JOIN assignments a
        ON a.employee_id = e.employee_id

        GROUP BY e.employee_id, e.name

        ORDER BY e.name COLLATE NOCASE

    """).fetchall()


    query = """

        SELECT
            s.*,
            COUNT(a.id) AS assigned_count

        FROM shifts s

        LEFT JOIN assignments a
        ON a.shift_id = s.id

    """

    params = []

    if selected_date:

        query += " WHERE s.shift_date = ?"

        params.append(selected_date)

    query += """

        GROUP BY s.id

        ORDER BY s.starts_at DESC

    """

    shifts = db.execute(
        query, params
    ).fetchall()


    assignments = db.execute("""

        SELECT
            a.id AS assignment_id,
            a.shift_id,
            e.employee_id,
            e.name

        FROM assignments a

        JOIN employees e
        ON e.employee_id = a.employee_id

        ORDER BY e.name COLLATE NOCASE

    """).fetchall()


    assigned_by_shift = {}

    for item in assignments:

        assigned_by_shift.setdefault(
            item["shift_id"], []
        ).append(item)


    return (
        employees,
        shifts,
        assigned_by_shift
    )


# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------

@app.route("/", methods=["GET"])
def index():

    selected_date = request.args.get(
        "date", ""
    ).strip()

    if selected_date:

        try:

            date.fromisoformat(selected_date)

        except ValueError:

            flash(
                "Please select a valid date.",
                "error"
            )

            selected_date = ""


    db = get_db()

    employees, shifts, assigned_by_shift = load_page_data(
        db,
        selected_date or None
    )


    employee_count = db.execute(
        "SELECT COUNT(*) FROM employees"
    ).fetchone()[0]


    shift_count = db.execute(
        "SELECT COUNT(*) FROM shifts"
    ).fetchone()[0]


    assignment_count = db.execute(
        "SELECT COUNT(*) FROM assignments"
    ).fetchone()[0]


    return render_template(

        "index.html",

        employees=employees,

        shifts=shifts,

        assigned_by_shift=assigned_by_shift,

        selected_date=selected_date,

        employee_count=employee_count,

        shift_count=shift_count,

        assignment_count=assignment_count,

        today=date.today().isoformat()

    )


# --------------------------------------------------
# ADD EMPLOYEE
# --------------------------------------------------

@app.route("/employees", methods=["POST"])
def add_employee():

    employee_id = request.form.get(
        "employee_id", ""
    ).strip()

    name = request.form.get(
        "name", ""
    ).strip()


    if not employee_id or not name:

        flash(
            "Employee ID and name are required.",
            "error"
        )

        return redirect(url_for("index"))


    if len(employee_id) > 30 or len(name) > 100:

        flash(
            "Employee ID must be within 30 characters and name within 100 characters.",
            "error"
        )

        return redirect(url_for("index"))


    db = get_db()

    try:

        db.execute("""

            INSERT INTO employees
            (employee_id, name)

            VALUES (?, ?)

        """, (employee_id, name))

        db.commit()

        flash(
            f"Employee {employee_id} added successfully.",
            "success"
        )

    except sqlite3.IntegrityError:

        flash(
            "This Employee ID already exists.",
            "error"
        )


    return redirect(url_for("index"))


# --------------------------------------------------
# CREATE SHIFT
# --------------------------------------------------

@app.route("/shifts", methods=["POST"])
def create_shift():

    shift_date = request.form.get(
        "shift_date", ""
    ).strip()

    start_time = request.form.get(
        "start_time", ""
    ).strip()

    end_time = request.form.get(
        "end_time", ""
    ).strip()

    overnight = (
        request.form.get("overnight") == "on"
    )


    try:

        starts_at, ends_at = parse_shift_times(
            shift_date,
            start_time,
            end_time,
            overnight
        )

    except ValueError as error:

        flash(str(error), "error")

        return redirect(url_for("index"))


    db = get_db()

    db.execute("""

        INSERT INTO shifts (

            shift_date,
            start_time,
            end_time,
            starts_at,
            ends_at,
            is_overnight

        )

        VALUES (?, ?, ?, ?, ?, ?)

    """, (

        shift_date,
        start_time,
        end_time,
        starts_at,
        ends_at,
        int(overnight)

    ))

    db.commit()

    flash(
        "New shift created successfully.",
        "success"
    )

    return redirect(url_for("index"))


# --------------------------------------------------
# ASSIGN EMPLOYEE TO SHIFT
# --------------------------------------------------

@app.route("/assign", methods=["POST"])
def assign_employee():

    employee_id = request.form.get(
        "employee_id", ""
    ).strip()

    try:

        shift_id = int(
            request.form.get("shift_id", "")
        )

    except (ValueError, TypeError):

        flash(
            "Please select a valid shift.",
            "error"
        )

        return redirect(url_for("index"))


    db = get_db()


    employee = db.execute("""

        SELECT employee_id

        FROM employees

        WHERE employee_id = ?

    """, (employee_id,)).fetchone()


    shift = db.execute("""

        SELECT *

        FROM shifts

        WHERE id = ?

    """, (shift_id,)).fetchone()


    if employee is None or shift is None:

        flash(
            "Employee or shift not found.",
            "error"
        )

        return redirect(url_for("index"))


    already_assigned = db.execute("""

        SELECT 1

        FROM assignments

        WHERE employee_id = ?

        AND shift_id = ?

    """, (employee_id, shift_id)).fetchone()


    if already_assigned:

        flash(
            "Employee is already assigned to this shift.",
            "error"
        )

        return redirect(url_for("index"))


    if has_conflict(
        db,
        employee_id,
        shift["starts_at"],
        shift["ends_at"]
    ):

        flash(

            f"Scheduling conflict: {employee_id} already has an overlapping shift.",

            "error"

        )

        return redirect(url_for("index"))


    db.execute("""

        INSERT INTO assignments
        (employee_id, shift_id)

        VALUES (?, ?)

    """, (employee_id, shift_id))


    db.commit()

    flash(
        f"Employee {employee_id} assigned successfully.",
        "success"
    )

    return redirect(url_for("index"))


# --------------------------------------------------
# REMOVE EMPLOYEE ASSIGNMENT
# --------------------------------------------------

@app.route(
    "/assignments/<int:assignment_id>/delete",
    methods=["POST"]
)
def remove_assignment(assignment_id):

    db = get_db()

    result = db.execute("""

        DELETE FROM assignments

        WHERE id = ?

    """, (assignment_id,))


    db.commit()

    if result.rowcount:

        flash(
            "Employee assignment removed successfully.",
            "success"
        )

    else:

        flash(
            "Assignment not found.",
            "error"
        )


    return redirect(url_for("index"))


# --------------------------------------------------
# DELETE SHIFT
# --------------------------------------------------

@app.route(
    "/shifts/<int:shift_id>/delete",
    methods=["POST"]
)
def delete_shift(shift_id):

    db = get_db()

    result = db.execute("""

        DELETE FROM shifts

        WHERE id = ?

    """, (shift_id,))


    db.commit()

    if result.rowcount:

        flash(
            "Shift deleted successfully.",
            "success"
        )

    else:

        flash(
            "Shift not found.",
            "error"
        )


    return redirect(url_for("index"))


# --------------------------------------------------
# DELETE EMPLOYEE
# --------------------------------------------------

@app.route(
    "/employees/<employee_id>/delete",
    methods=["POST"]
)
def delete_employee(employee_id):

    db = get_db()

    result = db.execute("""

        DELETE FROM employees

        WHERE employee_id = ?

    """, (employee_id,))


    db.commit()

    if result.rowcount:

        flash(
            "Employee and their assignments deleted successfully.",
            "success"
        )

    else:

        flash(
            "Employee not found.",
            "error"
        )


    return redirect(url_for("index"))


# --------------------------------------------------
# APPLICATION ENTRY POINT
# --------------------------------------------------

if __name__ == "__main__":

    init_db()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )

else:

    init_db()