import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="RTT ERP System", layout="wide")

# =========================
# DATABASE CONNECTION - SUPABASE POSTGRESQL
# =========================
DB_URL = "postgresql://postgres.lytcnpytanxegiacwbvq:Mohi777Mohi2026@aws-1-eu-west-2.pooler.supabase.com:5432/postgres"


def get_conn():
    return psycopg2.connect(DB_URL)


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def add_column_if_not_exists(cursor, table_name, column_name, column_type):
    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
    """, (table_name, column_name))
    if cursor.fetchone() is None:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


# =========================
# DATABASE INITIALIZATION
# =========================
def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS vendors (
        id SERIAL PRIMARY KEY,
        vendor_name TEXT UNIQUE NOT NULL,
        phone TEXT,
        email TEXT,
        address TEXT,
        created_at TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id SERIAL PRIMARY KEY,
        item_name TEXT UNIQUE NOT NULL,
        unit TEXT,
        description TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS purchase_requisitions (
        id SERIAL PRIMARY KEY,
        pr_no TEXT UNIQUE,
        requester_name TEXT,
        department TEXT,
        project_name TEXT,
        item_name TEXT,
        quantity NUMERIC,
        unit TEXT,
        required_date TEXT,
        reason TEXT,
        priority TEXT,
        approval_status TEXT,
        pr_status TEXT,
        manager_approval_status TEXT,
        manager_approved_by TEXT,
        manager_approved_at TEXT,
        manager_comment TEXT,
        created_at TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS rfqs (
        id SERIAL PRIMARY KEY,
        rfq_no TEXT UNIQUE,
        pr_no TEXT,
        item_name TEXT,
        quantity NUMERIC,
        unit TEXT,
        required_date TEXT,
        status TEXT,
        created_at TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS quotations (
        id SERIAL PRIMARY KEY,
        rfq_no TEXT,
        vendor TEXT,
        quoted_price NUMERIC,
        currency TEXT,
        delivery_days INTEGER,
        notes TEXT,
        created_at TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS purchase_orders (
        id SERIAL PRIMARY KEY,
        po_no TEXT UNIQUE,
        rfq_no TEXT,
        vendor TEXT,
        item_name TEXT,
        quantity NUMERIC,
        unit TEXT,
        unit_price NUMERIC,
        currency TEXT,
        total_amount NUMERIC,
        approval_status TEXT,
        po_status TEXT,
        created_at TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS invoices (
        id SERIAL PRIMARY KEY,
        invoice_no TEXT UNIQUE,
        po_no TEXT,
        vendor TEXT,
        invoice_date TEXT,
        invoice_amount NUMERIC,
        currency TEXT,
        invoice_status TEXT,
        notes TEXT,
        created_at TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id SERIAL PRIMARY KEY,
        payment_no TEXT UNIQUE,
        invoice_no TEXT,
        po_no TEXT,
        vendor TEXT,
        payment_date TEXT,
        payment_amount NUMERIC,
        currency TEXT,
        payment_method TEXT,
        reference_no TEXT,
        notes TEXT,
        created_at TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT
    )
    """)

    default_users = [
        ("admin", "admin123", "Admin", "Active", now_text()),
        ("pruser", "pr123", "PR User", "Active", now_text()),
        ("procurement", "proc123", "Procurement", "Active", now_text()),
        ("finance", "fin123", "Finance", "Active", now_text()),
        ("manager", "mgr123", "Manager", "Active", now_text()),
    ]

    for user in default_users:
        c.execute("""
        INSERT INTO users (username, password, role, status, created_at)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (username) DO NOTHING
        """, user)

    conn.commit()
    conn.close()


# =========================
# HELPERS
# =========================
def fetch_df(table):
    conn = get_conn()
    df = pd.read_sql_query(f"SELECT * FROM {table} ORDER BY id", conn)
    conn.close()
    return df


def fetch_list(table, column):
    conn = get_conn()
    df = pd.read_sql_query(f"SELECT {column} FROM {table} ORDER BY {column}", conn)
    conn.close()
    if df.empty:
        return []
    return df[column].dropna().astype(str).tolist()


