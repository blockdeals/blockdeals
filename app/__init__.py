from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from pymongo import MongoClient
from steem import Steem
from datetime import date, timedelta
import sys, traceback, json, textwrap, requests, pprint

app = Flask(__name__, static_folder='static', static_url_path='')
app.config.from_envvar('BLOCKDEALS_SETTINGS')
app.secret_key=app.config['SESSION_SECRET']

db = MongoClient("mongodb://mongodb:27017").blockdeals

@app.route("/")
def index():
    # TODO: only show non-expired deals... paginate?
    deals = []
    deal_cursor=db.deal.find(
        {
            'deal_end': { '$lte': date.today().isoformat() },
        }
    ).sort('deal_end', -1)
    for deal in deal_cursor:
        deals.append(deal)
    if 'username' in session:
        if 'logged_in' in session:
            print("{} logged_in: {}, authorized: {}".format(session['username'], session['logged_in'], session['authorized']))
        else:
            print("{} logged_in: {}".format(session['username'], False))
    else:
        print("anonymous user")
    return render_template('index.html', deals=deals)

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
        print('Auth of {} successful'.format(session['username']))
        session['authorized'] = False
        pprint.pprint(r.json()['account']['posting'])
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
        print('Login of {} successful'.format(username))
        session['authorized'] = False
        session['logged_in'] = username == r.json()['_id']
        pprint.pprint(r.json()['account']['posting'])
        if 'account_auths' in r.json()['account']['posting']:
            for auth_account in r.json()['account']['posting']['account_auths']:
                if auth_account[0] == "blockdeals":
                    session['authorized'] = True
        session['username'] = username
        session['token'] = token
        return redirect(url_for('index'))
    else:
        session['logged_in'] = False
        return render_template('login_failed.html'), 401


@app.route('/deal', methods=['GET', 'POST'])
def deal():
    deal_form=request.form.to_dict()
    # Test posting
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
        'format': 'markdown',
        'tags': [ 'blockdeals' ]
    }

    permlink = ""

    try:
        # Work out our freebie emoji
        freebie = "&#128077;" if deal_form['freebie'] else "&#10060;"
    except KeyError:
        freebie = "&#10060;"

    try:

        # s = Steem(nodes=['https://api.steemit.com'], gtg.steem.house:8090
        s = Steem(nodes=['https://steemd.steemitstage.com/'],
                  keys=[app.config['POSTING_KEY'], app.config['ACTIVE_KEY']])
        p = s.commit.post(title=deal_form['title'],
                          body="""
# {0}

![{0}]({2})

| Details | |
| - | - |
| &#127991; **Coupon Code** | {3} |
| &#128198; **Starts** | {4} |
| &#128198; **Ends** | {5} |
| &#128176; **Freebie?** | {6} |
| &#128176; **Deal Link** | [{8}]({7}) |

## Description

{1}

---
### Find more deals or earn Steem for posting deals on [BlockDeals](https://blockdeals.org) today!
[![](https://blockdeals.org/assets/images/blockdeals_logo.png)](https://blockdeals.org)
""".
                          format(deal_form['title'],
                                 deal_form['description'],
                                 "https://via.placeholder.com/128x128",
                                 deal_form['coupon_code'],
                                 deal_form['deal_start'],
                                 deal_form['deal_end'],
                                 freebie,
                                 deal_form['url'],
                                 textwrap.shorten(deal_form['title'], width=40, placeholder="...")),
                          author=session['username'],
                          json_metadata=json_metadata,
                          comment_options=comment_options,
                          self_vote=True)

        permlink = p['operations'][0][1]['permlink']
        print(permlink)
        deal_form['permlink'] = permlink
        deal_form['steem_user'] = session['username']
        print(db['deal'].insert(deal_form))
    except Exception as e:
        print("***> SOMETHING FAILED")
        print(e)
        traceback.print_exc(file=sys.stdout)
        pass

    # TODO: make a pretty template but for now go to the post
    return redirect("https://steemit.com/@{}/{}".format(session['username'], permlink), code=302)