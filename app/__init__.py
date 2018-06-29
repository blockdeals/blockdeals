from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash, Response
from flaskext.markdown import Markdown
from pymongo import MongoClient
from steem import Steem
from datetime import date, timedelta, datetime
from dateutil import parser
from slugify import slugify
import sys, traceback, json, textwrap, requests, pprint, time, math, arrow

app = Flask(__name__, static_folder='static', static_url_path='')
app.config.from_envvar('BLOCKDEALS_SETTINGS')
app.secret_key=app.config['SESSION_SECRET']
admins = app.config['ADMINS'].split(',')
Markdown(app)

db = MongoClient("mongodb://mongodb:27017").blockdeals

def confirm_user():
    if not 'token' in session or not 'username' in session:
        return False

    r = requests.get('https://v2.steemconnect.com/api/me', headers={ 'Authorization': session['token'] })
    if r.status_code == 200:
        session['authorized'] = False
        if r.json()['_id'] != session['username']:
            return False
        if session['username'] == "blockdeals":
            session['authorized'] = True
        elif 'account_auths' in r.json()['account']['posting']:
            for auth_account in r.json()['account']['posting']['account_auths']:
                if auth_account[0] == "blockdeals":
                    session['authorized'] = True
                    app.logger.info('Confirmed token and auth of {} successful'.format(session['username']))
                    return True
    else:
        session['logged_in'] = False
    return False

def post_to_steem(deal, update=False):
    comment_options = {
        'max_accepted_payout': '1000000.000 SBD',
        'percent_steem_dollars': 10000,
        'allow_votes': True,
        'allow_curation_rewards': True,
        'extensions': [[0, {
            'beneficiaries': [
                {'account': 'blockdeals', 'weight': 1000}
            ]}
        ]]
    }

    permlink = ""
    deal_post_data = {}

    # populate sanitised deal data
    deal_post_data['title'] = deal['title'].strip()
    deal_post_data['url'] = deal['url']
    deal_post_data['brand_code'] = slugify(deal['brand'])
    deal_post_data['description'] = deal['description']

    try:
        deal_post_data['freebie'] = True if deal['freebie'] == 'on' else False
    except KeyError:
        deal_post_data['freebie'] = False

    # TODO: validate image?
    if 'image_url' not in deal or deal['image_url'] == "":
        deal_post_data['image_url'] = 'https://blockdeals.org/assets/images/logo_round.png'
    else:
        deal_post_data['image_url'] = deal['image_url']

    if 'global' in deal and deal['global'] == 'on':
        deal_post_data['global'] = True
    else:
        deal_post_data['global'] = False
        deal_post_data['country_code'] = deal['country_code']

    if not 'coupon_code' in deal or deal['coupon_code'].strip() == "":
        deal_post_data['coupon_code'] = False
    else:
        deal_post_data['coupon_code'] = deal['coupon_code'].strip()

    try:
        deal_post_data['date_start'] = parser.parse(deal['deal_start']).isoformat()
    except ValueError:
        deal_post_data['date_start'] = date.today().isoformat()
    try:
        deal_post_data['date_end'] = parser.parse(deal['deal_end']).isoformat()
    except ValueError:
        deal_post_data['date_end'] = (parser.parse(deal_post_data['date_start']) + timedelta(days=45)).isoformat()

    json_metadata = {
        'community': 'blockdeals',
        'app': 'blockdeals/1.0.0',
        'format': 'markdown',
        'tags': [ 'blockdeals' ],
        'image': [ "https://steemitimages.com/0x0/" + deal_post_data['image_url'] ],
        'deal': deal_post_data
    }

    if 'country_code' in deal_post_data and not deal_post_data['global']:
        json_metadata['tags'].append('blockdeals-'+deal['country_code'])
    else:
        json_metadata['tags'].append('blockdeals-global')

    app.logger.info("deal_post_data: {}".format(deal_post_data))
    body = render_template("deal_post.md", deal=deal_post_data)

    try:
        if 'POST_TO_STEEM' in app.config and app.config['POST_TO_STEEM'] == "1":
            s = Steem(nodes=['https://rpc.buildteam.io', 'https://api.steemit.com', 'https://steemd.steemitstage.com'],
                      keys=[app.config['POSTING_KEY'], app.config['ACTIVE_KEY']])
            if update:
                p = s.commit.post(title=deal['title'],
                                  body=body,
                                  author=session['username'],
                                  json_metadata=json_metadata)
            else:
                p = s.commit.post(title=deal['title'],
                                  body=body,
                                  author=session['username'],
                                  json_metadata=json_metadata,
                                  comment_options=comment_options,
                                  self_vote=True)

            permlink = p['operations'][0][1]['permlink']
            app.logger.info("Posted to STEEM with id={}".format(permlink))
            return True
        else:
            app.logger.info("Skipped posting to steem:\n\n{}".format(body))
            return False
    except Exception as e:
        app.logger.info(e)
        traceback.print_exc(file=sys.stdout)
        return False