def generate_no(prefix, table):
    conn = get_conn()
    c = conn.cursor()
    c.execute(f"SELECT COUNT(*) FROM {table}")
    count = c.fetchone()[0] + 1
    conn.close()
    return f"{prefix}-{count:04d}"


def check_login(username, password):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
    SELECT username, role FROM users
    WHERE username = %s AND password = %s AND status = 'Active'
    """, (username, password))
    user = c.fetchone()
    conn.close()
    return user


def insert_vendor(name, phone, email, address):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("""
        INSERT INTO vendors (vendor_name, phone, email, address, created_at)
        VALUES (%s, %s, %s, %s, %s)
        """, (name, phone, email, address, now_text()))
        conn.commit()
        st.success("Vendor saved successfully")
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        st.warning("Vendor already exists")
    finally:
        conn.close()


def insert_item(name, unit, description):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("""
        INSERT INTO items (item_name, unit, description)
        VALUES (%s, %s, %s)
        """, (name, unit, description))
        conn.commit()
        st.success("Item saved successfully")
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        st.warning("Item already exists")
    finally:
        conn.close()


def get_invoice_balance(invoice_no):
    invoices = fetch_df("invoices")
    payments = fetch_df("payments")
    invoice_row = invoices[invoices["invoice_no"] == invoice_no]
    if invoice_row.empty:
        return 0
    invoice_amount = float(invoice_row.iloc[0]["invoice_amount"])
    paid_amount = payments[payments["invoice_no"] == invoice_no]["payment_amount"].astype(float).sum() if not payments.empty else 0
    return invoice_amount - paid_amount


def update_invoice_status(invoice_no):
    balance = get_invoice_balance(invoice_no)
    payments = fetch_df("payments")
    paid_amount = payments[payments["invoice_no"] == invoice_no]["payment_amount"].astype(float).sum() if not payments.empty else 0

    if balance <= 0:
        status = "Paid"
    elif paid_amount > 0:
        status = "Partially Paid"
    else:
        status = "Unpaid"

    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE invoices SET invoice_status = %s WHERE invoice_no = %s", (status, invoice_no))
    conn.commit()
    conn.close()


def update_record(table, record_id, data):
    conn = get_conn()
    c = conn.cursor()
    try:
        clean_data = {}
        for key, value in data.items():
            clean_data[key] = None if value == "" else value

        set_clause = ", ".join([f"{col} = %s" for col in clean_data.keys()])
        values = list(clean_data.values()) + [record_id]
        c.execute(f"UPDATE {table} SET {set_clause} WHERE id = %s", values)
        conn.commit()
        st.success("Record updated successfully")
    except Exception as e:
        conn.rollback()
        st.error(f"Update failed: {e}")
    finally:
        conn.close()


def delete_record(table, record_id):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute(f"DELETE FROM {table} WHERE id = %s", (record_id,))
        conn.commit()
        st.success("Record deleted successfully")
    except Exception as e:
        conn.rollback()
        st.error(f"Delete failed: {e}")
    finally:
        conn.close()


# =========================
# LOGIN
# =========================
def login_page():
    st.title("RTT ERP Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            user = check_login(username, password)
            if user:
                st.session_state.logged_in = True
                st.session_state.username = user[0]
                st.session_state.role = user[1]
                st.rerun()
            else:
                st.error("Invalid username, password, or inactive user")


# =========================
# START APP
# =========================
init_db()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "role" not in st.session_state:
    st.session_state.role = ""

if not st.session_state.logged_in:
    login_page()
    st.stop()

st.sidebar.success(f"Logged in as: {st.session_state.username} ({st.session_state.role})")

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.rerun()

role = st.session_state.role

if role == "Admin":
    menu_options = [
        "Dashboard", "User Management", "System Settings", "Vendors", "Items",
        "Create PR", "PR Approvals", "Create RFQ", "Add Quotation",
        "Compare Quotations", "Create PO", "PO Approvals", "Register Invoice",
        "Register Payment", "Accounts Payable", "Reports"
    ]
elif role == "PR User":
    menu_options = ["Dashboard", "Create PR", "Reports"]
elif role == "Procurement":
    menu_options = ["Dashboard", "Vendors", "Items", "Create RFQ", "Add Quotation", "Compare Quotations", "Create PO", "Reports"]
elif role == "Finance":
    menu_options = ["Dashboard", "Register Invoice", "Register Payment", "Accounts Payable", "Reports"]
elif role == "Manager":
    menu_options = ["Dashboard", "PR Approvals", "PO Approvals", "Reports"]
else:
    menu_options = ["Dashboard"]

menu = st.sidebar.radio("Main Menu", menu_options)

# =========================
# DASHBOARD
# =========================
if menu == "Dashboard":
    st.title("Executive Dashboard")
    st.caption("Live Procurement, Finance, and Approval Performance Overview")

    vendors = fetch_df("vendors")
    items = fetch_df("items")
    prs = fetch_df("purchase_requisitions")
    rfqs = fetch_df("rfqs")
    quotations = fetch_df("quotations")
    pos = fetch_df("purchase_orders")
    invoices = fetch_df("invoices")
    payments = fetch_df("payments")

    total_po_amount = pos["total_amount"].astype(float).sum() if not pos.empty else 0
    total_invoice_amount = invoices["invoice_amount"].astype(float).sum() if not invoices.empty else 0
    total_payment_amount = payments["payment_amount"].astype(float).sum() if not payments.empty else 0
    outstanding_balance = total_invoice_amount - total_payment_amount

    pending_prs = len(prs[prs["approval_status"] == "Pending"]) if not prs.empty else 0
    approved_prs = len(prs[prs["approval_status"] == "Approved"]) if not prs.empty else 0
    rejected_prs = len(prs[prs["approval_status"] == "Rejected"]) if not prs.empty else 0

    pending_pos = len(pos[pos["approval_status"] == "Pending"]) if not pos.empty else 0
    approved_pos = len(pos[pos["approval_status"] == "Approved"]) if not pos.empty else 0

    st.subheader("Key Performance Indicators")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total PRs", len(prs))
    c2.metric("Pending PRs", pending_prs)
    c3.metric("Approved PRs", approved_prs)
    c4.metric("Rejected PRs", rejected_prs)

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Vendors", len(vendors))
    c6.metric("Items", len(items))
    c7.metric("RFQs", len(rfqs))
    c8.metric("POs", len(pos))

    st.divider()
    st.subheader("Financial Overview")
    f1, f2, f3, f4 = st.columns(4)
    f1.metric("Total PO Amount", f"{total_po_amount:,.2f}")
    f2.metric("Total Invoices", f"{total_invoice_amount:,.2f}")
    f3.metric("Total Payments", f"{total_payment_amount:,.2f}")
    f4.metric("Outstanding Balance", f"{outstanding_balance:,.2f}")

    st.divider()
    left, right = st.columns(2)

    with left:
        st.subheader("PR Approval Status")
        st.bar_chart(pd.DataFrame({
            "Status": ["Pending", "Approved", "Rejected"],
            "Count": [pending_prs, approved_prs, rejected_prs]
        }), x="Status", y="Count")

    with right:
        st.subheader("PO Approval Status")
        st.bar_chart(pd.DataFrame({
            "Status": ["Pending", "Approved"],
            "Count": [pending_pos, approved_pos]
        }), x="Status", y="Count")

    st.divider()
    st.subheader("Latest Purchase Requisitions")
    st.dataframe(prs.tail(10), use_container_width=True)

    st.subheader("Latest Purchase Orders")
    st.dataframe(pos.tail(10), use_container_width=True)

    st.subheader("Latest Invoices")
    st.dataframe(invoices.tail(10), use_container_width=True)

# =========================
# USER MANAGEMENT
# =========================
elif menu == "User Management":
    st.header("User Management")

    with st.form("user_form"):
        new_username = st.text_input("Username")
        new_password = st.text_input("Password", type="password")
        new_role = st.selectbox("Role", ["Admin", "PR User", "Procurement", "Finance", "Manager"])
        new_status = st.selectbox("Status", ["Active", "Inactive"])
        submitted = st.form_submit_button("Create User")

        if submitted:
            conn = get_conn()
            c = conn.cursor()
            try:
                c.execute("""
                INSERT INTO users (username, password, role, status, created_at)
                VALUES (%s, %s, %s, %s, %s)
                """, (new_username, new_password, new_role, new_status, now_text()))
                conn.commit()
                st.success("User created successfully")
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                st.warning("Username already exists")
            finally:
                conn.close()

    users_df = fetch_df("users")
    st.dataframe(users_df, use_container_width=True)

    if not users_df.empty:
        selected_user = st.selectbox("Select User", users_df["username"].tolist())
        selected_status = st.selectbox("New Status", ["Active", "Inactive"])
        if st.button("Update Status"):
            conn = get_conn()
            c = conn.cursor()
            c.execute("UPDATE users SET status = %s WHERE username = %s", (selected_status, selected_user))
            conn.commit()
            conn.close()
            st.success("User status updated successfully")

# =========================
# SYSTEM SETTINGS
# =========================
elif menu == "System Settings":
    st.header("System Settings")
    st.caption("Admin control panel for editing, correcting, and deleting system records")

    if st.session_state.role != "Admin":
        st.error("Access denied")
        st.stop()

    table_map = {
        "Vendors": "vendors",
        "Items": "items",
        "Purchase Requisitions": "purchase_requisitions",
        "RFQs": "rfqs",
        "Quotations": "quotations",
        "Purchase Orders": "purchase_orders",
        "Invoices": "invoices",
        "Payments": "payments",
        "Users": "users"
    }

    selected_module = st.selectbox("Select module", list(table_map.keys()))
    selected_table = table_map[selected_module]
    df = fetch_df(selected_table)

    if df.empty:
        st.info("No records found")
    else:
        st.subheader(f"{selected_module} Records")
        st.dataframe(df, use_container_width=True)

        selected_id = st.selectbox("Select Record ID", df["id"].tolist())
        selected_row = df[df["id"] == selected_id].iloc[0]

        st.divider()
        st.subheader("Edit Selected Record")

        updated_data = {}
        with st.form("edit_record_form"):
            for col in df.columns:
                if col == "id":
                    st.text_input("id", value=str(selected_row[col]), disabled=True)
                else:
                    current_value = "" if pd.isna(selected_row[col]) else str(selected_row[col])
                    updated_data[col] = st.text_input(col, value=current_value)

            save_changes = st.form_submit_button("Save Changes")
            if save_changes:
                update_record(selected_table, selected_id, updated_data)
                st.rerun()

        st.divider()
        st.subheader("Delete Selected Record")
        st.warning("Deleting a record is permanent. Use this only for wrong or duplicated entries.")
        confirm_delete = st.checkbox("I confirm that I want to delete this record")

        if st.button("Delete Record"):
            if confirm_delete:
                delete_record(selected_table, selected_id)
                st.rerun()
            else:
                st.warning("Please confirm deletion first")

# =========================
# VENDORS
# =========================
elif menu == "Vendors":
    st.header("Vendor Management")

    with st.form("vendor_form"):
        vendor_name = st.text_input("Vendor Name")
        phone = st.text_input("Phone")
        email = st.text_input("Email")
        address = st.text_area("Address")
        submitted = st.form_submit_button("Save Vendor")

        if submitted:
            if vendor_name.strip() == "":
                st.error("Vendor name is required")
            else:
                insert_vendor(vendor_name.strip(), phone, email, address)

    st.subheader("Vendor List")
    st.dataframe(fetch_df("vendors"), use_container_width=True)

# =========================
# ITEMS
# =========================
elif menu == "Items":
    st.header("Item Master")

    with st.form("item_form"):
        item_name = st.text_input("Item Name")
        unit = st.selectbox("Unit", ["PCS", "M", "M2", "M3", "KG", "TON", "L", "SET", "DAY"])
        description = st.text_area("Description")
        submitted = st.form_submit_button("Save Item")

        if submitted:
            if item_name.strip() == "":
                st.error("Item name is required")
            else:
                insert_item(item_name.strip(), unit, description)

    st.subheader("Item List")
    st.dataframe(fetch_df("items"), use_container_width=True)

# =========================
# CREATE PR
# =========================
elif menu == "Create PR":
    st.header("Create Purchase Requisition")

    items = fetch_list("items", "item_name")

    if not items:
        st.warning("Please add items first")
    else:
        with st.form("pr_form"):
            pr_no = generate_no("PR", "purchase_requisitions")
            st.text_input("PR Number", value=pr_no, disabled=True)
            requester_name = st.text_input("Requester Name")
            department = st.selectbox("Department", ["Procurement", "Finance", "HR", "Projects", "Warehouse", "Logistics", "Administration", "Other"])
            project_name = st.text_input("Project Name")
            item_name = st.selectbox("Item", items)
            quantity = st.number_input("Quantity", min_value=0.0, step=1.0)
            unit = st.selectbox("Unit", ["PCS", "M", "M2", "M3", "KG", "TON", "L", "SET", "DAY"])
            required_date = st.date_input("Required Date")
            priority = st.selectbox("Priority", ["Low", "Normal", "High", "Urgent"])
            reason = st.text_area("Reason / Justification")
            submitted = st.form_submit_button("Create PR")

            if submitted:
                if requester_name.strip() == "":
                    st.error("Requester name is required")
                elif quantity <= 0:
                    st.error("Quantity must be greater than zero")
                else:
                    conn = get_conn()
                    c = conn.cursor()
                    c.execute("""
                    INSERT INTO purchase_requisitions
                    (pr_no, requester_name, department, project_name, item_name, quantity, unit, required_date, reason, priority, approval_status, pr_status, manager_approval_status, manager_approved_by, manager_approved_at, manager_comment, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (pr_no, requester_name.strip(), department, project_name, item_name, quantity, unit, str(required_date), reason, priority, "Pending", "Open", "Pending", "", "", "", now_text()))
                    conn.commit()
                    conn.close()
                    st.success(f"Purchase Requisition created successfully: {pr_no}")

    st.subheader("Purchase Requisition List")
    st.dataframe(fetch_df("purchase_requisitions"), use_container_width=True)

