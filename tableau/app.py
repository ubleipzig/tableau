#!/usr/bin/env python
# coding: utf-8

from crossdomain import crossdomain
from flask import (Flask, render_template, session, redirect, request, url_for,
                   jsonify, Response, send_from_directory, abort, flash)
from werkzeug.wsgi import DispatcherMiddleware
from werkzeug.serving import run_simple
from utils import dbopen
from timer import Timer
from operator import itemgetter
import collections
import config
import time
import elasticsearch
import json
import os
import random

app = Flask(__name__)
app.secret_key = 'A0Zr98j/3yXasdsadR~sdgXHH!jmN]LWX/,?RT'

app.config['DEBUG'] = True
# app.config['APPLICATION_ROOT'] = ''

dispatcher = DispatcherMiddleware(app, {
    '/deduplication':     app
})


NAME_SOURCE_ID_MAP = {
    'bsz': 0,
    'nep': 3,
    'ebl': 4,
    'naxos': 5,
    'mor': 6,
    'pao': 7,
    'lfer': 8,
    'ema': 9,
    'mtc': 10,
    'bms': 11,
    'bvb': 12,
    'disson': 13,
    'rism': 14,
    'imslp': 15,
    'elsevier': 16,
    'nl': 17,
    'oso': 18,
    'ksd': 19,
    'bnf': 20,
    'gbv': 21,
    'qucosa': 22,
    'hszigr': 23,
    'ebrary': 24,
    'swbod': 25,
    'doab': 26,
    'doaj': 28,
}

def parse_feedback_string(feedback):
    """
    # feedback url: left::right::vote::started, e.g.
    # nep:21321938::ebl:12319898::OK::12312318239.12
    """
    Feedback = collections.namedtuple('Feedback', ['leftIndex', 'leftId',
                                                   'rightIndex', 'rightId', 'vote',
                                                   'started'])
    left, right, vote, started = feedback.split("::", 3)
    leftIndex, leftId = left.split(":", 1)
    rightIndex, rightId = right.split(":", 1)
    return Feedback(leftIndex, leftId, rightIndex, rightId, vote, started)


@app.before_request
def ensure_pairs():
    """ Ensure pairs are defined. """
    if not 'pairs' in session or not session['pairs']:
        with dbopen(config.SIM_DB) as cursor:
            cursor.execute("""SELECT DISTINCT i1, i2, count(*)
                              FROM similarity group by i1, i2""")
            results = cursor.fetchall()
            session['pairs'] = [tuple(result[:2]) for result in results]


@app.context_processor
def utility_processor():
    def now():
        return time.time()
    def source_id_link(source_id, base='https://katalog.ub.uni-leipzig.de'):
        return '%s/Search/Results?lookfor=source_id:%s' % (base, source_id)
    def record_id_link(record_id, base='https://katalog.ub.uni-leipzig.de'):
        return '%s/Search/Results?lookfor=record_id:%s' % (base, record_id)
    return dict(now=now, source_id_link=source_id_link,
                record_id_link=record_id_link)

@app.route("/sample")
def sample():
    es = elasticsearch.Elasticsearch()
    stats = es.indices.stats()
    counter = collections.Counter()
    for key, value in stats.get('indices').iteritems():
        count = value.get('primaries').get('docs').get('count')
        counter[key] = count

    return render_template('sample.html', name='sample', counter=counter)


@app.route("/count")
def count():
    es = elasticsearch.Elasticsearch()
    stats = es.indices.stats()
    counter = collections.Counter()
    for key, value in stats.get('indices').iteritems():
        count = value.get('primaries').get('docs').get('count')
        counter[key] = count
    return Response(json.dumps(counter.most_common()), mimetype="application/json")


@app.route("/pairs")
def pairs():
    with dbopen(SIM_DB) as cursor:
        cursor.execute("""SELECT distinct i1, i2, count(*)
                          FROM similarity GROUP BY i1, i2""")
        results = cursor.fetchall()
    return Response(json.dumps(results), mimetype="application/json")


@app.route("/summary")
def summary():
    # votes collected
    with dbopen(config.FEEDBACK_DB) as cursor:
        cursor.execute("""SELECT vote, COUNT(*) FROM feedback group by vote""")
        result = cursor.fetchall()
        groups = {vote: count for vote, count in result}

        cursor.execute("""SELECT COUNT(*) FROM feedback""")
        result = cursor.fetchone()
        votes = {'total': result[0], 'groups': groups}

    # current source in SIM_DB
    with dbopen(config.SIM_DB) as cursor:
        cursor.execute("SELECT DISTINCT i1, i2, count(*) as c from similarity group by i1, i2")
        results = cursor.fetchall()
        sources = [(i1.upper(), i2.upper(), count, (i1, i2) in session['pairs'])
                   for i1, i2, count in results]

    return render_template('summary.html', name='summary', votes=votes, sources=sources)


@app.route("/search")
def search():

    query = request.args.get('q')
    hits = []
    if query:
        with dbopen(config.SIM_DB) as cursor:
            cursor.execute("""SELECT DISTINCT r1 from similarity UNION
                              SELECT DISTINCT r2 from similarity""")
            results = cursor.fetchall()
            joined = [item for sublist in results for item in sublist]

        es = elasticsearch.Elasticsearch()

        result = es.search(index=['bsz', 'nep', 'ebl'], body={'query': {
            'constant_score': {'filter': {'and':
                [{'ids': {'values': joined}},
                 {'query': {'query_string': {'query': 'elevation'}}}]}}}},
                 size=10)
        hits = result['hits']['hits']
    return render_template('search.html', name='search', hits=hits)


