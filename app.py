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
def student_view():
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

        # ACTIVITY 6.1
        result_61_1_result = getvalue(invoice, "invoices.0.line_items.0.quantity", "")
        result_61_2_result = getvalue(invoice, "invoices.0.line_items.1.discount_rate", "")
        result_61_3_result = getvalue(invoice, "invoices.0.line_items.0.line_amount", "")
        result_61_4_result = getvalue(invoice, "invoices.0.line_items.1.line_amount", "")

        # ACTIVITY 6.2
        result_62_1_result = getvalue(invoice, "invoices.0.line_items.2.line_amount", "")
        result_62_2_result = getvalue(invoice, "invoices.0.line_items.2.tax_amount", "")
        result_62_3_result = getvalue(invoice, "invoices.0.sub_total", "")

        # GRADES
        if result_61_1_result == float('11'):
            result_61_1_mark = 5
        else:
            result_61_1_mark = 2
        
        if result_61_2_result == float('20'):
            result_61_2_mark = 5
        else:
            result_61_2_mark = 4
        
        if result_61_3_result == float('137.50'):
            result_61_3_mark = 5
        else:
            result_61_3_mark = 4

        if result_61_4_result == float('60'):
            result_61_4_mark = 5
        else:
            result_61_4_mark = 5
        
        if result_62_1_result == float('35'):
            result_62_1_mark = 5
        else:
            result_62_1_mark = 3
        
        if result_62_2_result == float('0.00'):
            result_62_2_mark = 5
        else:
            result_62_2_mark = 1
        
        if result_62_3_result == float('232.5'):
            result_62_3_mark = 5
        else:
            result_62_3_mark = 2
       
        # Grades and Feedback Dictionary
        auto_feedback_dict = {
            "5": "Awesome work! You have inputted all of the correct data and received an accurate result.",
            "4": "Very close, maybe double check your answer here. Be sure to check each value as one wrong input can disrupt the final calculation.",
            "3": "A few values seem to be wrong here. We suggest re-reading the tasks and make the right values are in the right boxes.",
            "2": "One or two values are correct, but you might need ...",
            "1": "This answer is wrong. Please re-read the question, and start over to ensure you're inputting the correct values."
        }
        
        result_61_1_feedback = auto_feedback_dict[str(result_61_1_mark)]
        result_61_2_feedback = auto_feedback_dict[str(result_61_2_mark)]
        result_61_3_feedback = auto_feedback_dict[str(result_61_3_mark)]
        result_61_4_feedback = auto_feedback_dict[str(result_61_4_mark)]
        result_62_1_feedback = auto_feedback_dict[str(result_62_1_mark)]
        result_62_2_feedback = auto_feedback_dict[str(result_62_2_mark)]
        result_62_3_feedback = auto_feedback_dict[str(result_62_3_mark)]

        total_marks = int(result_61_1_mark + result_61_2_mark + result_61_3_mark + result_61_4_mark
                        + result_62_1_mark + result_62_2_mark + result_62_3_mark)

        # amount_due = getvalue(invoice, "invoices.0.amount_due", "")
        # amount_paid = getvalue(invoice, "invoices.0.amount_paid", "")
        # contact_name_first = getvalue(invoice, "invoices.0.contact.first_name", "")
        # contact_email = getvalue(invoice, "invoices.0.contact.email_address", "")
        # contact_name_last = getvalue(invoice, "invoices.0.contact.last_name", "")
        # due_date = getvalue(invoice, "invoices.0.due_date", "")
        # paid_date = getvalue(invoice, "invoices.0.fully_paid_on_date", "")
        # invoice_id = getvalue(invoice, "invoices.0.invoice_id", "")
        # invoice_number = getvalue(invoice, "invoices.0.invoice_number", "")
        # line_item_0_description = getvalue(invoice, "invoices.0.line_items.0.description", "")
        # line_item_0_line_amount = getvalue(invoice, "invoices.0.line_items.0.line_amount", "")
        # line_item_0_quantity = getvalue(invoice, "invoices.0.line_items.0.quantity", "")
        # line_item_0_unit_amount = getvalue(invoice, "invoices.0.line_items.0.unit_amount", "")
        # status = getvalue(invoice, "invoices.0.status", "")
        # sub_total = getvalue(invoice, "invoices.0.sub_total", "")
        # total_tax = getvalue(invoice, "invoices.0.total_tax", "")
        # total = getvalue(invoice, "invoices.0.total", "")

        return render_template(
            "student_view.html", title="Home | POST Page", 
            result_61_1_result=result_61_1_result,
            result_61_2_result=result_61_2_result,
            result_61_3_result=result_61_3_result,
            result_61_4_result=result_61_4_result,
            result_62_1_result=result_62_1_result,
            result_62_2_result=result_62_2_result,
            result_62_3_result=result_62_3_result,
            result_61_1_mark=result_61_1_mark,
            result_61_2_mark=result_61_2_mark,
            result_61_3_mark=result_61_3_mark,
            result_61_4_mark=result_61_4_mark,
            result_62_1_mark=result_62_1_mark,
            result_62_2_mark=result_62_2_mark,
            result_62_3_mark=result_62_3_mark,
            result_61_1_feedback=result_61_1_feedback,
            result_61_2_feedback=result_61_2_feedback,
            result_61_3_feedback=result_61_3_feedback,
            result_61_4_feedback=result_61_4_feedback,
            result_62_1_feedback=result_62_1_feedback,
            result_62_2_feedback=result_62_2_feedback,
            result_62_3_feedback=result_62_3_feedback,
            total_marks=total_marks,
        )
        
    #if page called from navbar, initial open
    return render_template("student_view.html", title="Home | GET Page")

