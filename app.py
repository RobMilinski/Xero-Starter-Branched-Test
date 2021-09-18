# -*- coding: utf-8 -*-
import os
from functools import wraps
from io import BytesIO
from logging.config import dictConfig

from flask import Flask, url_for, render_template, session, redirect, json, send_file
from flask_oauthlib.contrib.client import OAuth, OAuth2Application
from flask_session import Session
from xero_python.accounting import AccountingApi, ContactPerson, Contact, Contacts
from xero_python.api_client import ApiClient, serialize
from xero_python.api_client.configuration import Configuration
from xero_python.api_client.oauth2 import OAuth2Token
from xero_python.exceptions import AccountingBadRequestException
from xero_python.identity import IdentityApi
from xero_python.utils import getvalue

import logging_settings
from utils import jsonify, serialize_model

from flask import request
import json

dictConfig(logging_settings.default_settings)

# configure main flask application
app = Flask(__name__)
app.config.from_object("default_settings")
app.config.from_pyfile("config.py", silent=True)

if app.config["ENV"] != "production":
    # allow oauth2 loop to run over http (used for local testing only)
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# configure persistent session cache
Session(app)

# configure flask-oauthlib application
# TODO fetch config from https://identity.xero.com/.well-known/openid-configuration #1
oauth = OAuth(app)
xero = oauth.remote_app(
    name="xero",
    version="2",
    client_id=app.config["CLIENT_ID"],
    client_secret=app.config["CLIENT_SECRET"],
    endpoint_url="https://api.xero.com/",
    authorization_url="https://login.xero.com/identity/connect/authorize",
    access_token_url="https://identity.xero.com/connect/token",
    refresh_token_url="https://identity.xero.com/connect/token",
    scope="offline_access openid profile email accounting.transactions "
    "accounting.reports.read accounting.journals.read accounting.settings "
    "accounting.contacts accounting.attachments assets projects",
)  # type: OAuth2Application


# configure xero-python sdk client
api_client = ApiClient(
    Configuration(
        debug=app.config["DEBUG"],
        oauth2_token=OAuth2Token(
            client_id=app.config["CLIENT_ID"], client_secret=app.config["CLIENT_SECRET"]
        ),
    ),
    pool_threads=1,
)


# configure token persistence and exchange point between flask-oauthlib and xero-python
@xero.tokengetter
@api_client.oauth2_token_getter
def obtain_xero_oauth2_token():
    return session.get("token")


@xero.tokensaver
@api_client.oauth2_token_saver
def store_xero_oauth2_token(token):
    session["token"] = token
    session.modified = True


def xero_token_required(function):
    @wraps(function)
    def decorator(*args, **kwargs):
        xero_token = obtain_xero_oauth2_token()
        if not xero_token:
            return redirect(url_for("login", _external=True))

        return function(*args, **kwargs)

    return decorator


@app.route("/index")
def index():
    xero_access = dict(obtain_xero_oauth2_token() or {})
    return render_template(
        "code.html",
        title="Home | oauth token",
        code=json.dumps(xero_access, sort_keys=True, indent=4),
    )