# =========================
# PR APPROVALS
# =========================
elif menu == "PR Approvals":
    st.header("PR Approval Workflow")

    prs = fetch_df("purchase_requisitions")

    if prs.empty:
        st.warning("No purchase requisitions found")
    else:
        pending_prs = prs[prs["approval_status"] == "Pending"]

        if pending_prs.empty:
            st.success("No pending PRs for approval")
        else:
            st.dataframe(pending_prs, use_container_width=True)
            selected_pr = st.selectbox("Select PR for Approval", pending_prs["pr_no"].dropna().tolist())
            manager_comment = st.text_area("Manager Comment")

            col1, col2 = st.columns(2)
            approve_clicked = col1.button("Approve PR")
            reject_clicked = col2.button("Reject PR")

            if approve_clicked or reject_clicked:
                new_status = "Approved" if approve_clicked else "Rejected"

                conn = get_conn()
                c = conn.cursor()
                c.execute("""
                UPDATE purchase_requisitions
                SET approval_status = %s,
                    pr_status = %s,
                    manager_approval_status = %s,
                    manager_approved_by = %s,
                    manager_approved_at = %s,
                    manager_comment = %s
                WHERE pr_no = %s
                """, (new_status, new_status, new_status, st.session_state.username, now_text(), manager_comment, selected_pr))
                conn.commit()
                conn.close()

                st.success(f"PR {selected_pr} has been {new_status}")
                st.rerun()

        st.subheader("All PRs")
        st.dataframe(prs, use_container_width=True)