@app.route("/educator_view", methods=['GET', 'POST'])
@xero_token_required
def educator_view():
    xero_access = dict(obtain_xero_oauth2_token() or {})

    # # # THIS CODE BLOCK BELOW IS REGARDING THE DROP DOWN MODULE LIST. AS FAR AS I KNOW, IT DOES NOT WORK AT THIS STAGE # # #
    # if request.method == 'POST':
    #     if request.form['module_select_box'] == "":
    #         return render_template("educator_view.html", title="Educator View | Xero Learn")
    #     elif request.form['module_select_box'] == "Module 6: Invoicing":
    #         display = 1
    #         return render_template("educator_view.html", title="Educator View | Xero Learn")
    
    if request.method == 'POST':
        xero_tenant_id = get_xero_tenant_id()
        accounting_api = AccountingApi(api_client)

        invoice_number = request.form['invoice_number_search']

        invoice = accounting_api.get_invoice(
            xero_tenant_id,
            invoice_number
        )
        json_data = serialize_model(invoice)

        # INVOICE DATA TO BE ADDED AS STUDENT ANSWERS
        # ACTIVITY 6.1
        # Result 1 - Light Fittings Quantity
        result_61_1_result = getvalue(invoice, "invoices.0.line_items.0.quantity", "")
        # Result 2 - Callout Fee Discount
        result_61_2_result = getvalue(invoice, "invoices.0.line_items.1.discount_rate", "")
        # Result 3 - Light Fittings Amount (AUD)
        result_61_3_result = getvalue(invoice, "invoices.0.line_items.0.line_amount", "")
        # Result 4 - Callout Fee Amount (AUD)
        result_61_4_result = getvalue(invoice, "invoices.0.line_items.1.line_amount", "")

        # ACTIVITY 6.2
        # Result 1 - Delivery Amount (AUD)
        result_62_1_result = getvalue(invoice, "invoices.0.line_items.2.line_amount", "")
        # Result 2 - Tax Amount
        result_62_2_result = getvalue(invoice, "invoices.0.line_items.2.tax_amount", "")
        # Result 3 - Invoice Total (AUD)
        result_62_3_result = getvalue(invoice, "invoices.0.sub_total", "")

        # GRADES
        # can flesh out options for lesser marks, i.e. 3,2,1
        if result_61_1_result == float('11'):
            result_61_1_mark = 5
        else:
            result_61_1_mark = 2
        
        if result_61_2_result == float('20'):
            result_61_2_mark = 5
        else:
            result_61_2_mark = 4
        
        if result_61_3_result == float('137.50'):
            result_61_3_mark = 5
        else:
            result_61_3_mark = 4

        if result_61_4_result == float('60'):
            result_61_4_mark = 5
        else:
            result_61_4_mark = 5
        
        if result_62_1_result == float('35'):
            result_62_1_mark = 5
        else:
            result_62_1_mark = 3
        
        if result_62_2_result == float('0.00'):
            result_62_2_mark = 5
        else:
            result_62_2_mark = 1
        
        if result_62_3_result == float('232.5'):
            result_62_3_mark = 5
        else:
            result_62_3_mark = 2

       
        # Possible dictionary format for linking grades to feedback?
        auto_feedback_dict = {
            "5": "Awesome work! You have inputted all of the correct data and received an accurate result.",
            "4": "Very close, maybe double check your answer here. Be sure to check each value as one wrong input can disrupt the final calculation.",
            "3": "A few values seem to be wrong here. We suggest re-reading the tasks and make the right values are in the right boxes.",
            "2": "One or two values are correct, but you might need ...",
            "1": "This answer is wrong. Please re-read the question, and start over to ensure you're inputting the correct values."
        }
        
        result_61_1_feedback = auto_feedback_dict[str(result_61_1_mark)]
        result_61_2_feedback = auto_feedback_dict[str(result_61_2_mark)]
        result_61_3_feedback = auto_feedback_dict[str(result_61_3_mark)]
        result_61_4_feedback = auto_feedback_dict[str(result_61_4_mark)]
        result_62_1_feedback = auto_feedback_dict[str(result_62_1_mark)]
        result_62_2_feedback = auto_feedback_dict[str(result_62_2_mark)]
        result_62_3_feedback = auto_feedback_dict[str(result_62_3_mark)]

        total_marks = int(result_61_1_mark + result_61_2_mark + result_61_3_mark + result_61_4_mark
                        + result_62_1_mark + result_62_2_mark + result_62_3_mark)

        return render_template(
            "educator_view.html", 
            title="Educator View", 
            result_61_1_result=result_61_1_result,
            result_61_2_result=result_61_2_result,
            result_61_3_result=result_61_3_result,
            result_61_4_result=result_61_4_result,
            result_62_1_result=result_62_1_result,
            result_62_2_result=result_62_2_result,
            result_62_3_result=result_62_3_result,
            result_61_1_mark=result_61_1_mark,
            result_61_2_mark=result_61_2_mark,
            result_61_3_mark=result_61_3_mark,
            result_61_4_mark=result_61_4_mark,
            result_62_1_mark=result_62_1_mark,
            result_62_2_mark=result_62_2_mark,
            result_62_3_mark=result_62_3_mark,
            result_61_1_feedback=result_61_1_feedback,
            result_61_2_feedback=result_61_2_feedback,
            result_61_3_feedback=result_61_3_feedback,
            result_61_4_feedback=result_61_4_feedback,
            result_62_1_feedback=result_62_1_feedback,
            result_62_2_feedback=result_62_2_feedback,
            result_62_3_feedback=result_62_3_feedback,
            total_marks=total_marks
        )
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