# utilising single invoice search method = "get_invoice"
@app.route("/", methods=['GET', 'POST'])
@xero_token_required
def test():
    xero_access = dict(obtain_xero_oauth2_token() or {})

    if request.method == 'POST':
        #when educator inputs invoice ID
        xero_tenant_id = get_xero_tenant_id()
        accounting_api = AccountingApi(api_client)

        if request.form['input_invoice_id'] != '':
                invoice_id = request.form['input_invoice_id']
        elif request.form['moduleselectbox'] != '':
            invoice_id = request.form['moduleselectbox']
        
        invoice = accounting_api.get_invoice(
            xero_tenant_id,
            invoice_id
        )
        json = serialize_model(invoice)

        amount_due = getvalue(invoice, "invoices.0.amount_due", "")
        amount_paid = getvalue(invoice, "invoices.0.amount_paid", "")
        contact_name_first = getvalue(invoice, "invoices.0.contact.first_name", "")
        contact_email = getvalue(invoice, "invoices.0.contact.email_address", "")
        contact_name_last = getvalue(invoice, "invoices.0.contact.last_name", "")
        due_date = getvalue(invoice, "invoices.0.due_date", "")
        paid_date = getvalue(invoice, "invoices.0.fully_paid_on_date", "")
        invoice_id = getvalue(invoice, "invoices.0.invoice_id", "")
        invoice_number = getvalue(invoice, "invoices.0.invoice_number", "")
        line_item_0_description = getvalue(invoice, "invoices.0.line_items.0.description", "")
        line_item_0_line_amount = getvalue(invoice, "invoices.0.line_items.0.line_amount", "")
        line_item_0_quantity = getvalue(invoice, "invoices.0.line_items.0.quantity", "")
        line_item_0_unit_amount = getvalue(invoice, "invoices.0.line_items.0.unit_amount", "")
        status = getvalue(invoice, "invoices.0.status", "")
        sub_total = getvalue(invoice, "invoices.0.sub_total", "")
        total_tax = getvalue(invoice, "invoices.0.total_tax", "")
        total = getvalue(invoice, "invoices.0.total", "")

        sub_title = "Invoice Requested"

        return render_template(
            "invoice.html", title="Home | POST Page", code=json, sub_title=sub_title,
            amount_due=amount_due, amount_paid=amount_paid, 
            contact_name_first=contact_name_first, contact_email=contact_email, contact_name_last=contact_name_last, 
            due_date=due_date, paid_date=paid_date, 
            invoice_id=invoice_id, invoice_number=invoice_number,
            line_item_0_description=line_item_0_description, line_item_0_line_amount=line_item_0_line_amount, line_item_0_quantity=line_item_0_quantity, line_item_0_unit_amount=line_item_0_unit_amount,
            status=status, sub_total=sub_total, total_tax=total_tax, total=total,
        )
        
    #if page called from navbar, initial open
    return render_template("test.html", title="Home | GET Page")

@app.route("/educator_view", methods=['GET', 'POST'])
@xero_token_required
def educator_view():
    xero_access = dict(obtain_xero_oauth2_token() or {})

    if request.method == 'POST':
        if request.form['module_select_box'] == "":
            return render_template("educator_view.html", title="Educator View | Xero Learn")
        elif request.form['module_select_box'] == "Module 6: Invoicing":
            display = 1
            return render_template("educator_view.html", title="Educator View | Xero Learn")
    
    # if request.method == 'POST':
    #     xero_tenant_id = get_xero_tenant_id()
    #     accounting_api = AccountingApi(api_client)

    #     invoice_number = int(request.form['invoice_number_search'])

    #     invoice = accounting_api.get_invoice(
    #         xero_tenant_id,
    #         invoice_number
    #     )
    #     code = serialize_model(invoice)
    #     sub_title = "Invoice Requested" 

    #     return render_template(
    #         "educator_view.html", title="Educator View", code=code, sub_title=sub_title
    #     )
    return render_template("educator_view.html", title="Educator View | Xero Learn")

@app.route("/login")
def login():
    redirect_url = url_for("oauth_callback", _external=True)
    response = xero.authorize(callback_uri=redirect_url)
    return response


@app.route("/callback")
def oauth_callback():
    try:
        response = xero.authorized_response()
    except Exception as e:
        print(e)
        raise
    # todo validate state value
    if response is None or response.get("access_token") is None:
        return "Access denied: response=%s" % response
    store_xero_oauth2_token(response)
    return redirect(url_for("index", _external=True))


@app.route("/logout")
def logout():
    store_xero_oauth2_token(None)
    return redirect(url_for("index", _external=True))


@app.route("/export-token")
@xero_token_required
def export_token():
    token = obtain_xero_oauth2_token()
    buffer = BytesIO("token={!r}".format(token).encode("utf-8"))
    buffer.seek(0)
    return send_file(
        buffer,
        mimetype="x.python",
        as_attachment=True,
        attachment_filename="oauth2_token.py",
    )


@app.route("/refresh-token")
@xero_token_required
def refresh_token():
    xero_token = obtain_xero_oauth2_token()
    new_token = api_client.refresh_oauth2_token()
    return render_template(
        "code.html",
        title="Xero OAuth2 token",
        code=jsonify({"Old Token": xero_token, "New token": new_token}),
        sub_title="token refreshed",
    )


def get_xero_tenant_id():
    token = obtain_xero_oauth2_token()
    if not token:
        return None

    identity_api = IdentityApi(api_client)
    for connection in identity_api.get_connections():
        if connection.tenant_type == "ORGANISATION":
            return connection.tenant_id


if __name__ == '__main__':
    app.run(host='localhost', port=5000)