@app.route("/doc/<index>/<id>")
@crossdomain(origin='*')
def doc(index, id):
    with Timer() as timer:
        es = elasticsearch.Elasticsearch()
        source = es.get_source(index=index, id=id)
    app.logger.debug("ES query: %s" % timer.elapsed_s)
    return jsonify(source)


@app.route("/settings", methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        pairs = [tuple(k.split('-')) for k, v in request.form.iteritems() if v == 'on']
        session['pairs'] = pairs
        return redirect(url_for('begin'))

    with dbopen(config.SIM_DB) as cursor:
        cursor.execute("SELECT DISTINCT i1, i2, count(*) from similarity group by i1, i2")
        results = cursor.fetchall()
    return render_template('settings.html', results=results)


@app.route("/begin")
def begin():
    """ Pick an item from the database and redirect to the comparison screen """
    filters = ["""(i1 = '{0}' AND i2 = '{1}')""".format(i1, i2)
               for i1, i2 in session.get('pairs', [])]
    disjunction = " OR ".join(filters)
    where_clause = "WHERE {}".format(disjunction) if disjunction else ""

    with dbopen(config.SIM_DB) as cursor:
        cursor.execute("""SELECT * FROM similarity
                          %s ORDER BY RANDOM() LIMIT 1""" % where_clause)
        result = cursor.fetchone()
    left = "%s:%s" % (result[1], result[2])
    right = "%s:%s" % (result[3], result[4])
    return redirect(url_for('compare', left=left, right=right))

@app.route("/initdb")
def initdb():
    """ Initialize feedback database. """
    with dbopen(config.FEEDBACK_DB) as cursor:
        cursor.execute("""CREATE TABLE IF NOT EXISTS feedback
                          (i1 TEXT, r1 TEXT, i2 TEXT, r2 TEXT,
                            vote TEXT, ip TEXT, started REAL, stopped REAL)""")
    return redirect(url_for('hello'))


@app.route("/compared")
@crossdomain(origin='*')
def compared():
    with dbopen(config.FEEDBACK_DB) as cursor:
        cursor.execute("""SELECT COUNT(*) FROM feedback""")
        result = cursor.fetchone()
    return jsonify(compared=result[0])


@app.route("/compare")
def compare():
    # see if we got feedback
    feedback_arg = request.args.get('feedback')
    if feedback_arg:
        try:
            stopped = time.time()
            feedback = parse_feedback_string(feedback_arg)
            with dbopen(config.FEEDBACK_DB) as cursor:
                cursor.execute("""INSERT INTO feedback
                    (i1, r1, i2, r2, vote, ip, started, stopped)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?) """,
                    (feedback.leftIndex, feedback.leftId,
                     feedback.rightIndex, feedback.rightId,
                     feedback.vote, request.remote_addr,
                     feedback.started, stopped))
        except Exception as err:
            app.logger.error(err)
            abort(500)
        else:
            app.logger.debug("Wrote feedback for: %s" % request.args)
            flash(u'Vielen Dank für Ihr Votum.')
            # show the next comparison ...
            return redirect(url_for('compare', left=request.args.get('left'),
                                               right=request.args.get('right')))

    # count the feedback data points
    with dbopen(config.FEEDBACK_DB) as cursor:
        cursor.execute("""SELECT COUNT(*) FROM feedback""")
        result = cursor.fetchone()
    compared = result[0]

    # request argument spelunking
    try:
        left, right = itemgetter('left', 'right')(request.args)
        leftIndex, leftId = left.split(":", 1)
        rightIndex, rightId = right.split(":", 1)
    except KeyError as error:
        abort(400)

    # the payload for the current comparison
    payload = {"left": {"index": leftIndex, "id": leftId,
                        "source_id": NAME_SOURCE_ID_MAP.get(leftIndex)},
               "right": {"index": rightIndex, "id": rightId,
                         "source_id": NAME_SOURCE_ID_MAP.get(rightIndex)},
               "base": config.BASE}

    # prefetch next comparison pair
    filters = ["""(i1 = '{0}' AND i2 = '{1}')""".format(i1, i2)
               for i1, i2 in session.get('pairs', [])]
    disjunction = " OR ".join(filters)
    where_clause = "WHERE {}".format(disjunction) if disjunction else ""

    with dbopen(config.SIM_DB) as cursor:
        cursor.execute("""SELECT * FROM similarity
                          %s ORDER BY RANDOM() LIMIT 1""" % where_clause)
        result = cursor.fetchone()
    left = "%s:%s" % (result[1], result[2])
    right = "%s:%s" % (result[3], result[4])
    next_pair = {'left': left, 'right': right}

    return render_template('compare.html', name='compare', payload=payload,
                           next_pair=next_pair, compared=compared)


@app.route("/")
def hello():
    return redirect(url_for('summary'))

if __name__ == "__main__":
    # app.run(debug=True, host="0.0.0.0")
    # dispatcher.run(debug=True, host="0.0.0.0")
    run_simple('0.0.0.0', 5000, dispatcher, use_reloader=True)