@app.template_filter('humanize')
def _jinja2_filter_humanize(t):
    l = arrow.get(parser.parse(t))
    return l.humanize()

@app.template_filter('reputation')
def _jinja2_filter_reputation(rep):
    rep = int(rep)
    calc = (math.log10(abs(rep) - 10) - 9)
    if rep < 0:
        calc = -calc
    return int(calc * 9 + 25)

@app.template_filter('expired')
def _jinja2_filter_expired(date):
    date = parser.parse(date)
    native = date.replace(hour=23, minute=59, tzinfo=None)
    ds = (native-date.today()).total_seconds()
    if ds < 0:
        return True
    else:
        return False

@app.template_filter('expires_class')
def _jinja2_filter_expires_class(date, fmt=None):
    date = parser.parse(date)
    native = date.replace(hour=23, minute=59, tzinfo=None)
    days = (native-date.today()).days
    if days <= 2:
        return "red pulse"
    else:
        return "grey lighten-1"

@app.template_filter('expires_time')
def _jinja2_filter_expires_time(date, fmt=None):
    date = parser.parse(date)
    native = date.replace(hour=23, minute=59, tzinfo=None)
    days = (native-date.today()).days
    ds = (native-date.today()).total_seconds()
    if ds < 0:
        return "{} day{} ago".format(abs(days), '' if abs(days) == 1 else 's')
    elif ds < 86400:
        return "now"
    elif ds < 172800:
        return "soon"
    else:
        return "in {} day{}".format(days, '' if days == 1 else 's')

@app.template_filter('datetimeformat')
def _jinja2_filter_datetime(date, fmt=None):
    date = parser.parse(date)
    native = date.replace(tzinfo=None)
    format='%b %d, %Y'
    return native.strftime(format)

@app.route("/blockdeals/@<author>/<permlink>")
def read_deal(author, permlink):
    try:
        r = requests.get(
            'https://api.steemjs.com/getState?path=/blockdeals/@{}/{}'.format(author, permlink))
        if r.status_code == 200:
            all_content = r.json()['content']
            content = all_content['{}/{}'.format(author, permlink)]
            json_metadata = json.loads(content['json_metadata'])
            deal_metadata = json_metadata['deal']
            payout = float(content['pending_payout_value'].split(" ")[0]) + float(content['total_payout_value'].split(" ")[0])
            return render_template('details.html', author=author, permlink=permlink, json_metadata=json_metadata, deal=deal_metadata, content=all_content, payout="{0:.2f}".format(payout))
        else:
            return render_template('404.html'), 404
    except Exception as e:
        app.logger.info(e)
        return redirect('https://steemit.com/blockdeals/@{}/{}'.format(author, permlink))

