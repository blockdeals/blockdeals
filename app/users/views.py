from flask import Blueprint, render_template, abort
from jinja2 import TemplateNotFound


user_blueprint = Blueprint('user_blueprint', __name__, template_folder='templates')

"""
Submit_page:

returns the html page for users to submit a deal

"""

@user_blueprint.route('/submit')
def submit_page():
    return render_template("users/submit_deals.html")


"""
login:

returns the html page for users to login to the website

"""

@user_blueprint.route('/login')
def login():
    return render_template("users/../../templates/login_modal.html")


"""
deals_page:

returns the html page for users to view current deals on the blockchain. 

"""

@user_blueprint.route('/deals')
def deals_page():
    return render_template("users/deals_page.html")


"""
community:

returns the html page for users to view the community page which will be a forum type page.

"""

@user_blueprint.route('/community')
def community():
    return render_template("users/community.html")