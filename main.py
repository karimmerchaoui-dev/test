from seleniumbase import Driver
from selenium.webdriver.common.by import By
import time
import json
import os
import smtplib
from email.message import EmailMessage


JSON_FILE = "payments.json"


# =========================
# ADEX LOGIN
# =========================

ADEX_LOGIN = os.getenv("ADEX_LOGIN")
ADEX_PASSWORD = os.getenv("ADEX_PASSWORD")


# =========================
# EMAIL CONFIGURATION
# =========================

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465

EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_TO = os.getenv("EMAIL_TO")


# =========================
# LOGIN TO ADEX
# =========================

def login_adex(driver):

    # 1. Login
    driver.get("https://my.adex.tn/login")

    driver.wait_for_element_visible(
        "//*[@id='login']", by=By.XPATH
    )

    driver.type(
        "//*[@id='login']",
        ADEX_LOGIN,
        by=By.XPATH
    )

    driver.type(
        "//*[@id='password']",
        ADEX_PASSWORD,
        by=By.XPATH
    )

    driver.click(
        "//*[@id='btn-submit']",
        by=By.XPATH
    )

    time.sleep(3)

    driver.click(
        "/html/body/aside/ul/li[11]/a"
    )

    driver.type(
        "//*[@id='admin-password']",
        ADEX_PASSWORD,
        by=By.XPATH
    )

    driver.click(
        '//*[@id="admin-password-submit"]'
    )

    time.sleep(3)


# =========================
# READ PAYMENT TABLE
# =========================

def get_payments(driver):

    table = driver.find_element(
        By.XPATH,
        '//*[@id="tableView"]/div[2]/table'
    )

    headers = [
        "N° Paiement",
        "Date prévue",
        "Espèces",
        "Chèques",
        "Total",
        "Frais Liv.",
        "R.A.S",
        "Net à payer",
        "Code secret",
        "Statut"
    ]

    payments = []

    rows = table.find_elements(
        By.XPATH,
        ".//tbody/tr"
    )

    for row in rows:

        cells = row.find_elements(
            By.XPATH,
            "./td"
        )

        if not cells:
            continue

        values = []

        for index, cell in enumerate(cells):

            # Code secret column
            if index == 8:

                try:

                    code_element = cell.find_element(
                        By.CSS_SELECTOR,
                        "span[data-code]"
                    )

                    value = code_element.get_attribute(
                        "data-code"
                    )

                except Exception:

                    value = ""

            else:

                value = cell.text.strip()

            values.append(value)

        if len(values) < len(headers):
            continue

        payment = dict(zip(headers, values))

        payments.append(payment)

    return payments


# =========================
# LOAD OLD DATA
# =========================

def load_previous_payments():

    if not os.path.exists(JSON_FILE):
        return []

    try:

        with open(
            JSON_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except (json.JSONDecodeError, OSError):

        return []


# =========================
# SAVE DATA
# =========================

def save_payments(payments):

    with open(
        JSON_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            payments,
            f,
            ensure_ascii=False,
            indent=4
        )


# =========================
# DETECT CHANGES
# =========================

def detect_changes(
    old_payments,
    new_payments
):

    old_by_id = {
        payment["N° Paiement"]: payment
        for payment in old_payments
    }

    new_by_id = {
        payment["N° Paiement"]: payment
        for payment in new_payments
    }

    new_payments_found = []
    status_changes = []

    # =========================
    # NEW PAYMENTS
    # =========================

    for payment_id, payment in new_by_id.items():

        if payment_id not in old_by_id:

            new_payments_found.append(
                payment
            )

    # =========================
    # STATUS MODIFICATIONS
    # =========================

    for payment_id, new_payment in new_by_id.items():

        if payment_id not in old_by_id:
            continue

        old_payment = old_by_id[payment_id]

        old_status = old_payment.get(
            "Statut",
            ""
        )

        new_status = new_payment.get(
            "Statut",
            ""
        )

        if old_status != new_status:

            status_changes.append({
                "payment": new_payment,
                "old_status": old_status,
                "new_status": new_status
            })

    return (
        new_payments_found,
        status_changes
    )


# =========================
# SEND EMAIL
# =========================

def send_email(
    new_payments,
    status_changes
):

    if not new_payments and not status_changes:
        return

    message = EmailMessage()

    message["Subject"] = "ADEX - Payment Update"
    message["From"] = EMAIL_FROM
    message["To"] = EMAIL_TO

    body = []

    # =========================
    # NEW PAYMENTS
    # =========================

    if new_payments:

        body.append("NEW PAYMENT(S)")
        body.append("=" * 40)

        for payment in new_payments:

            body.append(
                f"N° Paiement: "
                f"{payment.get('N° Paiement', '')}"
            )

            body.append(
                f"Date prévue: "
                f"{payment.get('Date prévue', '')}"
            )

            body.append(
                f"Net à payer: "
                f"{payment.get('Net à payer', '')}"
            )

            body.append(
                f"Statut: "
                f"{payment.get('Statut', '')}"
            )

            body.append("")

    # =========================
    # STATUS CHANGES
    # =========================

    if status_changes:

        body.append("STATUS CHANGE(S)")
        body.append("=" * 40)

        for change in status_changes:

            payment = change["payment"]

            body.append(
                f"N° Paiement: "
                f"{payment.get('N° Paiement', '')}"
            )

            body.append(
                f"Old status: "
                f"{change['old_status']}"
            )

            body.append(
                f"New status: "
                f"{change['new_status']}"
            )

            body.append("")

    message.set_content(
        "\n".join(body)
    )

    with smtplib.SMTP_SSL(
        SMTP_SERVER,
        SMTP_PORT
    ) as server:

        server.login(
            EMAIL_FROM,
            EMAIL_PASSWORD
        )

        server.send_message(
            message
        )


# =========================
# MAIN CHECK
# =========================

def check_payments(driver):

    time.sleep(3)

    current_payments = get_payments(
        driver
    )

    previous_payments = (
        load_previous_payments()
    )

    (
        new_payments,
        status_changes
    ) = detect_changes(
        previous_payments,
        current_payments
    )

    # Save latest version
    save_payments(
        current_payments
    )

    # Send email if something changed
    if new_payments or status_changes:

        print(
            "Payment update detected!",
            flush=True
        )

        send_email(
            new_payments,
            status_changes
        )

    else:

        print(
            "No payment changes.",
            flush=True
        )

    return (
        new_payments,
        status_changes
    )


# =========================
# CONTINUOUS MONITORING
# =========================

driver = Driver(
    pls="eager",
    headless=True,
    no_sandbox=True
)

try:

    login_adex(driver)

    while True:

        try:

            print(
                "Checking payments...",
                flush=True
            )

            # Refresh the payments page
            driver.get(
                "https://my.adex.tn/paiements"
            )

            check_payments(driver)

        except Exception as e:

            print(
                f"Error during check: {e}",
                flush=True
            )

            # If something goes wrong, try logging in again
            try:

                print(
                    "Trying to login again...",
                    flush=True
                )

                login_adex(driver)

            except Exception as login_error:

                print(
                    f"Login error: {login_error}",
                    flush=True
                )

        print(
            "Waiting 30 seconds...",
            flush=True
        )

        time.sleep(30)

finally:

    driver.quit()