@app.route("/vote/<author>/<permlink>/<kind>")
def vote(author, permlink, kind):
    if 'logged_in' in session and session['logged_in'] and 'authorized' in session and session['authorized'] and 'username' in session:
        try:
            weight=100
            if kind == "flag":
                weight=-100
            identifier = "@" + author + "/" + permlink
            if 'POST_TO_STEEM' in app.config and app.config['POST_TO_STEEM'] == "1":
                s = Steem(nodes=['https://rpc.buildteam.io', 'https://api.steemit.com', 'https://steemd.steemitstage.com'],
                        keys=[app.config['POSTING_KEY'], app.config['ACTIVE_KEY']])
                p = s.commit.vote(identifier, weight, account=session['username'])
                app.logger.info(p)
            return jsonify({ 'status': True })
        except Exception as e:
            app.logger.info(e)
            return jsonify({ 'status': False, 'msg': 'unknown exception' })
    else:
        return jsonify({ 'status': False, 'msg': 'please login and authorize first' })

@app.route("/whoami")
def whoami():
    if 'username' in session:
        return jsonify({ 'username': session['username']})
    else:
        return jsonify({ 'username': "" });

@app.route("/update/<permlink>", methods=['GET', 'POST'])
def update(permlink):
    if 'logged_in' in session and session['logged_in'] and 'username' in session and session['username'] in app.config['ADMINS'].split(','):
        if request.method == 'POST':
            deal_update=request.form.to_dict()

            # fix some values
            if deal_update['warning'].strip() != "":
                deal_update['available'] = False
            else:
                deal_update['available'] = True
            if not 'freebie' in deal_update:
                deal_update['freebie'] = ''
            if not 'global' in deal_update:
                deal_update['global'] = ''
            if not 'hide' in deal_update:
                deal_update['hide'] = False;
            else:
                deal_update['hide'] = True;
            try:
                deal_update['deal_start'] = parser.parse(deal_update['deal_start']).isoformat()
            except ValueError:
                deal_update['deal_start'] = date.today().isoformat()
            try:
                deal_update['deal_end'] = parser.parse(deal_update['deal_end']).isoformat()
            except ValueError:
                deal_update['deal_end'] = (date.today() + timedelta(days=45)).isoformat()
            deal_update['deal_expires'] = deal_update['deal_end']
            deal_update['brand_code'] = slugify(deal_update['brand'])

            # TODO: needs more testing on testnet...
            # p = post_to_steem(deal_update, update=True)
            # app.logger.info("STEEM updated? {}".format(p))

            app.logger.info("updating {}: {}".format(permlink, deal_update))
            try:
                db.deal.update_one({ 'permlink': permlink },
                                   { '$set': deal_update }, upsert=False)
            except Exception as e:
                flash(u'Sorry but there was an error trying to update your deal: ' + textwrap.shorten(str(e), width=80, placeholder="..."), 'error')
            return redirect(url_for('index'))
        else:
            deal = db.deal.find_one({'permlink':  permlink })
            app.logger.info("requested update of: {}".format(deal))
            return render_template('update.html', deal=deal)
    else:
        app.logger.info("non-authorised update attempt ({}, {})".format(permlink, session['username'] if 'username' in session else 'anon'))
        return render_template('login_failed.html'), 401

@app.route("/")
def index():
    # TODO: only show non-expired deals... paginate?
    deals = []
    deal_cursor = db.deal.find({'deal_expires': { '$gte': date.today().isoformat()}, 'hide': { '$ne': True}}).sort([('_id', -1)])
    for deal in deal_cursor:
        deals.append(deal)
    if 'username' in session:
        if 'logged_in' in session:
            app.logger.info("{} logged_in: {}, authorized: {}".format(session['username'], session['logged_in'], session['authorized']))
        else:
            app.logger.info("{} logged_in: {}".format(session['username'], False))
    else:
        app.logger.info("anonymous user")
    return render_template('index.html', deals=deals, session=session, admins=admins)