# =========================
# CREATE RFQ
# =========================
elif menu == "Create RFQ":
    st.header("Create RFQ from Approved PR")

    prs = fetch_df("purchase_requisitions")

    if prs.empty:
        st.warning("No purchase requisitions available")
    else:
        approved_prs = prs[prs["approval_status"] == "Approved"]

        if approved_prs.empty:
            st.warning("No approved PRs found")
        else:
            selected_pr = st.selectbox("Select Approved PR", approved_prs["pr_no"].dropna().tolist())
            pr_row = approved_prs[approved_prs["pr_no"] == selected_pr].iloc[0]
            rfq_no = generate_no("RFQ", "rfqs")

            st.info(f"RFQ Number: {rfq_no}")
            st.write(f"Item: {pr_row['item_name']}")
            st.write(f"Quantity: {pr_row['quantity']}")
            st.write(f"Unit: {pr_row['unit']}")
            st.write(f"Required Date: {pr_row['required_date']}")

            if st.button("Create RFQ"):
                conn = get_conn()
                c = conn.cursor()
                c.execute("""
                INSERT INTO rfqs (rfq_no, pr_no, item_name, quantity, unit, required_date, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (rfq_no, selected_pr, pr_row["item_name"], pr_row["quantity"], pr_row["unit"], pr_row["required_date"], "Open", now_text()))
                conn.commit()
                conn.close()
                st.success(f"RFQ Created Successfully: {rfq_no}")
                st.rerun()

    st.subheader("RFQ List")
    st.dataframe(fetch_df("rfqs"), use_container_width=True)

# =========================
# ADD QUOTATION
# =========================
elif menu == "Add Quotation":
    st.header("Add Vendor Quotation")

    rfqs = fetch_list("rfqs", "rfq_no")
    vendors = fetch_list("vendors", "vendor_name")

    if not rfqs:
        st.warning("Please create an RFQ first")
    elif not vendors:
        st.warning("Please add vendors first")
    else:
        with st.form("quotation_form"):
            rfq_no = st.selectbox("RFQ Number", rfqs)
            vendor = st.selectbox("Vendor", vendors)
            quoted_price = st.number_input("Quoted Price", min_value=0.0, step=1000.0)
            currency = st.selectbox("Currency", ["IQD", "USD"])
            delivery_days = st.number_input("Delivery Days", min_value=0, step=1)
            notes = st.text_area("Notes")
            submitted = st.form_submit_button("Save Quotation")

            if submitted:
                conn = get_conn()
                c = conn.cursor()
                c.execute("""
                INSERT INTO quotations (rfq_no, vendor, quoted_price, currency, delivery_days, notes, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (rfq_no, vendor, quoted_price, currency, delivery_days, notes, now_text()))
                conn.commit()
                conn.close()
                st.success("Quotation saved successfully")

    st.subheader("Quotation List")
    st.dataframe(fetch_df("quotations"), use_container_width=True)

# =========================
# COMPARE QUOTATIONS
# =========================
elif menu == "Compare Quotations":
    st.header("Compare Quotations")

    quotations = fetch_df("quotations")

    if quotations.empty:
        st.warning("No quotations available")
    else:
        rfq_list = quotations["rfq_no"].dropna().unique().tolist()
        selected_rfq = st.selectbox("Select RFQ", rfq_list)
        df = quotations[quotations["rfq_no"] == selected_rfq].copy()
        df["quoted_price"] = df["quoted_price"].astype(float)
        df = df.sort_values(by="quoted_price")

        st.dataframe(df, use_container_width=True)

        if not df.empty:
            best = df.iloc[0]
            st.success(f"Best quotation: {best['vendor']} | {best['quoted_price']} {best['currency']}")

# =========================
# CREATE PO
# =========================
elif menu == "Create PO":
    st.header("Create Purchase Order")

    quotations = fetch_df("quotations")
    rfqs_df = fetch_df("rfqs")

    if quotations.empty:
        st.warning("No quotations available")
    else:
        rfq_list = quotations["rfq_no"].dropna().unique().tolist()
        selected_rfq = st.selectbox("Select RFQ", rfq_list)
        q_df = quotations[quotations["rfq_no"] == selected_rfq].copy()

        if q_df.empty:
            st.warning("No quotations found for this RFQ")
        else:
            selected_vendor = st.selectbox("Select Vendor", q_df["vendor"].dropna().unique().tolist())
            selected_quote = q_df[q_df["vendor"] == selected_vendor].iloc[0]
            rfq_row = rfqs_df[rfqs_df["rfq_no"] == selected_rfq]

            if rfq_row.empty:
                st.error("RFQ data not found")
            else:
                rfq_row = rfq_row.iloc[0]
                po_no = generate_no("PO", "purchase_orders")
                quantity = float(rfq_row["quantity"])
                unit_price = float(selected_quote["quoted_price"])
                total_amount = quantity * unit_price

                st.info(f"PO Number: {po_no}")
                st.write(f"Item: {rfq_row['item_name']}")
                st.write(f"Quantity: {quantity} {rfq_row['unit']}")
                st.write(f"Vendor: {selected_vendor}")
                st.write(f"Unit Price: {unit_price} {selected_quote['currency']}")
                st.write(f"Total Amount: {total_amount} {selected_quote['currency']}")

                approval_status = st.selectbox("Approval Status", ["Pending", "Approved", "Rejected"])

                if st.button("Create PO"):
                    conn = get_conn()
                    c = conn.cursor()
                    c.execute("""
                    INSERT INTO purchase_orders
                    (po_no, rfq_no, vendor, item_name, quantity, unit, unit_price, currency, total_amount, approval_status, po_status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (po_no, selected_rfq, selected_vendor, rfq_row["item_name"], quantity, rfq_row["unit"], unit_price, selected_quote["currency"], total_amount, approval_status, "Open", now_text()))
                    conn.commit()
                    conn.close()
                    st.success(f"Purchase Order created successfully: {po_no}")

    st.subheader("Purchase Order List")
    st.dataframe(fetch_df("purchase_orders"), use_container_width=True)

# =========================
# PO APPROVALS
# =========================
elif menu == "PO Approvals":
    st.header("PO Approval Management")

    pos = fetch_df("purchase_orders")

    if pos.empty:
        st.warning("No purchase orders found")
    else:
        st.dataframe(pos, use_container_width=True)
        selected_po = st.selectbox("Select Purchase Order", pos["po_no"].dropna().tolist())
        new_status = st.selectbox("Approval Status", ["Pending", "Approved", "Rejected"])

        if st.button("Update Approval"):
            conn = get_conn()
            c = conn.cursor()
            c.execute("UPDATE purchase_orders SET approval_status = %s WHERE po_no = %s", (new_status, selected_po))
            conn.commit()
            conn.close()
            st.success("Approval status updated successfully")

# =========================
# REGISTER INVOICE
# =========================
elif menu == "Register Invoice":
    st.header("Register Supplier Invoice")

    pos = fetch_df("purchase_orders")

    if pos.empty:
        st.warning("No purchase orders available")
    else:
        approved_pos = pos[pos["approval_status"] == "Approved"]

        if approved_pos.empty:
            st.warning("No approved purchase orders available")
        else:
            po_list = approved_pos["po_no"].dropna().tolist()

            with st.form("invoice_form"):
                invoice_no = generate_no("INV", "invoices")
                st.text_input("Invoice Number", value=invoice_no, disabled=True)
                selected_po = st.selectbox("Purchase Order", po_list)
                po_row = approved_pos[approved_pos["po_no"] == selected_po].iloc[0]

                vendor = po_row["vendor"]
                po_amount = float(po_row["total_amount"])
                currency = po_row["currency"]

                st.write(f"Vendor: {vendor}")
                st.write(f"PO Amount: {po_amount:,.2f} {currency}")

                invoice_date = st.date_input("Invoice Date")
                invoice_amount = st.number_input("Invoice Amount", min_value=0.0, value=po_amount, step=1000.0)
                notes = st.text_area("Notes")
                submitted = st.form_submit_button("Register Invoice")

                if submitted:
                    conn = get_conn()
                    c = conn.cursor()
                    c.execute("""
                    INSERT INTO invoices
                    (invoice_no, po_no, vendor, invoice_date, invoice_amount, currency, invoice_status, notes, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (invoice_no, selected_po, vendor, str(invoice_date), invoice_amount, currency, "Unpaid", notes, now_text()))

                    c.execute("UPDATE purchase_orders SET po_status = %s WHERE po_no = %s", ("Invoiced", selected_po))

                    conn.commit()
                    conn.close()
                    st.success(f"Invoice registered successfully: {invoice_no}")

    st.subheader("Invoice List")
    st.dataframe(fetch_df("invoices"), use_container_width=True)

# =========================
# REGISTER PAYMENT
# =========================
elif menu == "Register Payment":
    st.header("Register Supplier Payment")

    invoices = fetch_df("invoices")

    if invoices.empty:
        st.warning("No invoices available")
    else:
        unpaid_invoices = invoices[invoices["invoice_status"].isin(["Unpaid", "Partially Paid"])]

        if unpaid_invoices.empty:
            st.success("There are no unpaid invoices")
        else:
            invoice_list = unpaid_invoices["invoice_no"].dropna().tolist()

            with st.form("payment_form"):
                payment_no = generate_no("PAY", "payments")
                st.text_input("Payment Number", value=payment_no, disabled=True)
                selected_invoice = st.selectbox("Invoice Number", invoice_list)

                invoice_row = unpaid_invoices[unpaid_invoices["invoice_no"] == selected_invoice].iloc[0]
                balance = get_invoice_balance(selected_invoice)

                st.write(f"Vendor: {invoice_row['vendor']}")
                st.write(f"PO Number: {invoice_row['po_no']}")
                st.write(f"Outstanding Balance: {balance:,.2f} {invoice_row['currency']}")

                payment_date = st.date_input("Payment Date")
                payment_amount = st.number_input("Payment Amount", min_value=0.0, max_value=float(balance), step=1000.0)
                payment_method = st.selectbox("Payment Method", ["Cash", "Bank Transfer", "Cheque", "Exchange Office", "Other"])
                reference_no = st.text_input("Reference Number")
                notes = st.text_area("Notes")
                submitted = st.form_submit_button("Register Payment")

                if submitted:
                    if payment_amount <= 0:
                        st.error("Payment amount must be greater than zero")
                    else:
                        conn = get_conn()
                        c = conn.cursor()
                        c.execute("""
                        INSERT INTO payments
                        (payment_no, invoice_no, po_no, vendor, payment_date, payment_amount, currency, payment_method, reference_no, notes, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (payment_no, selected_invoice, invoice_row["po_no"], invoice_row["vendor"], str(payment_date), payment_amount, invoice_row["currency"], payment_method, reference_no, notes, now_text()))
                        conn.commit()
                        conn.close()

                        update_invoice_status(selected_invoice)
                        st.success(f"Payment registered successfully: {payment_no}")

    st.subheader("Payment List")
    st.dataframe(fetch_df("payments"), use_container_width=True)

# =========================
# ACCOUNTS PAYABLE
# =========================
elif menu == "Accounts Payable":
    st.header("Accounts Payable")

    invoices = fetch_df("invoices")
    payments = fetch_df("payments")

    if invoices.empty:
        st.warning("No invoices available")
    else:
        report_rows = []

        for _, inv in invoices.iterrows():
            invoice_no = inv["invoice_no"]
            invoice_amount = float(inv["invoice_amount"])
            paid_amount = payments[payments["invoice_no"] == invoice_no]["payment_amount"].astype(float).sum() if not payments.empty else 0
            balance = invoice_amount - paid_amount

            report_rows.append({
                "Invoice No": invoice_no,
                "PO No": inv["po_no"],
                "Vendor": inv["vendor"],
                "Invoice Date": inv["invoice_date"],
                "Invoice Amount": invoice_amount,
                "Paid Amount": paid_amount,
                "Outstanding Balance": balance,
                "Currency": inv["currency"],
                "Status": inv["invoice_status"]
            })

        ap_df = pd.DataFrame(report_rows)

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Invoice Amount", f"{ap_df['Invoice Amount'].sum():,.2f}")
        col2.metric("Total Paid Amount", f"{ap_df['Paid Amount'].sum():,.2f}")
        col3.metric("Total Outstanding", f"{ap_df['Outstanding Balance'].sum():,.2f}")

        st.dataframe(ap_df, use_container_width=True)

        csv = ap_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button("Download Accounts Payable Report", csv, file_name="accounts_payable_report.csv", mime="text/csv")

# =========================
# REPORTS
# =========================
elif menu == "Reports":
    st.header("Reports")

    report_type = st.selectbox("Select Report", [
        "Vendors", "Items", "Purchase Requisitions", "RFQs",
        "Quotations", "Purchase Orders", "Invoices", "Payments"
    ])

    table_map = {
        "Vendors": "vendors",
        "Items": "items",
        "Purchase Requisitions": "purchase_requisitions",
        "RFQs": "rfqs",
        "Quotations": "quotations",
        "Purchase Orders": "purchase_orders",
        "Invoices": "invoices",
        "Payments": "payments"
    }

    df = fetch_df(table_map[report_type])
    st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("Download CSV", csv, file_name=f"{report_type}.csv", mime="text/csv")