@app.route("/trending")
def trending():
    return render_template('trending.html')

@app.route("/created")
def created():
    return render_template('created.html')

@app.route("/hot")
def hot():
    return render_template('hot.html')

@app.route("/countries")
def countries_json():
    countries = db.deal.find({ 'country_code': { '$ne': '' }}).distinct('country_code')
    return jsonify(sorted(countries, reverse=True))

@app.route("/country/<country>")
def countries(country):
    deals = []
    deal_cursor=db.deal.find({'deal_expires': { '$gte': date.today().isoformat()}, 'country_code': country, 'hide': { '$ne': True}}).sort([('_id', -1)])
    for deal in deal_cursor:
        deals.append(deal)
    return render_template('index.html', deals=deals, country=country, session=session, admins=admins)

@app.route("/freebies")
def freebies():
    deals = []
    deal_cursor=db.deal.find({'deal_expires': { '$gte': date.today().isoformat()}, 'freebie': 'on', 'hide': { '$ne': True}}).sort([('_id', -1)])
    for deal in deal_cursor:
        deals.append(deal)
    return render_template('index.html', deals=deals, session=session, admins=admins)

@app.route("/brand/<brand>")
def brands(brand):
    deals = []
    deal_cursor=db.deal.find({'deal_expires': { '$gte': date.today().isoformat()}, 'brand_code': brand, 'hide': { '$ne': True}}).sort([('_id', -1)])
    for deal in deal_cursor:
        deals.append(deal)
    return render_template('index.html', deals=deals, session=session, admins=admins)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.route('/logout', methods=['GET'])
def logout():
    session.pop('username', None)
    session.pop('token', None)
    session.pop('authorized', None)
    session['logged_in'] = False
    return redirect(url_for('index'))

@app.route('/auth', methods=['GET'])
def authorized():
    if not 'logged_in' in session or not session['logged_in']:
        return render_template('login_failed.html'), 401

    r = requests.get('https://v2.steemconnect.com/api/me', headers={ 'Authorization': session['token'] })
    if r.status_code == 200:
        app.logger.info('Auth of {} successful'.format(session['username']))
        session['authorized'] = False
        if r.json()['_id'] != session['username']:
            session['logged_in'] = False
            return render_template('login_failed.html'), 401
        if session['username'] == "blockdeals":
            session['authorized'] = True
        if 'account_auths' in r.json()['account']['posting']:
            for auth_account in r.json()['account']['posting']['account_auths']:
                if auth_account[0] == "blockdeals":
                    session['authorized'] = True
        return redirect(url_for('index'))
    else:
        session['logged_in'] = False
        return render_template('login_failed.html'), 401

@app.route('/complete/sc/', methods=['GET'])
def complete_sc():
    # TODO: verify token
    token = request.args.get('access_token')
    expire = request.args.get('expires_in')
    username = request.args.get('username')
    r = requests.get('https://v2.steemconnect.com/api/me', headers={ 'Authorization': token })
    if r.status_code == 200:
        app.logger.info('Login of {} successful'.format(username))
        session['authorized'] = False
        session['logged_in'] = username == r.json()['_id']
        if username == "blockdeals":
            session['authorized'] = True
        elif 'account_auths' in r.json()['account']['posting']:
            for auth_account in r.json()['account']['posting']['account_auths']:
                if auth_account[0] == "blockdeals":
                    session['authorized'] = True
        session['username'] = username
        session['token'] = token
        return redirect(url_for('index'))
    else:
        session['logged_in'] = False
        return render_template('login_failed.html'), 401

@app.route('/comment/<parent_author>/<parent_permlink>', methods=['POST'])
def post_comment(parent_author, parent_permlink):
    if not confirm_user():
        return render_template('login_failed.html'), 401

    comment_form=request.form.to_dict()

    comment_options = {
        'max_accepted_payout': '1000000.000 SBD',
        'percent_steem_dollars': 10000,
        'allow_votes': True,
        'allow_curation_rewards': True,
        'extensions': [[0, {
            'beneficiaries': [
                {'account': 'blockdeals', 'weight': 1000}
            ]}
        ]]
    }

    json_metadata = {
        'community': 'blockdeals',
        'app': 'blockdeals/1.0.0',
        'format': 'markdown'
    }

    try:
        if 'POST_TO_STEEM' in app.config and app.config['POST_TO_STEEM'] == "1":
            s = Steem(nodes=['https://rpc.buildteam.io', 'https://api.steemit.com', 'https://steemd.steemitstage.com'],
                      keys=[app.config['POSTING_KEY'], app.config['ACTIVE_KEY']])
            p = s.commit.post(body=comment_form['body'],
                              title="",
                              author=session['username'],
                              json_metadata=json_metadata,
                              reply_identifier="@{}/{}".format(parent_author, parent_permlink),
                              comment_options=comment_options)

            permlink = p['operations'][0][1]['permlink']
            app.logger.info("Posted to STEEM with id={}".format(permlink))
        else:
            app.logger.info("Skipped posting to steem:\n\n{}".format(comment_form['body']))
            permlink = "testing-{}".format(int(time.time()))
    except Exception as e:
        app.logger.info(e)
        traceback.print_exc(file=sys.stdout)
        flash(u'Sorry but there was an error trying to post your comment: ' + textwrap.shorten(str(e), width=80, placeholder="..."), 'error')
        return redirect(url_for("index"))

    if 'return_to' in comment_form:
        return redirect(comment_form['return_to'], code=302)
    else:
        return redirect(url_for("index"), code=302)

@app.route('/deal', methods=['POST'])
def deal():
    if not confirm_user():
        return render_template('login_failed.html'), 401

    deal_form=request.form.to_dict()

    comment_options = {
        'max_accepted_payout': '1000000.000 SBD',
        'percent_steem_dollars': 10000,
        'allow_votes': True,
        'allow_curation_rewards': True,
        'extensions': [[0, {
            'beneficiaries': [
                {'account': 'blockdeals', 'weight': 1000}
            ]}
        ]]
    }

    permlink = ""
    deal_post_data = {}

    # populate sanitised deal data
    deal_post_data['title'] = deal_form['title'].strip()
    deal_post_data['url'] = deal_form['url']
    if deal_form['brand'].strip() != "":
        deal_post_data['brand_code'] = slugify(deal_form['brand'].strip())
    deal_post_data['description'] = deal_form['description']

    try:
        deal_post_data['freebie'] = True if deal_form['freebie'] == 'on' else False
    except KeyError:
        deal_post_data['freebie'] = False

    if 'image_url' not in deal_form or deal_form['image_url'] == "":
        deal_post_data['image_url'] = 'https://blockdeals.org/assets/images/logo_round.png'
    else:
        deal_post_data['image_url'] = deal_form['image_url']

    if 'global' in deal_form and deal_form['global'] == 'on':
        deal_post_data['global'] = True
    else:
        deal_post_data['global'] = False
        deal_post_data['country_code'] = deal_form['country_code']

    if not 'coupon_code' in deal_form or deal_form['coupon_code'].strip() == "":
        deal_post_data['coupon_code'] = False
    else:
        deal_post_data['coupon_code'] = deal_form['coupon_code'].strip()

    try:
        deal_post_data['date_start'] = parser.parse(deal_form['deal_start']).isoformat()
    except ValueError:
        deal_post_data['date_start'] = date.today().isoformat()
    try:
        deal_post_data['date_end'] = parser.parse(deal_form['deal_end']).isoformat()
    except ValueError:
        deal_post_data['date_end'] = (parser.parse(deal_post_data['date_start']) + timedelta(days=45)).isoformat()

    json_metadata = {
        'community': 'blockdeals',
        'app': 'blockdeals/1.0.0',
        'format': 'markdown',
        'tags': [ 'blockdeals' ],
        'image': [ "https://steemitimages.com/0x0/" + deal_post_data['image_url'] ],
        'deal': deal_post_data
    }

    if 'country_code' in deal_post_data and not deal_post_data['global']:
        json_metadata['tags'].append('blockdeals-'+deal_form['country_code'])
    else:
        json_metadata['tags'].append('blockdeals-global')

    if 'brand_code' in deal_post_data and deal_post_data['brand_code'] != "":
        json_metadata['tags'].append(deal_post_data['brand_code'])

    app.logger.info("deal_post_data: {}".format(deal_post_data))
    body = render_template("deal_post.md", deal=deal_post_data)

    try:
        if 'POST_TO_STEEM' in app.config and app.config['POST_TO_STEEM'] == "1":
            s = Steem(nodes=['https://rpc.buildteam.io', 'https://api.steemit.com', 'https://steemd.steemitstage.com'],
                      keys=[app.config['POSTING_KEY'], app.config['ACTIVE_KEY']])
            p = s.commit.post(title=deal_form['title'],
                              body=body,
                              author=session['username'],
                              json_metadata=json_metadata,
                              comment_options=comment_options,
                              self_vote=True)

            permlink = p['operations'][0][1]['permlink']
            app.logger.info("Posted to STEEM with id={}".format(permlink))
        else:
            app.logger.info("Skipped posting to steem:\n\n{}".format(body))
            permlink = "testing-{}".format(int(time.time()))

        deal_form['permlink'] = permlink
        deal_form['steem_user'] = session['username']
        try:
            deal_form['deal_start'] = parser.parse(deal_form['deal_start']).isoformat()
        except ValueError:
            deal_form['deal_start'] = date.today().isoformat()
        try:
            deal_form['deal_end'] = parser.parse(deal_form['deal_end']).isoformat()
        except ValueError:
            deal_form['deal_end'] = (date.today() + timedelta(days=45)).isoformat()
        deal_form['deal_expires'] = deal_form['deal_end']
        deal_form['brand_code'] = slugify(deal_form['brand'])
        mongo_id = db['deal'].insert(deal_form)
        app.logger.info("saved to mongodb: {}\n{}".format(mongo_id, deal_form))
    except Exception as e:
        app.logger.info(e)
        traceback.print_exc(file=sys.stdout)
        flash(u'Sorry but there was an error trying to post your deal: ' + textwrap.shorten(str(e), width=80, placeholder="..."), 'error')
        return redirect(url_for("submit_page"))

    # TODO: make a pretty template but for now go to the post
    if 'POST_TO_STEEM' in app.config and app.config['POST_TO_STEEM'] == "1":
        return redirect("/blockdeals/@{}/{}".format(session['username'], permlink), code=302)
    else:
        return redirect(url_for("index"))

@app.route('/submit')
def submit_page():
    if 'logged_in' in session and session['logged_in'] and 'authorized' in session and session['authorized']:
        return render_template("submit_deals.html")
    return redirect(url_for('index'))

@app.route('/sitemap.xml', methods=['GET'])
def sitemap():
    pages=[]
    ten_days_ago = (date.today() - timedelta(days=10)).isoformat()

    # static pages
    for rule in app.url_map.iter_rules():
        if "GET" in rule.methods and len(rule.arguments)==0:
            pages.append([rule.rule, ten_days_ago])

    # deals
    deal_cursor = db.deal.find({'hide': { '$ne': True}}).sort([('_id', -1)])
    for deal in deal_cursor:
        if 'steem_user' in deal:
            pages.append(["/blockdeals/@{}/{}".format(deal['steem_user'], deal['permlink']), parser.parse(deal['deal_start']).date().isoformat()])

    sitemap_xml = render_template('sitemap.xml', pages=pages)
    return Response(sitemap_xml, mimetype='application/xml')
